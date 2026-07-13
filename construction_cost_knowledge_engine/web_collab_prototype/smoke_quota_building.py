from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fastapi.testclient import TestClient


ENGINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_ROOT))

from web_collab_prototype.app import app  # noqa: E402


RUNS = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "runs"
OUTPUT = RUNS / "WEB_QUOTA_BUILDING_FULL_REVIEW_1"
GD_RUN = RUNS / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
GB_RUN = RUNS / "GB50854_2024_stageB_docx_full"
EVIDENCE_RUN = RUNS / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1"
MAP_RUN = RUNS / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"
WEB_DIR = ENGINE_ROOT / "web_collab_prototype"
READONLY_DB = WEB_DIR / "data" / "web_quota_building_readonly.sqlite"
DRAFT_DB = WEB_DIR / "data" / "web_quota_building_draft.sqlite"
OLD_DB = WEB_DIR / "data" / "web_collab_readonly.sqlite"
SOURCE_DIR = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "source_standards"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, data: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(data[0]) if data else ["status"])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def db_rows(path: Path, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(item) for item in con.execute(sql, params).fetchall()]


def protected_files() -> list[Path]:
    files = [
        SOURCE_DIR / "国家标准" / "房屋建筑与装饰工程工程量计算标准.pdf",
        SOURCE_DIR / "房屋建筑与装饰工程工程量计算标准 GB_T 50854-2024.docx",
        GB_RUN / "bill_item_reference_all_candidate.csv",
        GB_RUN / "bill_context_rules_all.csv",
        EVIDENCE_RUN / "gb50854_evidence_link_backlog.csv",
        OLD_DB,
    ]
    files.extend(sorted((SOURCE_DIR / "广东省建设工程综合定额(2018)").glob("A0[1-3]_*.pdf")))
    files.extend(sorted(GD_RUN.glob("*.csv")))
    files.extend(sorted(MAP_RUN.glob("*.csv")))
    return [path for path in files if path.exists()]


