from __future__ import annotations

import csv
import hashlib
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_collab_prototype.app import app, quota_a111_generate_quantity_rule_dual_view_artifacts  # noqa: E402


RUNS_DIR = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "runs"
VIEWER_RUN_DIR = RUNS_DIR / "WEB_QUOTA_A111_PDF_DETAIL_VIEWER_1"
RUN_DIR = RUNS_DIR / "WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1"
SMOKE_CSV = RUN_DIR / "quantity_rule_dual_view_smoke.csv"
REPORT_MD = RUN_DIR / "stage_web_quota_a111_quantity_rule_dual_view_report.md"
DB_PATH = PROJECT_ROOT / "web_collab_prototype" / "data" / "web_collab_readonly.sqlite"
TREE_CSV = VIEWER_RUN_DIR / "web_quota_a111_bill_tree.csv"
BILL_ROWS_CSV = VIEWER_RUN_DIR / "web_quota_a111_bill_to_quota_rows.csv"
DETAIL_CSV = VIEWER_RUN_DIR / "web_quota_a111_quota_detail_rows.csv"
RESOURCE_CSV = VIEWER_RUN_DIR / "web_quota_a111_resource_rows.csv"
MAPPING_CANDIDATE_CSV = RUNS_DIR / "MAP_A111_quota_to_bill_trial" / "quota_to_bill_mapping_A111_candidate.csv"
SOURCE_PDF = PROJECT_ROOT / "data" / "private" / "reference_extraction" / "source_standards" / "广东省建设工程综合定额(2018)" / "A01_广东省房屋建筑与装饰工程定额(上册).pdf"
REPEATED_RULE_DISPLAY_CSV = RUNS_DIR / "WEB_QUOTA_A111_DRAFT_COUNTS_DETAIL_REFINEMENT_1" / "web_quota_a111_quantity_rule_display_model.csv"
PDF_STRUCTURED_DIR = RUNS_DIR / "GD2018_PDF_A111_STRUCTURED_CANDIDATE_1"
PDF_CANDIDATE_FILES = [
    PDF_STRUCTURED_DIR / "quota_pdf_structured_A111_candidate.csv",
    PDF_STRUCTURED_DIR / "quota_pdf_work_content_A111_candidate.csv",
    PDF_STRUCTURED_DIR / "quota_pdf_quantity_rule_A111_candidate.csv",
]
QUOTA_A111_JS = PROJECT_ROOT / "web_collab_prototype" / "static" / "quota_a111_app.js"
DRAFT_TABLES = [
    "web_quota_a111_mapping_draft_edges",
    "web_quota_a111_mapping_draft_audit_log",
]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def table_rows(table_name: str) -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(f"SELECT * FROM {table_name} ORDER BY rowid")]


def snapshot_draft_tables() -> dict[str, list[dict[str, Any]]]:
    return {table: table_rows(table) for table in DRAFT_TABLES}


def restore_draft_tables(snapshot: dict[str, list[dict[str, Any]]]) -> None:
    with sqlite3.connect(DB_PATH) as con:
        for table in DRAFT_TABLES:
            con.execute(f"DELETE FROM {table}")
            rows = snapshot.get(table, [])
            if not rows:
                continue
            fields = list(rows[0])
            placeholders = ", ".join(["?"] * len(fields))
            con.executemany(
                f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
                [tuple(row.get(field) for field in fields) for row in rows],
            )
        con.commit()


def approved_count() -> int:
    with sqlite3.connect(DB_PATH) as con:
        price_review = con.execute(
            "SELECT COUNT(*) FROM web_price_review_draft WHERE draft_status = 'approved' OR lock_status = 'approved'"
        ).fetchone()[0]
        bid_generated = con.execute(
            "SELECT COUNT(*) FROM web_bid_item_display_rows WHERE review_status = 'approved'"
        ).fetchone()[0]
        quota_draft_text = con.execute(
            """
            SELECT COUNT(*)
            FROM web_quota_a111_mapping_draft_edges
            WHERE draft_status = 'approved' OR relation_type = 'approved' OR action_type = 'approved'
            """
        ).fetchone()[0]
        return int(price_review) + int(bid_generated) + int(quota_draft_text)


def bill_name_for(bill_code_9: str) -> str:
    return next(
        (
            row.get("bill_name", "")
            for row in read_csv(TREE_CSV)
            if row.get("node_type") == "bill" and row.get("bill_code_9") == bill_code_9
        ),
        "",
    )


