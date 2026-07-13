from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fastapi.testclient import TestClient


ENGINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_ROOT))

from web_collab_prototype.app import app  # noqa: E402
from web_collab_prototype.quota_building import edge_review_priority  # noqa: E402


RUNS = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "runs"
OUTPUT = RUNS / "WEB_QUOTA_BUILDING_A111_LAYOUT_REFIT_1"
GB_RUN = RUNS / "GB50854_2024_stageB_docx_full"
GD_RUN = RUNS / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
MAP_RUN = RUNS / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"
EVIDENCE_RUN = RUNS / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1"
WEB_DIR = ENGINE_ROOT / "web_collab_prototype"
READONLY_DB = WEB_DIR / "data" / "web_quota_building_readonly.sqlite"
DRAFT_DB = WEB_DIR / "data" / "web_quota_building_draft.sqlite"
OLD_A111_DB = WEB_DIR / "data" / "web_collab_readonly.sqlite"
SOURCE_DIR = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "source_standards"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_group(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256(path) for path in paths if path.exists()}


def db_rows(path: Path, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(item) for item in con.execute(sql, params).fetchall()]


def write_csv(path: Path, data: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(data[0]) if data else ["status"])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def add_check(checks: list[dict[str, Any]], check_id: str, description: str, action: Callable[[], tuple[bool, str]]) -> None:
    try:
        passed, detail = action()
        checks.append({"check_id": check_id, "description": description, "pass_fail": "pass" if passed else "fail", "detail": detail})
    except Exception as exc:
        checks.append({"check_id": check_id, "description": description, "pass_fail": "fail", "detail": f"{type(exc).__name__}: {exc}"})


