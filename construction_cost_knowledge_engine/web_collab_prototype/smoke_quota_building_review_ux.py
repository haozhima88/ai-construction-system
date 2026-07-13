from __future__ import annotations

import argparse
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


WEB_DIR = ENGINE_ROOT / "web_collab_prototype"
OUTPUT = ENGINE_ROOT / "data" / "private" / "reference_extraction" / "runs" / "WEB_QUOTA_BUILDING_REVIEW_UX_ENHANCEMENT_1"
DRAFT_DB = WEB_DIR / "data" / "web_quota_building_draft.sqlite"
OLD_DRAFT_DB = WEB_DIR / "data" / "web_collab_readonly.sqlite"
SCREENSHOTS = [
    "before_tree_redundant_labels.png",
    "after_tree_simplified_labels.png",
    "after_resizable_layout.png",
    "after_work_content_structured.png",
    "after_quantity_rule_structured.png",
    "after_conversion_rule_structured.png",
    "after_note_structured.png",
    "after_raw_vs_structured_toggle.png",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def add_check(
    checks: list[dict[str, Any]],
    number: int,
    description: str,
    action: Callable[[], tuple[bool, str]],
) -> None:
    try:
        passed, detail = action()
    except Exception as exc:
        passed, detail = False, f"{type(exc).__name__}: {exc}"
    checks.append(
        {
            "check_id": f"UX-{number:03d}",
            "description": description,
            "pass_fail": "pass" if passed else "fail",
            "detail": detail,
        }
    )


def draft_counts() -> dict[str, int]:
    with sqlite3.connect(DRAFT_DB) as connection:
        return {
            "draft": int(connection.execute("SELECT COUNT(*) FROM mapping_drafts").fetchone()[0]),
            "audit": int(connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]),
        }


def approved_count() -> int:
    count = 0
    with sqlite3.connect(DRAFT_DB) as connection:
        for table, columns in [
            ("mapping_drafts", ["draft_status", "review_status", "relation_type", "action_type"]),
            ("review_states", ["review_status"]),
        ]:
            for column in columns:
                count += connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE lower(coalesce({column},''))='approved'"
                ).fetchone()[0]
    with sqlite3.connect(OLD_DRAFT_DB) as connection:
        for table, column in [
            ("web_price_review_draft", "draft_status"),
            ("web_quota_a111_mapping_draft_edges", "draft_status"),
        ]:
            count += connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE lower(coalesce({column},''))='approved'"
            ).fetchone()[0]
    return int(count)