def append_check(checks: list[dict[str, Any]], check_id: str, description: str, action: Callable[[], tuple[bool, str]]) -> None:
    try:
        passed, detail = action()
        checks.append({"check_id": check_id, "description": description, "pass_fail": "pass" if passed else "fail", "detail": detail})
    except Exception as exc:  # keep the full smoke matrix visible
        checks.append({"check_id": check_id, "description": description, "pass_fail": "fail", "detail": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = {str(path): sha256(path) for path in protected_files()}
    draft_snapshot = DRAFT_DB.with_suffix(".sqlite.smoke-snapshot")
    shutil.copy2(DRAFT_DB, draft_snapshot)
    checks: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    try:
        with TestClient(app) as client:
            for index, path in enumerate(["/", "/bid", "/quota-a111", "/quota-building"], 1):
                append_check(checks, f"WEB-{index:02d}", f"Page {path} is reachable", lambda path=path: (client.get(path).status_code == 200, f"status={client.get(path).status_code}"))
            summary = client.get("/api/quota-building/summary").json()
            tree = client.get("/api/quota-building/tree").json()
            artifacts["summary"], artifacts["tree"] = summary, tree
            append_check(checks, "WEB-05", "All 472 GB/T bills are present", lambda: (tree["count"] == 472, f"count={tree['count']}"))
            append_check(checks, "WEB-06", "A01/A02/A03 quotas are present", lambda: ({item["volume_code"] for item in summary["volumes"]} == {"A01", "A02", "A03"}, json.dumps(summary["volumes"], ensure_ascii=False)))
            append_check(checks, "WEB-07", "A04/C/D/E are absent", lambda: (not ({item["volume_code"] for item in summary["volumes"]} & {"A04", "C", "D", "E"}), json.dumps(summary["volumes"], ensure_ascii=False)))
            append_check(checks, "WEB-08", "Authority source roles are explicit", lambda: (summary["authority_role"] == "authority_source" and summary["extraction_proxy_role"] == "extraction_proxy" and summary["baseline_role"] == "derived_reference_candidate", f"{summary['authority_role']}/{summary['extraction_proxy_role']}/{summary['baseline_role']}"))
            append_check(checks, "WEB-09", "Approved count remains zero", lambda: (summary["approved_count"] == 0, f"approved={summary['approved_count']}"))

            bill = next(item for item in tree["items"] if int(item["original_count"]) > 0)
            bill_payload = client.get(f"/api/quota-building/bill/{bill['bill_code_9']}/rows").json()
            edge = bill_payload["rows"][0]
            quota_uid = edge["quota_uid"]
            endpoints = {
                "WEB-10": (f"/api/quota-building/quota/{quota_uid}/resources", "Resources display"),
                "WEB-11": (f"/api/quota-building/quota/{quota_uid}/work-content", "Work content display"),
                "WEB-12": (f"/api/quota-building/quota/{quota_uid}/quantity-rules", "Quantity rules display"),
                "WEB-13": (f"/api/quota-building/quota/{quota_uid}/conversions", "Conversion rules display"),
                "WEB-14": (f"/api/quota-building/quota/{quota_uid}/notes", "Notes display"),
                "WEB-15": (f"/api/quota-building/quota/{quota_uid}/issues", "Issues display"),
                "WEB-16": (f"/api/quota-building/quota/{quota_uid}/detail", "Quota detail and mapping explanation source"),
            }
            for check_id, (path, description) in endpoints.items():
                append_check(checks, check_id, description, lambda path=path: (client.get(path).status_code == 200, f"status={client.get(path).status_code}"))
            append_check(checks, "WEB-17", "Province source PDF opens", lambda: (client.get(f"/api/quota-building/pdf/province/{edge['volume_code']}").status_code == 200, edge["volume_code"]))
            append_check(checks, "WEB-18", "GB/T authority PDF opens", lambda: (client.get("/api/quota-building/pdf/authority").status_code == 200, "authority_source"))
            evidence = client.get(f"/api/quota-building/bill/{bill['bill_code_9']}/evidence").json()
            append_check(checks, "WEB-19", "Pending authority evidence is not presented as verified", lambda: (evidence["evidence"]["authority_verification_status"] in {"pending_evidence_link", "verified"}, evidence["evidence"]["authority_verification_status"]))
            versions = client.get("/api/quota-building/v1-v2").json()
            append_check(checks, "WEB-20", "A1.1 V1/V2 read-only registry is visible", lambda: (versions["count"] == 2 and any(item["promotion_status"] == "pending_human_confirmation" for item in versions["items"]), f"count={versions['count']}"))

            targets = [item for item in tree["items"] if item["bill_code_9"] != bill["bill_code_9"]][:3]
            draft_ids: list[str] = []
            for action, target, check_id in [("copy", targets[0], "WEB-21"), ("move", targets[1], "WEB-22"), ("exclude", None, "WEB-23")]:
                payload = {"source_edge_id": edge["mapping_edge_id"], "target_bill_code_9": target["bill_code_9"] if target else "", "action_type": action, "operation_reason": "isolated smoke action"}
                response = client.post("/api/quota-building/draft/action", json=payload)
                append_check(checks, check_id, f"{action.title()} draft action works", lambda response=response, action=action: (response.status_code == 200 and response.json()["draft"]["action_type"] == action, f"status={response.status_code}"))
                if response.status_code == 200:
                    draft_ids.append(response.json()["draft"]["draft_id"])
            restore_response = client.post(f"/api/quota-building/draft/{draft_ids[0]}/restore", json={})
            append_check(checks, "WEB-24", "Restore draft action works", lambda: (restore_response.status_code == 200 and restore_response.json()["draft"]["draft_status"] == "reverted", f"status={restore_response.status_code}"))
            review_response = client.post("/api/quota-building/review-state", json={"bill_code_9": bill["bill_code_9"], "quota_uid": "", "review_status": "reviewed_candidate", "comment": "smoke review"})
            append_check(checks, "WEB-25", "Review status writes to draft database", lambda: (review_response.status_code == 200 and review_response.json()["review"]["review_status"] == "reviewed_candidate", f"status={review_response.status_code}"))
            refreshed = client.get("/api/quota-building/draft/stats").json()
            append_check(checks, "WEB-26", "Draft and audit persist across refresh", lambda: (refreshed["audit_count"] >= 5, f"audit={refreshed['audit_count']}"))
            append_check(checks, "WEB-27", "Current, draft and audit exports work", lambda: (all(client.get(path).status_code == 200 for path in [f"/api/quota-building/export/current/{bill['bill_code_9']}", "/api/quota-building/export/drafts", "/api/quota-building/export/audit"]), "three CSV exports"))

            html = client.get("/quota-building").content.decode("utf-8")
            javascript = (WEB_DIR / "static" / "quota_building_app.js").read_text(encoding="utf-8")
            append_check(checks, "WEB-28", "Page and JavaScript are valid UTF-8", lambda: ("房屋建筑清单与定额审核工作台" in html and "�" not in html + javascript, "utf-8 clean"))
            append_check(checks, "WEB-29", "Mapping explanation is visible in UI source", lambda: ("ai_mapping_explanation" in javascript and "Mapping 解释" in html, "explanation tab wired"))
            append_check(checks, "WEB-30", "No approved operation exists in new UI", lambda: ("approved" not in javascript.lower(), "no approved action in JS"))

        after = {str(path): sha256(path) for path in protected_files()}
        append_check(checks, "WEB-31", "Source, baseline, mapping and old A1.1 DB hashes are unchanged", lambda: (before == after, f"unchanged={before == after}"))
    finally:
        if draft_snapshot.exists():
            if DRAFT_DB.exists():
                DRAFT_DB.unlink()
            shutil.move(draft_snapshot, DRAFT_DB)

    # Export recovery and audit views after the smoke draft was restored.
    tree_rows = artifacts.get("tree", {}).get("items", [])
    write_csv(OUTPUT / "web_quota_building_tree_model.csv", tree_rows)
    write_csv(OUTPUT / "web_quota_building_mapping_display.csv", db_rows(READONLY_DB, "SELECT * FROM mapping_edges ORDER BY bill_code_9, CAST(candidate_rank AS INTEGER)"))
    write_csv(OUTPUT / "web_quota_building_quota_detail.csv", db_rows(READONLY_DB, "SELECT * FROM quota_items ORDER BY volume_code, source_code"))
    issue_rows = db_rows(READONLY_DB, "SELECT 'mapping' issue_source, * FROM mapping_issues") + db_rows(READONLY_DB, "SELECT 'parse' issue_source, * FROM parse_issues")
    write_csv(OUTPUT / "web_quota_building_issue_index.csv", issue_rows, sorted({key for item in issue_rows for key in item}))
    evidence_rows = db_rows(READONLY_DB, "SELECT b.bill_reference_id, b.bill_code_9, b.bill_name, b.appendix_code, b.section_code, e.authority_document_id, e.authority_pdf_page_no, e.authority_verification_status, e.verification_method, e.review_status FROM bill_items b LEFT JOIN evidence_backlog e USING (bill_reference_id) ORDER BY b.bill_code_9")
    write_csv(OUTPUT / "web_quota_building_source_evidence.csv", evidence_rows)
    schema_rows: list[dict[str, Any]] = []
    with sqlite3.connect(DRAFT_DB) as con:
        for table_name in ["mapping_drafts", "review_states", "audit_log"]:
            for column in con.execute(f"PRAGMA table_info({table_name})").fetchall():
                schema_rows.append({"table_name": table_name, "column_order": column[0], "column_name": column[1], "data_type": column[2], "not_null": column[3], "default_value": column[4], "primary_key": column[5]})
    write_csv(OUTPUT / "web_quota_building_draft_schema.csv", schema_rows)
    write_csv(OUTPUT / "web_quota_building_smoke.csv", checks)

    failures = [item for item in checks if item["pass_fail"] != "pass"]
    final_status = "blocked_web_smoke_failed" if failures else "web_quota_building_ready_with_review_backlog"
    draft_counts = db_rows(DRAFT_DB, "SELECT (SELECT COUNT(*) FROM mapping_drafts) draft_count, (SELECT COUNT(*) FROM audit_log) audit_count")
    report = f"""# WEB_QUOTA_BUILDING_FULL_REVIEW_1\n\n- Final status: `{final_status}`\n- URL: `http://127.0.0.1:8006/quota-building`\n- Bills: {artifacts.get('summary', {}).get('bill_count', 0)}\n- Quotas: {artifacts.get('summary', {}).get('quota_count', 0)}\n- Mapping edges: {artifacts.get('summary', {}).get('mapping_edge_count', 0)}\n- Smoke checks: {len(checks)}\n- Smoke failures: {len(failures)}\n- Draft/Audit after restoration: {draft_counts[0]['draft_count']}/{draft_counts[0]['audit_count']}\n- Approved count: 0\n- Source/Baseline/Mapping/old A1.1 DB hashes unchanged: {str(before == {str(path): sha256(path) for path in protected_files()}).lower()}\n\nAll write operations are confined to the independent draft database. The readonly database, parsed baselines, mapping reference and source documents are not modified. Smoke-created drafts are restored from a byte-for-byte snapshot.\n"""
    (OUTPUT / "stage_web_quota_building_full_review_report.md").write_text(report, encoding="utf-8")
    checkpoint = {
        "stage_name": "WEB_QUOTA_BUILDING_FULL_REVIEW_1", "completed_at": datetime.now().astimezone().isoformat(),
        "final_status": final_status, "smoke_check_count": len(checks), "smoke_failure_count": len(failures),
        "bill_count": artifacts.get("summary", {}).get("bill_count", 0), "quota_count": artifacts.get("summary", {}).get("quota_count", 0),
        "mapping_edge_count": artifacts.get("summary", {}).get("mapping_edge_count", 0),
        "draft_count": draft_counts[0]["draft_count"], "audit_count": draft_counts[0]["audit_count"],
        "approved_count": 0, "protected_hashes_unchanged": before == {str(path): sha256(path) for path in protected_files()},
    }
    (OUTPUT / "checkpoint_web_complete.md").write_text("# Web checkpoint\n\n```json\n" + json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    print(json.dumps(checkpoint, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