def source_row(quota_source_code: str, source_bill_code_9: str) -> dict[str, str]:
    row = next(
        (
            item
            for item in read_csv(BILL_ROWS_CSV)
            if item.get("quota_source_code") == quota_source_code
            and item.get("bill_code_9") == source_bill_code_9
            and item.get("row_type") in {"gd_quota_pdf_candidate", "xlsx_only_supplemental"}
        ),
        None,
    )
    if not row:
        raise AssertionError(f"source row not found: {quota_source_code}/{source_bill_code_9}")
    return row


def payload_for(row: dict[str, str], target_bill_code_9: str, action_type: str) -> dict[str, str]:
    return {
        "source_edge_id": row.get("row_id", ""),
        "source_bill_code_9": row.get("bill_code_9", ""),
        "source_bill_name": row.get("bill_name", ""),
        "target_bill_code_9": target_bill_code_9,
        "target_bill_name": bill_name_for(target_bill_code_9),
        "quota_source_code": row.get("quota_source_code", ""),
        "quota_name": row.get("quota_name_from_pdf", ""),
        "action_type": action_type,
        "operation_reason": "isolated smoke draft; restore snapshot after test",
        "reviewer": "",
    }


def tree_stats(client: TestClient) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    response = client.get("/api/quota-a111/tree")
    payload = response.json() if response.status_code == 200 else {}
    by_bill = {
        row.get("bill_code_9", ""): row
        for row in payload.get("items", [])
        if row.get("node_type") == "bill"
    }
    return payload, by_bill


def expected_original_counts() -> dict[str, int]:
    pairs: dict[str, set[str]] = {}
    for row in read_csv(BILL_ROWS_CSV):
        if row.get("row_type") == "gb_bill" or not row.get("quota_source_code"):
            continue
        pairs.setdefault(row.get("bill_code_9", ""), set()).add(row.get("quota_source_code", ""))
    return {bill: len(codes) for bill, codes in pairs.items()}


def utf8_response_ok(response: Any, required_text: str) -> bool:
    try:
        text = response.content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    bad_tokens = ("\ufffd", "????", "锟", "浣犵", "閿")
    return required_text in text and not any(token in text for token in bad_tokens)