def hash_status(guard: dict[str, Any]) -> dict[str, bool]:
    result = {}
    for group in ("source", "baseline", "mapping", "protected_ui"):
        result[group] = all(Path(path).exists() and sha256(Path(path)) == expected for path, expected in guard[group].items())
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-result", type=Path, required=True)
    parser.add_argument("--guard", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    browser = json.loads(args.browser_result.read_text(encoding="utf-8-sig"))
    guard = json.loads(args.guard.read_text(encoding="utf-8-sig"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    tree = browser["tree"]
    layout = browser["layout"]
    structured = browser["structured"]
    initial = layout["initialGeometry"]
    dragged = layout["draggedGeometry"]
    reloaded = layout["reloadedGeometry"]
    reset = layout["afterReset"]

    add_check(checks, 1, "Tree primary labels omit appendix prefixes", lambda: (tree["redundantPrefixCount"] == 0, f"groups={tree['count']}; redundant={tree['redundantPrefixCount']}"))
    add_check(checks, 2, "Tree shows normalized standard names", lambda: (tree["hasEarthwork"] and tree["hasFoundationSupport"], "土石方工程 / 地基处理与边坡支护工程"))
    add_check(checks, 3, "Main table scrolls horizontally inside its container", lambda: (layout["independentScroll"]["horizontalScroll"]["left"] > 0 and layout["independentScroll"]["horizontalScroll"]["overflowX"] == "auto", json.dumps(layout["independentScroll"]["horizontalScroll"], ensure_ascii=False)))
    add_check(checks, 4, "Main table does not compress or cover the detail panel", lambda: (dragged["tableScroll"]["right"] <= dragged["center"]["right"] + 0.5 and dragged["center"]["right"] <= dragged["detail"]["x"] + 0.5 and layout["independentScroll"]["detailStable"], f"tableRight={dragged['tableScroll']['right']}; centerRight={dragged['center']['right']}; detailX={dragged['detail']['x']}"))
    add_check(checks, 5, "Bottom tab region scrolls independently", lambda: (layout["independentScroll"]["tabScroll"]["independent"] and layout["independentScroll"]["tabScroll"]["top"] > 0, json.dumps(layout["independentScroll"]["tabScroll"], ensure_ascii=False)))
    add_check(checks, 6, "Left-center splitter is draggable", lambda: (dragged["tree"]["width"] > initial["tree"]["width"] + 30, f"{initial['tree']['width']} -> {dragged['tree']['width']}"))
    add_check(checks, 7, "Center-right splitter is draggable", lambda: (dragged["detail"]["width"] > initial["detail"]["width"] + 25, f"{initial['detail']['width']} -> {dragged['detail']['width']}"))
    add_check(checks, 8, "Main-bottom splitter is draggable", lambda: (dragged["main"]["height"] < initial["main"]["height"] - 40, f"{initial['main']['height']} -> {dragged['main']['height']}"))
    add_check(checks, 9, "Layout state persists after refresh", lambda: (layout["storedLayout"] is not None and abs(dragged["tree"]["width"] - reloaded["tree"]["width"]) < 1 and abs(dragged["detail"]["width"] - reloaded["detail"]["width"]) < 1 and abs(dragged["main"]["height"] - reloaded["main"]["height"]) < 1, json.dumps(layout["storedLayout"], ensure_ascii=False)))
    add_check(checks, 10, "Reset default layout clears persisted state", lambda: (layout["storageAfterReset"] is None and abs(reset["tree"]["width"] - 320) < 1 and 339 <= reset["detail"]["width"] <= 421, f"tree={reset['tree']['width']}; detail={reset['detail']['width']}; storage={layout['storageAfterReset']}"))

    add_check(checks, 11, "Work content structured view splits numbered items", lambda: (structured["work"]["rowCount"] >= 2 and structured["work"]["headers"] == ["序号", "内容", "PDF页"], f"rows={structured['work']['rowCount']}; first={structured['work']['firstRows']}"))
    add_check(checks, 12, "Work content raw view is available", lambda: (structured["work"]["rawRecordCount"] > 0 and structured["work"]["rawTextPresent"], f"raw={structured['work']['rawRecordCount']}"))
    add_check(checks, 13, "Quantity rules preserve hierarchy and PDF pages", lambda: (structured["rules"]["rowCount"] > 1 and all(level in structured["rules"]["levels"] for level in ["总则", "分部", "子项", "条款"]) and structured["rules"]["pdfLinks"] == structured["rules"]["rowCount"], json.dumps(structured["rules"], ensure_ascii=False)))
    add_check(checks, 14, "Quantity rule raw view is available", lambda: (structured["rules"]["rawRecordCount"] > 0, f"raw={structured['rules']['rawRecordCount']}"))
    add_check(checks, 15, "Conversion rules are structured one per row", lambda: (structured["conversions"]["rowCount"] > 0 and structured["conversions"]["pdfLinks"] == structured["conversions"]["rowCount"], f"rows={structured['conversions']['rowCount']}"))
    add_check(checks, 16, "Conversion rule raw view is available", lambda: (structured["conversions"]["rawRecordCount"] > 0, f"raw={structured['conversions']['rawRecordCount']}"))
    add_check(checks, 17, "Notes are structured one per row", lambda: (structured["notes"]["rowCount"] > 0 and structured["notes"]["pdfLinks"] == structured["notes"]["rowCount"], f"rows={structured['notes']['rowCount']}"))
    add_check(checks, 18, "Note raw view is available", lambda: (structured["notes"]["rawRecordCount"] > 0, f"raw={structured['notes']['rawRecordCount']}"))

    before_counts = draft_counts()
    before_draft_hash = sha256(DRAFT_DB)
    before_old_hash = sha256(OLD_DRAFT_DB)
    draft_snapshot = OUTPUT / ".review_ux_draft.sqlite.snapshot"
    old_snapshot = OUTPUT / ".review_ux_old.sqlite.snapshot"
    shutil.copy2(DRAFT_DB, draft_snapshot)
    shutil.copy2(OLD_DRAFT_DB, old_snapshot)
    operation: dict[str, Any] = {}
    try:
        with TestClient(app) as client:
            tree_payload = client.get("/api/quota-building/tree").json()
            source_bill = next(item for item in tree_payload["items"] if int(item["original_count"]) > 0)
            source_edge = client.get(f"/api/quota-building/bill/{source_bill['bill_code_9']}/rows").json()["rows"][0]
            targets = [item for item in tree_payload["items"] if item["bill_code_9"] != source_bill["bill_code_9"]][:2]
            ids: list[str] = []
            for action, target in (("copy", targets[0]), ("move", targets[1]), ("exclude", None)):
                response = client.post(
                    "/api/quota-building/draft/action",
                    json={
                        "source_edge_id": source_edge["mapping_edge_id"],
                        "target_bill_code_9": target["bill_code_9"] if target else "",
                        "action_type": action,
                        "operation_reason": "isolated review UX smoke",
                    },
                )
                payload = response.json() if response.status_code == 200 else {}
                operation[action] = response.status_code == 200 and payload.get("draft", {}).get("action_type") == action
                if payload.get("draft", {}).get("draft_id"):
                    ids.append(payload["draft"]["draft_id"])
            restore = client.post(f"/api/quota-building/draft/{ids[0]}/restore", json={}) if ids else None
            operation["restore"] = bool(restore and restore.status_code == 200 and restore.json().get("draft", {}).get("draft_status") == "reverted")
    except Exception as exc:
        operation["exception"] = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.copy2(draft_snapshot, DRAFT_DB)
        shutil.copy2(old_snapshot, OLD_DRAFT_DB)
        draft_snapshot.unlink()
        old_snapshot.unlink()

    add_check(checks, 19, "Copy behavior is unchanged", lambda: (operation.get("copy") is True, json.dumps(operation, ensure_ascii=False)))
    add_check(checks, 20, "Move behavior is unchanged", lambda: (operation.get("move") is True, json.dumps(operation, ensure_ascii=False)))
    add_check(checks, 21, "Exclude behavior is unchanged", lambda: (operation.get("exclude") is True, json.dumps(operation, ensure_ascii=False)))
    add_check(checks, 22, "Restore behavior is unchanged", lambda: (operation.get("restore") is True, json.dumps(operation, ensure_ascii=False)))

    after_counts = draft_counts()
    add_check(checks, 23, "Draft row count and bytes are preserved", lambda: (after_counts["draft"] == before_counts["draft"] and sha256(DRAFT_DB) == before_draft_hash, f"before={before_counts['draft']}; after={after_counts['draft']}; bytes_restored={sha256(DRAFT_DB) == before_draft_hash}"))
    add_check(checks, 24, "Audit row count and existing A1.1 bytes are preserved", lambda: (after_counts["audit"] == before_counts["audit"] and sha256(OLD_DRAFT_DB) == before_old_hash, f"before={before_counts['audit']}; after={after_counts['audit']}; a111_bytes_restored={sha256(OLD_DRAFT_DB) == before_old_hash}"))
    approved = approved_count()
    add_check(checks, 25, "Approved count remains zero", lambda: (approved == 0, f"approved_count={approved}"))
    hashes = hash_status(guard)
    add_check(checks, 26, "Source, Baseline and Mapping hashes are unchanged", lambda: (hashes["source"] and hashes["baseline"] and hashes["mapping"], json.dumps(hashes, ensure_ascii=False)))

    missing_screenshots = [name for name in SCREENSHOTS if not (OUTPUT / name).exists()]
    failures = [item for item in checks if item["pass_fail"] != "pass"]
    if not hashes["source"] or not hashes["baseline"] or not hashes["mapping"] or not hashes["protected_ui"]:
        final_status = "blocked_hash_guard_failed"
    elif any(item["check_id"] in {f"UX-{number:03d}" for number in range(6, 11)} for item in failures):
        final_status = "blocked_layout_splitter_unstable"
    elif any(item["check_id"] in {f"UX-{number:03d}" for number in range(11, 19)} for item in failures):
        final_status = "blocked_structured_view_split_quality_insufficient"
    elif failures or missing_screenshots:
        final_status = "blocked_smoke_failed"
    else:
        final_status = "quota_building_review_ux_enhanced"

    write_csv(OUTPUT / "web_quota_building_review_ux_checks.csv", checks)
    write_csv(OUTPUT / "web_quota_building_layout_state_checks.csv", checks[2:10])
    write_csv(OUTPUT / "web_quota_building_structured_tab_checks.csv", checks[10:18])

    checkpoint = {
        "stage_name": "WEB_QUOTA_BUILDING_REVIEW_UX_ENHANCEMENT_1",
        "completed_at": datetime.now().astimezone().isoformat(),
        "final_status": final_status,
        "check_count": len(checks),
        "pass_count": len(checks) - len(failures),
        "failure_count": len(failures),
        "draft_audit_before": before_counts,
        "draft_audit_after": after_counts,
        "approved_count": approved,
        "hash_status": hashes,
        "missing_screenshots": missing_screenshots,
        "structured_counts": {key: value["rowCount"] for key, value in structured.items()},
        "modified_files": [
            "web_collab_prototype/templates/quota_building_index.html",
            "web_collab_prototype/static/quota_building_style.css",
            "web_collab_prototype/static/quota_building_app.js",
            "web_collab_prototype/smoke_quota_building_review_ux_browser.mjs",
            "web_collab_prototype/smoke_quota_building_review_ux.py",
        ],
    }
    (OUTPUT / "checkpoint_review_ux_enhancement_complete.md").write_text(
        "# Review UX enhancement checkpoint\n\n```json\n" + json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    report = f"""# WEB_QUOTA_BUILDING_REVIEW_UX_ENHANCEMENT_1

- Final status: `{final_status}`
- Tree labels: 16 appendix groups use normalized standard names; appendix codes remain in `data-appendix-code` and tooltips.
- Layout: three constrained splitters control tree width, detail width, and main-table height. State persists under `quotaBuildingReviewLayoutV1`; reset removes the stored value.
- Main table: fixed readable column widths with independent horizontal scrolling and sticky headers.
- Structured rows: work {structured['work']['rowCount']}, quantity rules {structured['rules']['rowCount']}, conversions {structured['conversions']['rowCount']}, notes {structured['notes']['rowCount']}.
- Rule hierarchy observed: {', '.join(structured['rules']['levels'])}.
- Raw views: work/rules/conversions/notes = {structured['work']['rawRecordCount']}/{structured['rules']['rawRecordCount']}/{structured['conversions']['rawRecordCount']}/{structured['notes']['rawRecordCount']} source records.
- Smoke: {len(checks) - len(failures)} passed / {len(failures)} failed.
- Draft/Audit before and after byte restoration: {before_counts['draft']}/{before_counts['audit']} -> {after_counts['draft']}/{after_counts['audit']}.
- Approved count: {approved}.
- Source/Baseline/Mapping/protected-route hash guard: `{str(all(hashes.values())).lower()}`.

No source PDF, parsed/consolidated/GB baseline, Mapping Reference, Draft/Audit semantics, Copy/Move/Exclude/Restore logic, `/quota-a111`, or `/quota-building-legacy` implementation was modified. Text splitting is a conservative client-side presentation transformation; original records remain available unchanged in each raw view.
"""
    (OUTPUT / "stage_web_quota_building_review_ux_enhancement_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(checkpoint, ensure_ascii=False, indent=2))
    if final_status != "quota_building_review_ux_enhanced":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
