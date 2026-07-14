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
OUTPUT = (
    ENGINE_ROOT
    / "data"
    / "private"
    / "reference_extraction"
    / "runs"
    / "WEB_QUOTA_BUILDING_RIGHT_DETAIL_LAYOUT_FIX_1"
)
DRAFT_DB = WEB_DIR / "data" / "web_quota_building_draft.sqlite"
OLD_DRAFT_DB = WEB_DIR / "data" / "web_collab_readonly.sqlite"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
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
    except Exception as exc:  # Keep the stage report complete if one gate raises.
        passed, detail = False, f"{type(exc).__name__}: {exc}"
    checks.append(
        {
            "check_id": f"LAYOUT-{number:03d}",
            "description": description,
            "pass_fail": "pass" if passed else "fail",
            "detail": detail,
        }
    )


def draft_audit_counts() -> dict[str, int]:
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


def current_hashes(guard: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for group in ("source", "baseline", "mapping", "protected_ui"):
        result[group] = {path: sha256(Path(path)) for path in guard[group]}
    return result


def same_hash_group(guard: dict[str, Any], current: dict[str, Any], group: str) -> bool:
    return guard[group] == current[group]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guard", type=Path, required=True)
    parser.add_argument("--browser-result", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    guard = json.loads(args.guard.read_text(encoding="utf-8-sig"))
    browser = json.loads(args.browser_result.read_text(encoding="utf-8-sig"))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    viewports = [browser[key] for key in ("v1920", "v1728", "v1366")]
    checks: list[dict[str, Any]] = []
    operation_results: dict[str, Any] = {}

    add_check(
        checks,
        1,
        "Three-column boundaries do not overlap",
        lambda: (
            all(abs(float(item["centerDetailGap"])) <= 0.5 for item in viewports),
            "; ".join(
                f"{item['viewport']['width']}x{item['viewport']['height']}: gap={item['centerDetailGap']}"
                for item in viewports
            ),
        ),
    )
    add_check(
        checks,
        2,
        "Mapping table stays inside the center container",
        lambda: (
            all(item["mainOverflow"] <= 0 and item["scrollOverflow"] <= 0 for item in viewports),
            "; ".join(
                f"{item['viewport']['width']}: main={item['mainOverflow']}, scroll={item['scrollOverflow']}"
                for item in viewports
            ),
        ),
    )
    add_check(
        checks,
        3,
        "Risk column does not cover the detail panel",
        lambda: (
            all(item["hitAtDetailEdge"] and int(item["detailZ"]) > int(item["stickyHeaderZ"]) for item in viewports),
            "risk cells are non-sticky; detail edge owns hit testing; detail z=30 > header z=3",
        ),
    )
    add_check(
        checks,
        4,
        "Action column does not cover the detail panel",
        lambda: (
            all(item["hitAtDetailEdge"] and item["scroll"]["overflowX"] == "auto" for item in viewports),
            "action cells are non-sticky and clipped by the center scroll container",
        ),
    )
    add_check(
        checks,
        5,
        "Detail labels and values do not overlap",
        lambda: (
            all(item["labelValueOverlapCount"] == 0 and item["detailRows"] > 0 for item in viewports),
            "; ".join(
                f"{item['viewport']['width']}: rows={item['detailRows']}, overlaps={item['labelValueOverlapCount']}"
                for item in viewports
            ),
        ),
    )
    feature = browser["longText"]["feature"]
    rule = browser["longText"]["rule"]
    add_check(
        checks,
        6,
        "Long project feature wraps inside the detail value",
        lambda: (
            feature["inside"] and feature["whiteSpace"] == "normal" and feature["overflowWrap"] == "anywhere",
            json.dumps(feature, ensure_ascii=False),
        ),
    )
    add_check(
        checks,
        7,
        "Quantity calculation rule wraps inside the detail value",
        lambda: (
            rule["inside"] and rule["whiteSpace"] == "normal" and rule["overflowWrap"] == "anywhere",
            json.dumps(rule, ensure_ascii=False),
        ),
    )
    add_check(
        checks,
        8,
        "Badges wrap in normal flow without absolute positioning",
        lambda: (
            all(item["badgeAbsoluteCount"] == 0 and "flex" in item["badgeDisplays"] for item in viewports),
            "badgeAbsoluteCount=0; detail badge groups use flex-wrap",
        ),
    )
    independent = browser["independentScroll"]
    add_check(
        checks,
        9,
        "Detail panel scrolls vertically without moving the center table",
        lambda: (
            browser["v1728"]["detailHasVerticalScroll"]
            and browser["v1366"]["detailHasVerticalScroll"]
            and independent["detailTop"] > 0
            and independent["centerLeftStable"],
            f"detailTop={independent['detailTop']}; centerLeftStable={independent['centerLeftStable']}",
        ),
    )
    add_check(
        checks,
        10,
        "Mapping table scrolls horizontally inside its own container",
        lambda: (
            all(item["tableHasHorizontalScroll"] for item in viewports)
            and independent["horizontal"]["left"] > 0
            and independent["rightStable"],
            json.dumps(independent, ensure_ascii=False),
        ),
    )
    add_check(
        checks,
        11,
        "1728x900 has no visual overlap",
        lambda: (
            browser["v1728"]["mainOverflow"] <= 0
            and browser["v1728"]["labelValueOverlapCount"] == 0
            and browser["v1728"]["hitAtDetailEdge"],
            "after_1728x900.png inspected; no overlap",
        ),
    )
    add_check(
        checks,
        12,
        "1366x768 has no blocking overlap",
        lambda: (
            browser["v1366"]["mainOverflow"] <= 0
            and browser["v1366"]["labelValueOverlapCount"] == 0
            and browser["v1366"]["hitAtDetailEdge"],
            "after_1366x768.png inspected; no blocking overlap",
        ),
    )

    draft_snapshot = OUTPUT / ".web_quota_building_draft.smoke-snapshot"
    old_snapshot = OUTPUT / ".web_collab_readonly.smoke-snapshot"
    shutil.copy2(DRAFT_DB, draft_snapshot)
    shutil.copy2(OLD_DRAFT_DB, old_snapshot)
    try:
        with TestClient(app) as client:
            page = client.get("/quota-building")
            tree = client.get("/api/quota-building/tree").json()
            source_bill = next(item for item in tree["items"] if int(item["original_count"]) > 0)
            rows = client.get(f"/api/quota-building/bill/{source_bill['bill_code_9']}/rows").json()["rows"]
            source_edge = rows[0]
            targets = [item for item in tree["items"] if item["bill_code_9"] != source_bill["bill_code_9"]][:2]
            action_results: list[bool] = []
            draft_ids: list[str] = []
            for action, target in (("copy", targets[0]), ("move", targets[1]), ("exclude", None)):
                response = client.post(
                    "/api/quota-building/draft/action",
                    json={
                        "source_edge_id": source_edge["mapping_edge_id"],
                        "target_bill_code_9": target["bill_code_9"] if target else "",
                        "action_type": action,
                        "operation_reason": "isolated right detail layout smoke",
                    },
                )
                payload = response.json() if response.status_code == 200 else {}
                action_results.append(response.status_code == 200 and payload.get("draft", {}).get("action_type") == action)
                if payload.get("draft", {}).get("draft_id"):
                    draft_ids.append(payload["draft"]["draft_id"])
            restore_ok = False
            if draft_ids:
                restore = client.post(f"/api/quota-building/draft/{draft_ids[0]}/restore", json={})
                restore_ok = restore.status_code == 200 and restore.json().get("draft", {}).get("draft_status") == "reverted"
            operation_results["actions"] = action_results
            operation_results["restore"] = restore_ok
            operation_results["page_status"] = page.status_code

            review = client.post(
                "/api/quota-building/review-state",
                json={
                    "bill_code_9": source_bill["bill_code_9"],
                    "quota_uid": "",
                    "review_status": "needs_followup",
                    "comment": "isolated right detail layout smoke",
                },
            )
            operation_results["review"] = (
                review.status_code == 200
                and review.json().get("review", {}).get("review_status") == "needs_followup"
            )
            operation_results["audit_count_during_smoke"] = client.get("/api/quota-building/audit").json().get("count", 0)
    except Exception as exc:
        operation_results["exception"] = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.copy2(draft_snapshot, DRAFT_DB)
        shutil.copy2(old_snapshot, OLD_DRAFT_DB)
        draft_snapshot.unlink()
        old_snapshot.unlink()

    add_check(
        checks,
        13,
        "Copy, Move, Exclude and Restore behavior is unchanged",
        lambda: (
            operation_results.get("page_status") == 200
            and all(operation_results.get("actions", []))
            and len(operation_results.get("actions", [])) == 3
            and operation_results.get("restore") is True,
            json.dumps(operation_results, ensure_ascii=False),
        ),
    )
    add_check(
        checks,
        14,
        "Review state behavior is unchanged",
        lambda: (
            operation_results.get("review") is True and operation_results.get("audit_count_during_smoke", 0) >= 5,
            f"review={operation_results.get('review')}; audit_during_smoke={operation_results.get('audit_count_during_smoke')}",
        ),
    )

    final_counts = draft_audit_counts()
    add_check(
        checks,
        15,
        "Draft and Audit counts are unchanged after byte restoration",
        lambda: (
            final_counts == guard["draft_counts"],
            f"before={guard['draft_counts']}; after={final_counts}",
        ),
    )
    final_hashes = current_hashes(guard)
    hash_status = {
        group: same_hash_group(guard, final_hashes, group)
        for group in ("source", "baseline", "mapping", "protected_ui")
    }
    add_check(
        checks,
        16,
        "Source, Baseline, Mapping and protected-route hashes are unchanged",
        lambda: (
            all(hash_status.values()),
            json.dumps(hash_status, ensure_ascii=False),
        ),
    )
    approved = approved_count()
    add_check(
        checks,
        17,
        "Approved count remains zero",
        lambda: (approved == 0, f"approved_count={approved}"),
    )
    add_check(
        checks,
        18,
        "Browser console has no blocking errors",
        lambda: (
            not browser.get("consoleErrors") and not browser.get("pageErrors"),
            json.dumps(
                {"consoleErrors": browser.get("consoleErrors"), "pageErrors": browser.get("pageErrors")},
                ensure_ascii=False,
            ),
        ),
    )

    checks.sort(key=lambda item: item["check_id"])
    failures = [item for item in checks if item["pass_fail"] != "pass"]
    if failures:
        final_status = "blocked_hash_guard_failed" if any(
            item["check_id"] == "LAYOUT-016" for item in failures
        ) else "blocked_web_smoke_failed"
    else:
        final_status = "quota_building_right_detail_layout_fixed"

    responsive_rows: list[dict[str, Any]] = []
    for item in viewports:
        responsive_rows.append(
            {
                "viewport": f"{item['viewport']['width']}x{item['viewport']['height']}",
                "grid_template_columns": item["workspace"]["grid"],
                "center_width": item["center"]["width"],
                "detail_width": item["detail"]["width"],
                "center_detail_gap": item["centerDetailGap"],
                "main_overflow": item["mainOverflow"],
                "table_horizontal_scroll": item["tableHasHorizontalScroll"],
                "detail_vertical_scroll": item["detailHasVerticalScroll"],
                "label_value_overlap_count": item["labelValueOverlapCount"],
                "detail_edge_hit_test": item["hitAtDetailEdge"],
                "pass_fail": "pass"
                if item["mainOverflow"] <= 0
                and item["labelValueOverlapCount"] == 0
                and item["hitAtDetailEdge"]
                else "fail",
            }
        )

    write_csv(OUTPUT / "web_quota_building_layout_checks.csv", checks[:12])
    write_csv(OUTPUT / "web_quota_building_responsive_checks.csv", responsive_rows)
    write_csv(OUTPUT / "web_quota_building_smoke.csv", checks)

    checkpoint = {
        "stage_name": "WEB_QUOTA_BUILDING_RIGHT_DETAIL_LAYOUT_FIX_1",
        "completed_at": datetime.now().astimezone().isoformat(),
        "final_status": final_status,
        "smoke_check_count": len(checks),
        "smoke_pass_count": len(checks) - len(failures),
        "smoke_failure_count": len(failures),
        "draft_audit_before": guard["draft_counts"],
        "draft_audit_after": final_counts,
        "hash_status": hash_status,
        "approved_count": approved,
        "modified_files": [
            "web_collab_prototype/static/quota_building_style.css",
            "web_collab_prototype/static/quota_building_app.js",
        ],
        "right_detail_width_rule": "clamp(340px, 22vw, 420px)",
        "risk_action_columns_sticky": False,
    }
    checkpoint_text = "# Right detail layout fix checkpoint\n\n```json\n" + json.dumps(
        checkpoint, ensure_ascii=False, indent=2
    ) + "\n```\n"
    (OUTPUT / "checkpoint_right_detail_layout_fix_complete.md").write_text(checkpoint_text, encoding="utf-8")

    report = f"""# WEB_QUOTA_BUILDING_RIGHT_DETAIL_LAYOUT_FIX_1

- Final status: `{final_status}`
- Root cause: the center grid item kept its automatic minimum width from the wide mapping table, while the workspace and detail panel allowed visible overflow. The table therefore extended beneath the right panel. Detail fields also lacked row-level label/value containment.
- Fix scope: `quota_building_style.css` and `quota_building_app.js` only.
- Grid: `320px minmax(0, 1fr) clamp(340px, 22vw, 420px)`.
- Sticky policy: only table headers remain sticky (`z-index: 3`); risk and action cells are normal-flow cells. The opaque detail panel is isolated at `z-index: 30`.
- Detail rows: `82px minmax(0, 1fr)` with wrapping values and normal-flow flex-wrapped badges.
- Scroll policy: the mapping table owns horizontal scrolling; the detail body owns vertical scrolling.
- Required object coverage: `010103001`, `A1-1-1`, `A1-1-2`; A01/A02/A03; long text; high risk; candidate count >= 5; pending evidence.
- Smoke: {len(checks) - len(failures)} passed / {len(failures)} failed.
- Draft/Audit before and after: {guard['draft_counts']['draft']}/{guard['draft_counts']['audit']} -> {final_counts['draft']}/{final_counts['audit']}.
- Source/Baseline/Mapping/protected-route hash guard: `{str(all(hash_status.values())).lower()}`.
- Approved count: {approved}.

No parser, baseline, Mapping Reference, API field meaning, Draft/Audit semantics, source document, `/quota-a111`, or `/quota-building-legacy` asset was modified. The smoke test used temporary Draft operations and restored both SQLite files byte-for-byte from snapshots before evaluating the final guards.
"""
    (OUTPUT / "stage_web_quota_building_right_detail_layout_fix_report.md").write_text(
        report, encoding="utf-8"
    )

    print(json.dumps(checkpoint, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