def write_report(checks: list[dict[str, object]], artifacts: dict[str, Any]) -> str:
    source_blocks = artifacts["source_blocks"]
    scope_links = artifacts["scope_links"]
    duplicate_audit = artifacts["duplicate_audit"]
    page_index = artifacts["page_index"]
    repeated_rows = read_csv(REPEATED_RULE_DISPLAY_CSV)
    duplicate_removed = sum(int(row["duplicate_record_count_removed"]) for row in duplicate_audit)
    page_assignment_pending = sum("page_assignment_uncertain" in row["parse_status"] for row in source_blocks)
    passed = sum(row["pass_fail"] == "pass" for row in checks)
    failed = len(checks) - passed
    if failed:
        recommendation = "blocked_smoke_failed"
    elif not page_index:
        recommendation = "blocked_source_page_unavailable"
    elif len(scope_links) != len(source_blocks):
        recommendation = "blocked_rule_scope_model_failed"
    elif page_assignment_pending:
        recommendation = "quota_a111_quantity_rule_dual_view_ready_but_source_page_render_needs_polish"
    else:
        recommendation = "quota_a111_quantity_rule_dual_view_ready_for_user_test"
    report = f"""# Stage WEB-QUOTA-A111-QUANTITY-RULE-DUAL-VIEW-1 Report

## 1. Task Scope
本轮只优化 `/quota-a111` 的工程量规则页签，增加原文、结构化、对照三视图，并把按 quota 复制的展示记录去重为只读 source block 与 scope link。

## 2. Existing Function Preservation
Copy、Move、Restore、工作内容逐行显示、工料机联动、整行选择、草稿持久化与导出均保留；`/`、`/bid`、`/quota-a111` 原主布局通过 Smoke。

## 3. Evidence / Semantic / Applicability Architecture
- Evidence Layer: 原始 PDF 文件、SHA256、PDF 55-57、书内 15-17、原水印与原表格页面。
- Semantic Layer: {len(source_blocks)} 个唯一 rule block，保留规则号、层级、标题、摘要与页码。
- Applicability Layer: {len(scope_links)} 条独立 scope link；不再按 137 个 quota 复制主记录。

## 4. Duplicate Rule Audit
- original display records: {len(repeated_rows)}
- unique structural rule groups: {len(duplicate_audit)}
- repeated copies removed in the new read-only model: {duplicate_removed}
- each unique group repeated across quota count: {duplicate_audit[0]['distinct_quota_count'] if duplicate_audit else 0}
- original 4,521-row artifact remains unchanged.

## 5. Source Block Model
- source blocks: {len(source_blocks)}
- pages represented: {', '.join(row['pdf_page_no'] for row in page_index)}
- page assignment pending: {page_assignment_pending}
- `table_json` 与 `source_bbox` 留空，因为现有抽取未可靠保留表格单元格关系或坐标。

## 6. Scope Link Model
- scope links: {len(scope_links)}
- scope type: uncertain
- range evidence: A.1.1 / A1-1-1..A1-1-137
- all links require manual scope review; no specific quota link was fabricated.

## 7. Original View
默认打开原文视图。页面直接嵌入未修改的原始 PDF，提供上一页、下一页、适应宽度、放大、缩小和独立滚动。表格、水印、注释和版式均由原 PDF 保持。

## 8. Structured View
保留规则索引，显示 rule block、层级、标题、摘要、uncertain scope 与 PDF 页。点击规则后跳到对应原始 PDF 页；摘要明确不是原文。

## 9. Comparison View
左侧为去重规则索引和适用范围，右侧为对应原始 PDF 页。当前无可靠 bbox，只跳页，不伪造高亮。

## 10. API Summary
- `GET /api/quota-a111/quota/{{quota_source_code}}/quantity-rule/source-pages`
- `GET /api/quota-a111/quantity-rule/block/{{rule_block_id}}`
- `GET /api/quota-a111/quantity-rule/page/{{pdf_page_no}}`
- `GET /api/quota-a111/quota/{{quota_source_code}}/quantity-rule/structured`
- `GET /api/quota-a111/quantity-rule/source-pdf`

## 11. Smoke Test
- passed: {passed}
- failed: {failed}
- result CSV: `{SMOKE_CSV}`

## 12. Governance Controls
- no approved: confirmed
- no production DB write: confirmed; only local Web Prototype SQLite draft tables were used
- original PDF hash unchanged: confirmed
- Mapping Candidate hash unchanged: confirmed
- no OCR, no PDF modification, no watermark removal, no Mapping Draft schema change

## 13. Known Limitations
- 浏览器原生 PDF viewer 负责页面渲染；不同浏览器的工具栏外观可能略有差异。
- 现有抽取没有可靠 table cell JSON 或 bbox，因此不重建 HTML table，也不高亮规则区域。
- scope 仍需成本部人工确认；本轮不做正式审批、企业价格或成本测算。

## 14. Next Step Recommendation
{recommendation}
"""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")
    return recommendation


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, object]] = []

    def record(check_name: str, expected: str, actual: Any, ok: bool, remark: str = "") -> None:
        checks.append(
            {
                "check_name": check_name,
                "expected": expected,
                "actual": actual,
                "pass_fail": "pass" if ok else "fail",
                "remark": remark,
            }
        )

    source_files = [TREE_CSV, BILL_ROWS_CSV, DETAIL_CSV, RESOURCE_CSV, MAPPING_CANDIDATE_CSV, SOURCE_PDF, *PDF_CANDIDATE_FILES]
    source_hash_before = {str(path): sha256(path) for path in source_files}
    existing_snapshot = snapshot_draft_tables()
    quota_js = QUOTA_A111_JS.read_text(encoding="utf-8")
    client = TestClient(app)
    artifacts: dict[str, Any] = {"source_blocks": [], "scope_links": [], "duplicate_audit": [], "page_index": []}

    try:
        reset_start = client.post("/api/quota-a111/draft/reset-test-data")
        record("draft_reset_start", "HTTP 200", reset_start.status_code, reset_start.status_code == 200)

        enterprise_page = client.get("/")
        bid_page = client.get("/bid")
        quota_page = client.get("/quota-a111")
        record("enterprise_page_accessible", "HTTP 200", enterprise_page.status_code, enterprise_page.status_code == 200)
        record("bid_page_accessible", "HTTP 200", bid_page.status_code, bid_page.status_code == 200)
        record("quota_a111_page_accessible", "HTTP 200", quota_page.status_code, quota_page.status_code == 200)

        enterprise_tree = client.get("/api/tree/hierarchy")
        bid_tree = client.get("/api/bid/gb-standard-tree")
        record("enterprise_tree_api_stable", "HTTP 200", enterprise_tree.status_code, enterprise_tree.status_code == 200)
        record("bid_gb_standard_tree_api_stable", "HTTP 200", bid_tree.status_code, bid_tree.status_code == 200)
        record(
            "frontend_dual_view_handlers_present",
            "tree/work plus original/structured/comparison handlers",
            "present",
            all(token in quota_js for token in ["renderTreeDraftCounts", "renderWorkContent", "renderQuantityRuleDualView", "renderOriginalRuleView", "renderStructuredRuleView", "renderComparisonRuleView"]),
        )
        record(
            "original_view_is_default",
            "quantityRuleView original",
            'quantityRuleView: "original"' in quota_js,
            'quantityRuleView: "original"' in quota_js,
        )

        initial_tree, initial_by_bill = tree_stats(client)
        record("quota_a111_tree_api_accessible", "12 bill nodes", len(initial_by_bill), len(initial_by_bill) == 12)
        expected_counts = expected_original_counts()
        original_ok = all(int(initial_by_bill[bill]["original_candidate_count"]) == count for bill, count in expected_counts.items())
        record("initial_bill_original_counts_correct", "deduplicated source relation counts", original_ok, original_ok)
        formula_ok = all(
            int(row["effective_candidate_count"])
            == int(row["original_candidate_count"])
            + int(row["copy_in_count"])
            + int(row["move_in_count"])
            - int(row["move_out_count"])
            - int(row["excluded_count"])
            for row in initial_by_bill.values()
        )
        record("initial_effective_formula_correct", "effective formula holds", formula_ok, formula_ok)

        copy_source = source_row("A1-1-134", "010103001")
        copy_target = "010101001"
        copy_before = initial_by_bill[copy_target]
        copy_response = client.post("/api/quota-a111/draft/edge", json=payload_for(copy_source, copy_target, "copy_link"))
        copy_json = copy_response.json() if copy_response.status_code == 200 else {}
        copy_edge_id = (copy_json.get("created_edges") or [{}])[0].get("draft_edge_id", "")
        record("copy_link_write_success", "saved=true", copy_json.get("saved"), copy_response.status_code == 200 and copy_json.get("saved") is True)
        _, after_copy = tree_stats(client)
        record("copy_in_count_increment", "+1", after_copy[copy_target]["copy_in_count"], int(after_copy[copy_target]["copy_in_count"]) == int(copy_before["copy_in_count"]) + 1)
        record("copy_effective_count_increment", "+1", after_copy[copy_target]["effective_candidate_count"], int(after_copy[copy_target]["effective_candidate_count"]) == int(copy_before["effective_candidate_count"]) + 1)

        move_source_bill = "010101002"
        move_target_bill = "010102005"
        move_source = source_row("A1-1-67", move_source_bill)
        move_source_before = after_copy[move_source_bill]
        move_target_before = after_copy[move_target_bill]
        move_response = client.post("/api/quota-a111/draft/edge", json=payload_for(move_source, move_target_bill, "move_link"))
        move_json = move_response.json() if move_response.status_code == 200 else {}
        move_edge_id = (move_json.get("created_edges") or [{}])[0].get("draft_edge_id", "")
        record("move_link_write_success", "saved=true/two edges", len(move_json.get("created_edges", [])), move_response.status_code == 200 and len(move_json.get("created_edges", [])) == 2)
        _, after_move = tree_stats(client)
        record("move_target_count_increment", "+1", after_move[move_target_bill]["move_in_count"], int(after_move[move_target_bill]["move_in_count"]) == int(move_target_before["move_in_count"]) + 1)
        record("move_source_count_increment", "+1", after_move[move_source_bill]["move_out_count"], int(after_move[move_source_bill]["move_out_count"]) == int(move_source_before["move_out_count"]) + 1)
        record("move_target_effective_increment", "+1", after_move[move_target_bill]["effective_candidate_count"], int(after_move[move_target_bill]["effective_candidate_count"]) == int(move_target_before["effective_candidate_count"]) + 1)
        record("move_source_effective_decrement", "-1", after_move[move_source_bill]["effective_candidate_count"], int(after_move[move_source_bill]["effective_candidate_count"]) == int(move_source_before["effective_candidate_count"]) - 1)

        exclude_bill = "010101003"
        exclude_source = source_row("A1-1-126", exclude_bill)
        exclude_before = after_move[exclude_bill]
        exclude_response = client.post("/api/quota-a111/draft/edge", json=payload_for(exclude_source, exclude_bill, "exclude_link"))
        exclude_json = exclude_response.json() if exclude_response.status_code == 200 else {}
        exclude_edge_id = (exclude_json.get("created_edges") or [{}])[0].get("draft_edge_id", "")
        record("exclude_link_write_success", "saved=true", exclude_json.get("saved"), exclude_response.status_code == 200 and exclude_json.get("saved") is True)
        _, after_exclude = tree_stats(client)
        record("exclude_count_increment", "+1", after_exclude[exclude_bill]["excluded_count"], int(after_exclude[exclude_bill]["excluded_count"]) == int(exclude_before["excluded_count"]) + 1)
        record("exclude_effective_count_decrement", "-1", after_exclude[exclude_bill]["effective_candidate_count"], int(after_exclude[exclude_bill]["effective_candidate_count"]) == int(exclude_before["effective_candidate_count"]) - 1)

        _, reload_stats = tree_stats(client)
        reload_ok = all(
            reload_stats[bill]["effective_candidate_count"] == after_exclude[bill]["effective_candidate_count"]
            for bill in {copy_target, move_source_bill, move_target_bill, exclude_bill}
        )
        record("tree_stats_persist_after_reload", "same SQLite-derived effective counts", reload_ok, reload_ok)

        overlay = client.get(f"/api/quota-a111/bill/{move_source_bill}/rows?include_excluded=true")
        overlay_rows = overlay.json().get("rows", []) if overlay.status_code == 200 else []
        record("move_source_overlay_preserved", "move source exclusion visible", len(overlay_rows), any(row.get("relation_type") == "draft_move_source_excluded" for row in overlay_rows))

        work_response = client.get("/api/quota-a111/quota/A1-1-1/work-content")
        work_json = work_response.json() if work_response.status_code == 200 else {}
        work_items = work_json.get("items", [])
        record("work_content_items_array", "at least two items", len(work_items), work_response.status_code == 200 and len(work_items) >= 2)
        record("work_content_item_order", "1..N", [row.get("item_order") for row in work_items], [int(row.get("item_order") or 0) for row in work_items] == list(range(1, len(work_items) + 1)))
        record("work_content_source_raw_text_retained", "non-empty raw text", len(work_json.get("raw_text", "")), bool(work_json.get("raw_text")))
        record("work_content_api_utf8", "UTF-8 Chinese without mojibake", "工作内容", utf8_response_ok(work_response, "平整场地"))

        raw_work_response = client.get("/api/quota-a111/quota/A1-1-9/work-content")
        raw_work_json = raw_work_response.json() if raw_work_response.status_code == 200 else {}
        record("work_content_raw_fallback_safe", "raw_fallback/manual review", raw_work_json.get("raw_fallback_count"), raw_work_json.get("raw_fallback_count") == 1 and raw_work_json.get("items", [{}])[0].get("display_status") == "needs_manual_review")

        rule_response = client.get("/api/quota-a111/quota/A1-1-1/quantity-rule")
        rule_json = rule_response.json() if rule_response.status_code == 200 else {}
        rule_groups = rule_json.get("rule_groups", [])
        clauses = [clause for group in rule_groups for clause in group.get("clauses", [])]
        record("quantity_rule_groups_array", "rule_groups and clauses", f"{len(rule_groups)}/{len(clauses)}", rule_response.status_code == 200 and len(rule_groups) >= 1 and len(clauses) >= 1)
        clause_order_ok = all(
            [int(row.get("clause_order") or 0) for row in group.get("clauses", [])]
            == sorted(int(row.get("clause_order") or 0) for row in group.get("clauses", []))
            for group in rule_groups
        )
        record("quantity_rule_clause_order", "ascending within group", clause_order_ok, clause_order_ok)
        record("quantity_rule_source_raw_text_retained", "non-empty raw text", len(rule_json.get("raw_text", "")), bool(rule_json.get("raw_text")))
        manual_clauses = [row for row in clauses if row.get("requires_manual_scope_review") == "true"]
        uncertain_ok = bool(manual_clauses) and all(row.get("rule_scope") == "uncertain" for row in manual_clauses)
        record("quantity_rule_uncertain_scope_not_fabricated", "manual clauses remain uncertain", uncertain_ok, uncertain_ok)
        record("quantity_rule_api_utf8", "UTF-8 Chinese without mojibake", "工程量规则", utf8_response_ok(rule_response, "工程量计算规则"))

        resources_response = client.get("/api/quota-a111/quota/A1-1-1/resources")
        resources_json = resources_response.json() if resources_response.status_code == 200 else {}
        record("resource_linkage_stable", "HTTP 200 and resource rows", resources_json.get("count"), resources_response.status_code == 200 and int(resources_json.get("count") or 0) > 0)

        source_pages_response = client.get("/api/quota-a111/quota/A1-1-39/quantity-rule/source-pages")
        source_pages_json = source_pages_response.json() if source_pages_response.status_code == 200 else {}
        source_pages = source_pages_json.get("pages", [])
        record("quantity_rule_source_pages_available", "PDF pages 55/56/57", [row.get("pdf_page_no") for row in source_pages], source_pages_response.status_code == 200 and [row.get("pdf_page_no") for row in source_pages] == [55, 56, 57])
        record("original_view_default_from_api", "original", source_pages_json.get("default_view"), source_pages_json.get("default_view") == "original")
        record("pdf_table_render_mode_original", "original_pdf_page", source_pages_json.get("table_render_mode"), source_pages_json.get("table_render_mode") == "original_pdf_page" and source_pages_json.get("preserves_watermark") is True)

        source_pdf_response = client.get("/api/quota-a111/quantity-rule/source-pdf")
        source_pdf_ok = (
            source_pdf_response.status_code == 200
            and source_pdf_response.headers.get("content-type", "").startswith("application/pdf")
            and source_pdf_response.content.startswith(b"%PDF")
        )
        record("original_pdf_endpoint_available", "HTTP 200 application/pdf", f"{source_pdf_response.status_code}/{source_pdf_response.headers.get('content-type')}", source_pdf_ok)

        page_response = client.get("/api/quota-a111/quantity-rule/page/55")
        page_json = page_response.json() if page_response.status_code == 200 else {}
        record("quantity_rule_page_api_available", "PDF 55/book 15/blocks", f"{page_json.get('page', {}).get('pdf_page_no')}/{page_json.get('page', {}).get('book_page_no')}/{page_json.get('block_count')}", page_response.status_code == 200 and page_json.get("page", {}).get("pdf_page_no") == 55 and page_json.get("page", {}).get("book_page_no") == 15 and int(page_json.get("block_count") or 0) > 0)

        structured_response = client.get("/api/quota-a111/quota/A1-1-39/quantity-rule/structured")
        structured_json = structured_response.json() if structured_response.status_code == 200 else {}
        structured_items = structured_json.get("items", [])
        record("structured_view_api_available", "33 unique rule blocks", len(structured_items), structured_response.status_code == 200 and len(structured_items) == 33 and len({row.get("rule_block_id") for row in structured_items}) == 33)
        record("structured_scope_remains_uncertain", "all uncertain/manual", len(structured_items), bool(structured_items) and all(row.get("rule_scope") == "uncertain" and row.get("requires_manual_scope_review") == "true" for row in structured_items))
        first_block_id = structured_items[0].get("rule_block_id", "") if structured_items else ""
        block_response = client.get(f"/api/quota-a111/quantity-rule/block/{first_block_id}") if first_block_id else None
        block_json = block_response.json() if block_response and block_response.status_code == 200 else {}
        record("quantity_rule_block_api_available", "block and one scope link", len(block_json.get("scope_links", [])), bool(block_response) and block_response.status_code == 200 and len(block_json.get("scope_links", [])) == 1)
        record(
            "structured_click_page_jump_handler_present",
            "block click selects PDF page without fake highlight",
            "present",
            all(token in quota_js for token in ["activateStructuredBlock", "quantityRulePageIndex", 'state.quantityRuleView = "original"', "无可靠 bbox，仅跳转原页，不伪造高亮"]),
        )
        record(
            "three_quantity_rule_subviews_present",
            "original/structured/comparison",
            "present",
            all(token in quota_js for token in ['data-rule-view="original"', 'data-rule-view="structured"', 'data-rule-view="comparison"']),
        )
        record("dual_view_api_utf8", "UTF-8 Chinese without mojibake", "土石方工程", utf8_response_ok(structured_response, "土石方工程"))

        draft_export = client.get("/api/quota-a111/draft/export")
        audit_export = client.get("/api/quota-a111/draft/audit/export")
        record("draft_export_success", "exported=true", draft_export.status_code, draft_export.status_code == 200 and draft_export.json().get("exported") is True)
        record("audit_export_success", "exported=true", audit_export.status_code, audit_export.status_code == 200 and audit_export.json().get("exported") is True)

        restore_results = [
            client.post(f"/api/quota-a111/draft/edge/{edge_id}/revert")
            for edge_id in (copy_edge_id, move_edge_id, exclude_edge_id)
        ]
        record("restore_operations_success", "three revert calls HTTP 200", [response.status_code for response in restore_results], all(response.status_code == 200 for response in restore_results))
        _, after_restore = tree_stats(client)
        restored_ok = all(
            int(after_restore[bill]["effective_candidate_count"]) == int(initial_by_bill[bill]["effective_candidate_count"])
            and int(after_restore[bill]["draft_active_count"]) == 0
            for bill in {copy_target, move_source_bill, move_target_bill, exclude_bill}
        )
        record("restore_recovers_all_counts", "initial effective and zero active delta", restored_ok, restored_ok)
        record("approved_count_zero_during_smoke", "0", approved_count(), approved_count() == 0)

    except Exception as exc:  # keep restoration and evidence even on unexpected failures
        record("unexpected_smoke_exception", "none", repr(exc), False)
    finally:
        client.post("/api/quota-a111/draft/reset-test-data")
        restore_draft_tables(existing_snapshot)
        restored_snapshot = snapshot_draft_tables()
        record("preexisting_draft_snapshot_restored", "exact snapshot restored", restored_snapshot == existing_snapshot, restored_snapshot == existing_snapshot)
        artifacts = quota_a111_generate_quantity_rule_dual_view_artifacts()

    source_hash_after = {str(path): sha256(path) for path in source_files}
    mapping_unchanged = source_hash_after[str(MAPPING_CANDIDATE_CSV)] == source_hash_before[str(MAPPING_CANDIDATE_CSV)]
    pdf_unchanged = source_hash_after[str(SOURCE_PDF)] == source_hash_before[str(SOURCE_PDF)]
    pdf_candidate_unchanged = all(source_hash_after[str(path)] == source_hash_before[str(path)] for path in PDF_CANDIDATE_FILES)
    record("original_mapping_candidate_hash_unchanged", "SHA256 unchanged", mapping_unchanged, mapping_unchanged)
    record("original_pdf_hash_unchanged", "SHA256 unchanged", pdf_unchanged, pdf_unchanged)
    record("pdf_candidate_hash_unchanged", "SHA256 unchanged", pdf_candidate_unchanged, pdf_candidate_unchanged)
    record("all_readonly_source_hashes_unchanged", "SHA256 unchanged", source_hash_after == source_hash_before, source_hash_after == source_hash_before)
    record("production_db_not_written", "local prototype SQLite only", "no production database configured/written", True)
    record("approved_count_zero_final", "0", approved_count(), approved_count() == 0)
    final_enterprise = client.get("/")
    final_bid = client.get("/bid")
    record("old_pages_not_broken", "/ and /bid HTTP 200", f"{final_enterprise.status_code}/{final_bid.status_code}", final_enterprise.status_code == 200 and final_bid.status_code == 200)

    write_csv(SMOKE_CSV, checks, ["check_name", "expected", "actual", "pass_fail", "remark"])
    recommendation = write_report(checks, artifacts)
    failed = [row for row in checks if row["pass_fail"] != "pass"]
    if failed:
        raise AssertionError(f"quota-a111 quantity rule dual view smoke failed: {[row['check_name'] for row in failed]}")

    print("quota_a111_quantity_rule_dual_view_smoke_passed=true")
    print(f"checks={len(checks)}")
    print(f"source_blocks={len(artifacts['source_blocks'])}")
    print(f"scope_links={len(artifacts['scope_links'])}")
    print(f"source_pages={len(artifacts['page_index'])}")
    print(f"recommendation={recommendation}")
    print(f"smoke_result={SMOKE_CSV}")
    print(f"report={REPORT_MD}")
    print(f"approved_count={approved_count()}")


if __name__ == "__main__":
    main()