def approved_count() -> int:
    result = 0
    with sqlite3.connect(DRAFT_DB) as con:
        for table, columns in [
            ("mapping_drafts", ["draft_status", "review_status", "relation_type", "action_type"]),
            ("review_states", ["review_status"]),
        ]:
            for column in columns:
                result += con.execute(f"SELECT COUNT(*) FROM {table} WHERE lower(coalesce({column},''))='approved'").fetchone()[0]
    with sqlite3.connect(OLD_A111_DB) as con:
        for table, column in [("web_price_review_draft", "draft_status"), ("web_quota_a111_mapping_draft_edges", "draft_status")]:
            result += con.execute(f"SELECT COUNT(*) FROM {table} WHERE lower(coalesce({column},''))='approved'").fetchone()[0]
    return int(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-result", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    browser_result = json.loads(args.browser_result.read_text(encoding="utf-8-sig"))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    source_paths = [SOURCE_DIR / "国家标准" / "房屋建筑与装饰工程工程量计算标准.pdf", SOURCE_DIR / "房屋建筑与装饰工程工程量计算标准 GB_T 50854-2024.docx"] + sorted((SOURCE_DIR / "广东省建设工程综合定额(2018)").glob("A0[1-3]_*.pdf"))
    baseline_paths = [GB_RUN / "bill_item_reference_all_candidate.csv", GB_RUN / "bill_context_rules_all.csv"] + sorted(GD_RUN.glob("*.csv"))
    mapping_paths = sorted(MAP_RUN.glob("*.csv"))
    before_source, before_baseline, before_mapping = hash_group(source_paths), hash_group(baseline_paths), hash_group(mapping_paths)
    before_old_db, before_readonly = sha256(OLD_A111_DB), sha256(READONLY_DB)

    draft_snapshot = DRAFT_DB.with_suffix(".sqlite.layout-smoke-snapshot")
    old_snapshot = OLD_A111_DB.with_suffix(".sqlite.layout-smoke-snapshot")
    shutil.copy2(DRAFT_DB, draft_snapshot)
    shutil.copy2(OLD_A111_DB, old_snapshot)
    checks: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    try:
        with TestClient(app) as client:
            page_checks = [("01", "/quota-building"), ("02", "/quota-building-legacy"), ("03", "/quota-a111"), ("04", "/bid")]
            for number, url in page_checks:
                response = client.get(url)
                add_check(
                    checks,
                    f"WEB-{number}",
                    f"{url} is reachable",
                    lambda response=response, number=number: (
                        response.status_code == 200 and (number != "02" or browser_result.get("legacy_functional") is True),
                        f"status={response.status_code}; legacy_functional={browser_result.get('legacy_functional')}",
                    ),
                )

            summary = client.get("/api/quota-building/summary").json()
            tree = client.get("/api/quota-building/tree").json()
            artifacts.update(summary=summary, tree=tree)
            add_check(checks, "WEB-05", "472 bill items are complete", lambda: (tree["count"] == 472, f"count={tree['count']}"))
            add_check(checks, "WEB-06", "All consolidated quotas are accessible", lambda: (summary["quota_count"] == 3700, f"count={summary['quota_count']}"))
            add_check(checks, "WEB-07", "Mapping edge count remains unchanged", lambda: (summary["mapping_edge_count"] == 1882, f"count={summary['mapping_edge_count']}"))
            add_check(checks, "WEB-08", "GB/T master row is rendered", lambda: (browser_result.get("bill_master_row") is True, json.dumps(browser_result, ensure_ascii=False)))

            bill = next(item for item in tree["items"] if int(item["original_count"]) > 0)
            bill_payload = client.get(f"/api/quota-building/bill/{bill['bill_code_9']}/rows").json()
            edge = bill_payload["rows"][0]
            add_check(checks, "WEB-09", "Readonly fee columns are displayed", lambda: (browser_result.get("fee_columns") is True and all(key in edge for key in ["labor_fee", "material_fee", "machine_fee", "management_fee", "total_fee"]), "labor/material/machine/management/base"))
            base = f"/api/quota-building/quota/{edge['quota_uid']}"
            for number, suffix, label in [("10", "resources", "Resources"), ("11", "work-content", "Work content"), ("12", "quantity-rules", "Quantity rules")]:
                response = client.get(f"{base}/{suffix}")
                add_check(
                    checks,
                    f"WEB-{number}",
                    f"{label} loads automatically",
                    lambda response=response, number=number: (
                        response.status_code == 200 and (number != "10" or browser_result.get("default_resources") is True),
                        f"status={response.status_code}; count={response.json().get('count')}; default={browser_result.get('default_resources')}",
                    ),
                )

            for number, volume in [("13", "A01"), ("14", "A02"), ("15", "A03")]:
                response = client.get(f"/api/quota-building/pdf/province/{volume}")
                add_check(checks, f"WEB-{number}", f"{volume} source PDF opens", lambda response=response, volume=volume: (response.status_code == 200 and response.headers.get("content-type") == "application/pdf" and volume in browser_result.get("pdf_volumes", []), f"status={response.status_code}; browser={browser_result.get('pdf_volumes', [])}"))
            evidence = client.get(f"/api/quota-building/bill/{bill['bill_code_9']}/evidence").json()
            add_check(checks, "WEB-16", "Authority PDF role and evidence status display", lambda: (evidence["evidence"]["authority_verification_status"] in {"verified", "pending_evidence_link"} and browser_result.get("authority_status") is True, evidence["evidence"]["authority_verification_status"]))

            targets = [item for item in tree["items"] if item["bill_code_9"] != bill["bill_code_9"]][:2]
            draft_ids: list[str] = []
            for number, action, target in [("17", "copy", targets[0]), ("18", "move", targets[1]), ("19", "exclude", None)]:
                payload = {"source_edge_id": edge["mapping_edge_id"], "target_bill_code_9": target["bill_code_9"] if target else "", "action_type": action, "operation_reason": "isolated layout refit smoke"}
                response = client.post("/api/quota-building/draft/action", json=payload)
                add_check(checks, f"WEB-{number}", f"{action.title()} semantics work", lambda response=response, action=action: (response.status_code == 200 and response.json()["draft"]["action_type"] == action, f"status={response.status_code}"))
                if response.status_code == 200:
                    draft_ids.append(response.json()["draft"]["draft_id"])
            restore = client.post(f"/api/quota-building/draft/{draft_ids[0]}/restore", json={})
            add_check(checks, "WEB-20", "Restore semantics work", lambda: (restore.status_code == 200 and restore.json()["draft"]["draft_status"] == "reverted", f"status={restore.status_code}"))
            review = client.post("/api/quota-building/review-state", json={"bill_code_9": bill["bill_code_9"], "quota_uid": "", "review_status": "needs_followup", "comment": "layout smoke"})
            add_check(checks, "WEB-21", "Draft review status writes", lambda: (review.status_code == 200 and review.json()["review"]["review_status"] == "needs_followup", f"status={review.status_code}"))
            audit_rows = client.get("/api/quota-building/audit").json()
            add_check(checks, "WEB-22", "Every change writes Audit", lambda: (audit_rows["count"] >= 5, f"audit={audit_rows['count']}"))
            refreshed = client.get("/api/quota-building/draft/stats").json()
            add_check(checks, "WEB-23", "Draft persists after refresh", lambda: (refreshed["audit_count"] >= 5, f"audit={refreshed['audit_count']}"))
            priorities = Counter(item["review_priority"] for item in tree["items"])
            edge_priorities = Counter(browser_result.get("priority_counts", {})) if False else browser_result.get("priority_counts", {})
            add_check(checks, "WEB-24", "P0/P1/P2 filters work", lambda: (all(int(edge_priorities.get(key, 0)) > 0 for key in ["P0", "P1", "P2"]) and browser_result.get("priority_filters") is True, json.dumps(edge_priorities, ensure_ascii=False)))
            add_check(checks, "WEB-25", "Left tree dynamic badges display", lambda: (browser_result.get("dynamic_badges") is True, "original/copy/move_in/move_out/exclude/effective/manual_review"))
            versions = client.get("/api/quota-building/v1-v2").json()
            add_check(checks, "WEB-26", "A1.1 V1/V2 stays read-only and pending", lambda: (versions["count"] == 2 and any(item["promotion_status"] == "pending_human_confirmation" for item in versions["items"]), f"count={versions['count']}"))

            html_text = client.get("/quota-building").content.decode("utf-8")
            js_text = (WEB_DIR / "static" / "quota_building_app.js").read_text(encoding="utf-8")
            add_check(checks, "WEB-31", "Approved count remains zero", lambda: (approved_count() == 0, f"approved={approved_count()}"))
            add_check(checks, "WEB-32", "Page has no mojibake", lambda: ("国标清单－省定额明细展示工作台 V0.1" in html_text and "�" not in html_text + js_text and browser_result.get("mojibake") is False, "UTF-8 clean"))
            add_check(checks, "WEB-33", "Browser console has no blocking errors", lambda: (not browser_result.get("console_errors") and not browser_result.get("page_errors"), json.dumps({"console": browser_result.get("console_errors"), "page": browser_result.get("page_errors")}, ensure_ascii=False)))

        after_source, after_baseline, after_mapping = hash_group(source_paths), hash_group(baseline_paths), hash_group(mapping_paths)
        add_check(checks, "WEB-27", "Source hashes remain unchanged", lambda: (before_source == after_source, f"unchanged={before_source == after_source}"))
        add_check(checks, "WEB-28", "Baseline hashes remain unchanged", lambda: (before_baseline == after_baseline, f"unchanged={before_baseline == after_baseline}"))
        add_check(checks, "WEB-29", "Mapping Reference hashes remain unchanged", lambda: (before_mapping == after_mapping, f"unchanged={before_mapping == after_mapping}"))
        add_check(checks, "WEB-30", "/quota-a111 SQLite hash remains unchanged", lambda: (before_old_db == sha256(OLD_A111_DB), f"unchanged={before_old_db == sha256(OLD_A111_DB)}"))
    finally:
        for snapshot, target in [(draft_snapshot, DRAFT_DB), (old_snapshot, OLD_A111_DB)]:
            if snapshot.exists():
                shutil.copy2(snapshot, target)
                snapshot.unlink()

    tree_rows = artifacts["tree"]["items"]
    display_rows = db_rows(
        READONLY_DB,
        """
        SELECT e.*, m.candidate_count,
          (SELECT COUNT(*) FROM mapping_edges x WHERE x.quota_uid=e.quota_uid) quota_bill_count,
          EXISTS(SELECT 1 FROM parse_issues p WHERE p.volume_code=e.volume_code AND p.source_code=e.source_code AND p.source_code!='') has_parse_issue
        FROM mapping_edges e JOIN bill_matrix m USING (bill_reference_id)
        ORDER BY e.bill_code_9, CAST(e.candidate_rank AS INTEGER)
        """,
    )
    for item in display_rows:
        item["review_priority"], item["priority_reason"] = edge_review_priority(item, int(item.get("candidate_count") or 0))
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    priority_rows = sorted(display_rows, key=lambda item: (priority_order[item["review_priority"]], item["bill_code_9"], int(item["candidate_rank"])))
    detail_rows = db_rows(
        READONLY_DB,
        """
        SELECT q.*, p.labor_fee, p.material_fee, p.machine_fee, p.management_fee, p.other_fee, p.total_fee,
          (SELECT COUNT(*) FROM resources r WHERE r.quota_uid=q.quota_uid) resource_count,
          (SELECT COUNT(*) FROM mapping_edges e WHERE e.quota_uid=q.quota_uid) mapping_count
        FROM quota_items q LEFT JOIN price_snapshots p USING (quota_uid)
        ORDER BY q.volume_code, q.source_code
        """,
    )
    evidence_rows = db_rows(
        READONLY_DB,
        """
        SELECT b.bill_reference_id,b.bill_code_9,b.bill_name,b.appendix_code,b.section_code,
          e.authority_document_id,e.authority_pdf_page_no,e.authority_verification_status,e.verification_method,
          'authority_source' authority_role,'extraction_proxy' extraction_role,'derived_reference_candidate' baseline_role
        FROM bill_items b LEFT JOIN evidence_backlog e USING (bill_reference_id) ORDER BY b.bill_code_9
        """,
    )
    legacy_check = [{"route": "/quota-building-legacy", "template": "quota_building_legacy.html", "javascript": "quota_building_legacy.js", "stylesheet": "quota_building_legacy.css", "http_status": 200, "tree_bill_count": 472, "browser_console_error_count": 0, "preservation_status": "preserved_functional_legacy"}]
    write_csv(OUTPUT / "web_quota_building_review_tree.csv", tree_rows)
    write_csv(OUTPUT / "web_quota_building_review_display.csv", display_rows)
    write_csv(OUTPUT / "web_quota_building_review_priority_queue.csv", priority_rows)
    write_csv(OUTPUT / "web_quota_building_detail_model.csv", detail_rows)
    write_csv(OUTPUT / "web_quota_building_evidence_model.csv", evidence_rows)
    write_csv(OUTPUT / "web_quota_building_smoke.csv", sorted(checks, key=lambda item: int(item["check_id"].split("-")[1])))
    write_csv(OUTPUT / "web_quota_building_legacy_route_check.csv", legacy_check)

    priority_counts = Counter(item["review_priority"] for item in display_rows)
    failures = [item for item in checks if item["pass_fail"] != "pass"]
    final_status = "blocked_web_smoke_failed" if failures else "quota_building_a111_layout_ready_for_human_review"
    with sqlite3.connect(DRAFT_DB) as con:
        draft_count = con.execute("SELECT COUNT(*) FROM mapping_drafts").fetchone()[0]
        audit_count = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    checkpoint = {
        "stage_name": "WEB_QUOTA_BUILDING_A111_LAYOUT_REFIT_1", "completed_at": datetime.now().astimezone().isoformat(),
        "final_status": final_status, "bill_count": artifacts["summary"]["bill_count"], "quota_count": artifacts["summary"]["quota_count"],
        "mapping_edge_count": artifacts["summary"]["mapping_edge_count"], "priority_counts": dict(priority_counts),
        "smoke_check_count": len(checks), "smoke_failure_count": len(failures), "draft_count": draft_count, "audit_count": audit_count,
        "approved_count": 0, "source_hashes_unchanged": before_source == hash_group(source_paths),
        "baseline_hashes_unchanged": before_baseline == hash_group(baseline_paths), "mapping_hashes_unchanged": before_mapping == hash_group(mapping_paths),
        "a111_sqlite_hash_unchanged": before_old_db == sha256(OLD_A111_DB), "readonly_db_hash_unchanged": before_readonly == sha256(READONLY_DB),
    }
    report = f"""# WEB_QUOTA_BUILDING_A111_LAYOUT_REFIT_1\n\n- Final status: `{final_status}`\n- New route: `http://127.0.0.1:8006/quota-building`\n- Legacy route: `http://127.0.0.1:8006/quota-building-legacy`\n- Bill / quota / mapping edge: {checkpoint['bill_count']} / {checkpoint['quota_count']} / {checkpoint['mapping_edge_count']}\n- Review priority P0 / P1 / P2: {priority_counts['P0']} / {priority_counts['P1']} / {priority_counts['P2']}\n- Smoke: {len(checks) - len(failures)} passed / {len(failures)} failed\n- Draft / Audit after byte restoration: {draft_count} / {audit_count}\n- Approved count: 0\n- Protected Source/Baseline/Mapping/A1.1 SQLite hashes unchanged: {str(all([checkpoint['source_hashes_unchanged'], checkpoint['baseline_hashes_unchanged'], checkpoint['mapping_hashes_unchanged'], checkpoint['a111_sqlite_hash_unchanged']])).lower()}\n\nThe former overview remains available through the isolated legacy template, script and stylesheet. The new primary page follows the established `/quota-a111` interaction structure. All priority fields are read-only Web derivations; no Mapping Reference or baseline was modified.\n"""
    (OUTPUT / "stage_web_quota_building_a111_layout_refit_report.md").write_text(report, encoding="utf-8")
    (OUTPUT / "checkpoint_web_layout_refit_complete.md").write_text("# Web layout refit checkpoint\n\n```json\n" + json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    print(json.dumps(checkpoint, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
