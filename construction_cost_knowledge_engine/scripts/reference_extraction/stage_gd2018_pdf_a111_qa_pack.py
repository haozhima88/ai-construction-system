#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage GD2018-PDF-A111-QA-PACK-1.

Builds a manual QA package from the A.1.1 official-PDF structured candidates.
This stage only creates review samples, risk lists, decision templates, and
review guidance. It does not modify upstream candidates, sources, baseline,
web_collab_prototype, database data, or enterprise quota artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
INPUT_DIR_REL = (
    ENGINE_REL
    / "data"
    / "private"
    / "reference_extraction"
    / "runs"
    / "GD2018_PDF_A111_STRUCTURED_CANDIDATE_1"
)
OUTPUT_DIR_REL = (
    ENGINE_REL
    / "data"
    / "private"
    / "reference_extraction"
    / "runs"
    / "GD2018_PDF_A111_QA_PACK_1"
)

SUPPLEMENTAL_CODES = [
    "A1-1-56-1",
    "A1-1-56-2",
    "A1-1-56-3",
    "A1-1-56-4",
    "A1-1-118-1",
    "A1-1-118-2",
]

MAIN_QA_FIELDS = [
    "qa_sample_id",
    "qa_category",
    "quota_source_code",
    "quota_name_from_pdf",
    "quota_name_from_xlsx",
    "unit_from_pdf",
    "unit_from_xlsx",
    "base_price_from_pdf",
    "total_from_xlsx",
    "labor_fee_from_pdf",
    "labor_fee_from_xlsx",
    "material_fee_from_pdf",
    "material_fee_from_xlsx",
    "machine_fee_from_pdf",
    "machine_fee_from_xlsx",
    "management_fee_from_pdf",
    "management_fee_from_xlsx",
    "delta_total",
    "delta_labor",
    "delta_material",
    "delta_machine",
    "delta_management",
    "pdf_page_no",
    "book_page_no",
    "parse_confidence",
    "match_status",
    "issue_type",
    "human_decision",
    "human_decision_level",
    "human_comment",
]

RESOURCE_QA_FIELDS = [
    "qa_sample_id",
    "qa_category",
    "quota_source_code",
    "quota_name_from_pdf",
    "resource_category_raw",
    "resource_category_normalized",
    "resource_code",
    "resource_name",
    "resource_spec",
    "resource_unit_raw",
    "resource_unit_normalized",
    "resource_unit_price",
    "resource_consumption",
    "resource_fee_calculated",
    "resource_row_index",
    "pdf_page_no",
    "book_page_no",
    "table_header_group_id",
    "column_index_in_table",
    "parse_confidence",
    "issue_type",
    "raw_row_json",
    "human_decision",
    "human_decision_level",
    "human_comment",
]

WORK_CONTENT_QA_FIELDS = [
    "qa_sample_id",
    "quota_source_code_start",
    "quota_source_code_end",
    "applicable_quota_codes_json",
    "work_content_raw",
    "work_content_normalized",
    "pdf_page_no",
    "book_page_no",
    "parse_confidence",
    "scope_issue",
    "human_applicable_scope",
    "human_decision",
    "human_comment",
]

QUANTITY_RULE_QA_FIELDS = [
    "qa_sample_id",
    "rule_no",
    "rule_text_raw",
    "rule_text_normalized",
    "applicable_section",
    "applicable_quota_code_range",
    "pdf_page_no",
    "book_page_no",
    "parse_confidence",
    "human_applicable_scope",
    "human_decision",
    "human_comment",
]

SUPPLEMENTAL_FIELDS = [
    "supplemental_quota_code",
    "present_in_xlsx",
    "present_in_pdf_candidate",
    "pdf_detected_nearby_page",
    "xlsx_name",
    "xlsx_unit",
    "xlsx_labor_fee",
    "xlsx_material_fee",
    "xlsx_machine_fee",
    "xlsx_management_fee",
    "xlsx_total",
    "nearby_pdf_quota_codes",
    "possible_reason",
    "manual_check_required",
    "human_decision",
    "human_comment",
]

HIGH_RISK_FIELDS = [
    "issue_id",
    "issue_type",
    "severity",
    "pdf_page_no",
    "book_page_no",
    "quota_source_code",
    "resource_code",
    "field_name",
    "issue_detail",
    "suggested_action",
    "raw_text_sample",
    "human_owner",
    "human_decision",
    "human_comment",
]

DECISION_FIELDS = [
    "object_type",
    "object_id",
    "quota_source_code",
    "field_group",
    "current_value",
    "human_corrected_value",
    "decision_level",
    "decision_status",
    "reviewer",
    "review_date",
    "comment",
]

SUMMARY_FIELDS = ["metric", "value", "remark"]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def code_key(code: str) -> Tuple[int, int, str]:
    match = re.fullmatch(r"A1-1-(\d+)(?:-(\d+))?", code or "")
    if not match:
        return (99_999, 99_999, code or "")
    return (int(match.group(1)), int(match.group(2) or 0), code or "")


def confidence(row: Dict[str, str]) -> float:
    try:
        return float(row.get("parse_confidence") or 0)
    except ValueError:
        return 0.0


def take_spread(rows: Sequence[Dict[str, str]], count: int) -> List[Dict[str, str]]:
    if count <= 0 or not rows:
        return []
    if len(rows) <= count:
        return list(rows)
    if count == 1:
        return [rows[0]]
    indexes = []
    last = len(rows) - 1
    for index in range(count):
        indexes.append(round(index * last / (count - 1)))
    return [rows[index] for index in sorted(set(indexes))][:count]


def category_for_business_code(code: str) -> str:
    n = code_key(code)[0]
    if 1 <= n <= 4:
        return "business_flattening_and_tamping"
    if 5 <= n <= 26:
        return "business_manual_excavation"
    if 27 <= n <= 36:
        return "business_manual_transport_or_loading"
    if 37 <= n <= 52:
        return "business_mechanical_excavation"
    if 53 <= n <= 56 or 117 <= n <= 118:
        return "business_truck_transport"
    if 67 <= n <= 125:
        return "business_rockwork"
    if 126 <= n <= 133:
        return "business_backfill"
    if 134 <= n <= 137:
        return "business_retaining_board"
    return "business_general"


def enrich_main_row(row: Dict[str, str], structured_by_code: Dict[str, Dict[str, str]], categories: Sequence[str], sample_id: str) -> Dict[str, str]:
    code = row.get("quota_source_code", "")
    source = structured_by_code.get(code, {})
    return {
        "qa_sample_id": sample_id,
        "qa_category": ";".join(categories),
        "quota_source_code": code,
        "quota_name_from_pdf": row.get("quota_name_from_pdf", ""),
        "quota_name_from_xlsx": row.get("quota_name_from_xlsx", ""),
        "unit_from_pdf": row.get("unit_from_pdf", ""),
        "unit_from_xlsx": row.get("unit_from_xlsx", ""),
        "base_price_from_pdf": row.get("base_price_from_pdf", ""),
        "total_from_xlsx": row.get("total_from_xlsx", ""),
        "labor_fee_from_pdf": row.get("labor_fee_from_pdf", ""),
        "labor_fee_from_xlsx": row.get("labor_fee_from_xlsx", ""),
        "material_fee_from_pdf": row.get("material_fee_from_pdf", ""),
        "material_fee_from_xlsx": row.get("material_fee_from_xlsx", ""),
        "machine_fee_from_pdf": row.get("machine_fee_from_pdf", ""),
        "machine_fee_from_xlsx": row.get("machine_fee_from_xlsx", ""),
        "management_fee_from_pdf": row.get("management_fee_from_pdf", ""),
        "management_fee_from_xlsx": row.get("management_fee_from_xlsx", ""),
        "delta_total": row.get("delta_total", ""),
        "delta_labor": row.get("delta_labor", ""),
        "delta_material": row.get("delta_material", ""),
        "delta_machine": row.get("delta_machine", ""),
        "delta_management": row.get("delta_management", ""),
        "pdf_page_no": source.get("pdf_page_no", ""),
        "book_page_no": source.get("book_page_no", ""),
        "parse_confidence": source.get("parse_confidence", ""),
        "match_status": row.get("match_status", ""),
        "issue_type": row.get("issue_type", ""),
        "human_decision": "",
        "human_decision_level": "",
        "human_comment": "",
    }


def build_main_quota_sample(reconciliation: Sequence[Dict[str, str]], structured: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    structured_by_code = {row["quota_source_code"]: row for row in structured}
    recon_by_code = {row["quota_source_code"]: row for row in reconciliation}
    selected: Dict[str, Dict[str, Any]] = {}

    def add(code: str, category: str) -> None:
        row = recon_by_code.get(code)
        if not row:
            return
        selected.setdefault(code, {"row": row, "categories": []})
        if category not in selected[code]["categories"]:
            selected[code]["categories"].append(category)

    by_status: DefaultDict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in sorted(reconciliation, key=lambda item: code_key(item.get("quota_source_code", ""))):
        by_status[row.get("match_status", "")].append(row)

    for row in take_spread(by_status["matched_exact"], 8):
        add(row["quota_source_code"], "sample_exact_match")
    for row in take_spread(by_status["matched_rounding_delta"], 6):
        add(row["quota_source_code"], "sample_rounding_delta")
    unit_rows = [
        row
        for row in reconciliation
        if row.get("match_status") == "matched_unit_diff_only" or "unit" in row.get("issue_type", "")
    ]
    for row in take_spread(sorted(unit_rows, key=lambda item: code_key(item.get("quota_source_code", ""))), 6):
        add(row["quota_source_code"], "sample_unit_difference")
    for row in take_spread(by_status["matched_name_diff_only"], 4):
        add(row["quota_source_code"], "sample_name_difference_only")

    for code in [f"A1-1-{n}" for n in range(53, 57)] + SUPPLEMENTAL_CODES:
        add(code, "must_check_A1_1_56_nearby_or_supplement")
    for code in ["A1-1-117", "A1-1-118", "A1-1-118-1", "A1-1-118-2"]:
        add(code, "must_check_A1_1_118_nearby_or_supplement")
    for code in [f"A1-1-{n}" for n in range(134, 138)]:
        add(code, "must_check_retaining_board_A1_1_134_to_137")

    business_seed_codes = [
        "A1-1-1",
        "A1-1-3",
        "A1-1-5",
        "A1-1-9",
        "A1-1-18",
        "A1-1-27",
        "A1-1-35",
        "A1-1-37",
        "A1-1-44",
        "A1-1-53",
        "A1-1-55",
        "A1-1-67",
        "A1-1-73",
        "A1-1-98",
        "A1-1-126",
        "A1-1-130",
        "A1-1-132",
        "A1-1-134",
    ]
    for code in business_seed_codes:
        if len(selected) >= 45:
            break
        add(code, category_for_business_code(code))

    output: List[Dict[str, str]] = []
    for index, code in enumerate(sorted(selected, key=code_key), start=1):
        output.append(enrich_main_row(selected[code]["row"], structured_by_code, selected[code]["categories"], f"MAIN_A111_QA_{index:03d}"))
    return output


def issue_types_for_resource(issues: Sequence[Dict[str, str]]) -> Dict[Tuple[str, str], str]:
    issue_map: DefaultDict[Tuple[str, str], set[str]] = defaultdict(set)
    for issue in issues:
        key = (issue.get("quota_source_code", ""), issue.get("resource_code", ""))
        if key[0] and key[1] and issue.get("issue_type"):
            issue_map[key].add(issue["issue_type"])
    return {key: ";".join(sorted(values)) for key, values in issue_map.items()}


def resource_key(row: Dict[str, str]) -> Tuple[str, str, str, str]:
    return (
        row.get("quota_source_code", ""),
        row.get("resource_code", ""),
        row.get("resource_row_index", ""),
        row.get("column_index_in_table", ""),
    )


def build_resource_sample(
    resources: Sequence[Dict[str, str]],
    fee_summary: Sequence[Dict[str, str]],
    issues: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    issue_map = issue_types_for_resource(issues)
    below_main_codes = {
        row["quota_source_code"]
        for row in fee_summary
        if row.get("resource_reconciliation_status") == "resource_sum_below_main_price"
    }
    resources_sorted = sorted(resources, key=lambda row: (code_key(row.get("quota_source_code", "")), row.get("resource_row_index", ""), row.get("resource_code", "")))
    selected: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}

    def add(row: Dict[str, str], category: str) -> None:
        key = resource_key(row)
        selected.setdefault(key, {"row": row, "categories": []})
        if category not in selected[key]["categories"]:
            selected[key]["categories"].append(category)

    def rows_for_code(code: str) -> List[Dict[str, str]]:
        return [row for row in resources_sorted if row.get("quota_source_code") == code]

    def pick_for_code(code: str, limit: int = 1) -> None:
        rows = sorted(rows_for_code(code), key=lambda row: (confidence(row), row.get("resource_category_normalized", ""), row.get("resource_code", "")))
        for row in rows[:limit]:
            add(row, f"must_check_quota_{code}")

    for code in sorted(below_main_codes, key=code_key):
        pick_for_code(code, 1)
    for code in [f"A1-1-{n}" for n in range(53, 57)] + ["A1-1-117", "A1-1-118"] + [f"A1-1-{n}" for n in range(134, 138)]:
        pick_for_code(code, 2)

    low_rows = [row for row in resources_sorted if confidence(row) < 0.80]
    high_rows = [row for row in resources_sorted if confidence(row) >= 0.80]
    low_count = lambda: sum(1 for item in selected.values() if confidence(item["row"]) < 0.80)
    high_count = lambda: sum(1 for item in selected.values() if confidence(item["row"]) >= 0.80)
    for row in low_rows:
        if len(selected) >= 50 or low_count() >= 20:
            break
        add(row, "sample_low_confidence_resource")
    for row in high_rows:
        if len(selected) >= 50 or high_count() >= 10:
            break
        add(row, "sample_high_confidence_resource")

    category_present = {item["row"].get("resource_category_normalized", "") for item in selected.values()}
    for category in ["人工", "材料", "机具"]:
        if category in category_present:
            continue
        for row in resources_sorted:
            if row.get("resource_category_normalized") == category and len(selected) < 50:
                add(row, f"category_coverage_{category}")
                break

    # If required checks already filled the sample but high-confidence coverage is thin, replace least-risk rows.
    if high_count() < 10:
        for row in high_rows:
            if len(selected) < 50:
                add(row, "sample_high_confidence_resource")
            if high_count() >= 10:
                break

    output: List[Dict[str, str]] = []
    for index, item in enumerate(sorted(selected.values(), key=lambda item: (code_key(item["row"].get("quota_source_code", "")), item["row"].get("resource_row_index", ""), item["row"].get("resource_code", ""))), start=1):
        row = item["row"]
        key = (row.get("quota_source_code", ""), row.get("resource_code", ""))
        output.append(
            {
                "qa_sample_id": f"RES_A111_QA_{index:03d}",
                "qa_category": ";".join(item["categories"]),
                "quota_source_code": row.get("quota_source_code", ""),
                "quota_name_from_pdf": row.get("quota_name_from_pdf", ""),
                "resource_category_raw": row.get("resource_category_raw", ""),
                "resource_category_normalized": row.get("resource_category_normalized", ""),
                "resource_code": row.get("resource_code", ""),
                "resource_name": row.get("resource_name", ""),
                "resource_spec": row.get("resource_spec", ""),
                "resource_unit_raw": row.get("resource_unit_raw", ""),
                "resource_unit_normalized": row.get("resource_unit_normalized", ""),
                "resource_unit_price": row.get("resource_unit_price", ""),
                "resource_consumption": row.get("resource_consumption", ""),
                "resource_fee_calculated": row.get("resource_fee_calculated", ""),
                "resource_row_index": row.get("resource_row_index", ""),
                "pdf_page_no": row.get("pdf_page_no", ""),
                "book_page_no": row.get("book_page_no", ""),
                "table_header_group_id": row.get("table_header_group_id", ""),
                "column_index_in_table": row.get("column_index_in_table", ""),
                "parse_confidence": row.get("parse_confidence", ""),
                "issue_type": issue_map.get(key, ""),
                "raw_row_json": row.get("raw_row_json", ""),
                "human_decision": "",
                "human_decision_level": "",
                "human_comment": "",
            }
        )
    return output


def build_work_content_qa(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    output = []
    for index, row in enumerate(sorted(rows, key=lambda item: code_key(item.get("quota_source_code_start", ""))), start=1):
        output.append(
            {
                "qa_sample_id": f"WORK_A111_QA_{index:03d}",
                "quota_source_code_start": row.get("quota_source_code_start", ""),
                "quota_source_code_end": row.get("quota_source_code_end", ""),
                "applicable_quota_codes_json": row.get("applicable_quota_codes_json", ""),
                "work_content_raw": row.get("work_content_raw", ""),
                "work_content_normalized": row.get("work_content_normalized", ""),
                "pdf_page_no": row.get("pdf_page_no", ""),
                "book_page_no": row.get("book_page_no", ""),
                "parse_confidence": row.get("parse_confidence", ""),
                "scope_issue": "work_content_scope_pending_cost_QA",
                "human_applicable_scope": "",
                "human_decision": "",
                "human_comment": "",
            }
        )
    return output


def build_quantity_rule_qa(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    output = []
    for index, row in enumerate(sorted(rows, key=lambda item: int(item.get("pdf_page_no") or 0)), start=1):
        output.append(
            {
                "qa_sample_id": f"RULE_A111_QA_{index:03d}",
                "rule_no": row.get("rule_no", ""),
                "rule_text_raw": row.get("rule_text_raw", ""),
                "rule_text_normalized": row.get("rule_text_normalized", ""),
                "applicable_section": row.get("applicable_section", ""),
                "applicable_quota_code_range": row.get("applicable_quota_code_range", ""),
                "pdf_page_no": row.get("pdf_page_no", ""),
                "book_page_no": row.get("book_page_no", ""),
                "parse_confidence": row.get("parse_confidence", ""),
                "human_applicable_scope": "",
                "human_decision": "",
                "human_comment": "",
            }
        )
    return output


def build_supplemental_investigation(reconciliation: Sequence[Dict[str, str]], structured: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    recon_by_code = {row["quota_source_code"]: row for row in reconciliation}
    structured_by_code = {row["quota_source_code"]: row for row in structured}
    nearby = {
        "A1-1-56-1": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-56-2": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-56-3": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-56-4": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-118-1": ["A1-1-117", "A1-1-118"],
        "A1-1-118-2": ["A1-1-117", "A1-1-118"],
    }
    output = []
    for code in SUPPLEMENTAL_CODES:
        row = recon_by_code.get(code, {})
        nearby_codes = nearby[code]
        nearby_pages = sorted({structured_by_code.get(item, {}).get("pdf_page_no", "") for item in nearby_codes if structured_by_code.get(item, {}).get("pdf_page_no", "")})
        output.append(
            {
                "supplemental_quota_code": code,
                "present_in_xlsx": "yes" if row.get("quota_name_from_xlsx") else "no",
                "present_in_pdf_candidate": "yes" if structured_by_code.get(code) else "no",
                "pdf_detected_nearby_page": ";".join(nearby_pages),
                "xlsx_name": row.get("quota_name_from_xlsx", ""),
                "xlsx_unit": row.get("unit_from_xlsx", ""),
                "xlsx_labor_fee": row.get("labor_fee_from_xlsx", ""),
                "xlsx_material_fee": row.get("material_fee_from_xlsx", ""),
                "xlsx_machine_fee": row.get("machine_fee_from_xlsx", ""),
                "xlsx_management_fee": row.get("management_fee_from_xlsx", ""),
                "xlsx_total": row.get("total_from_xlsx", ""),
                "nearby_pdf_quota_codes": ";".join(nearby_codes),
                "possible_reason": "manual_review_required",
                "manual_check_required": "yes",
                "human_decision": "",
                "human_comment": "",
            }
        )
    return output


def build_high_risk_issues(issues: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    risky_terms = [
        "resource_quota_alignment_uncertain",
        "resource_sum_reconciliation_delta",
        "low_parse_confidence",
        "private_unicode_unit",
        "work_content_scope_uncertain",
        "quantity_rule_scope_uncertain",
    ]
    output = []
    for row in issues:
        issue_type = row.get("issue_type", "")
        include = row.get("severity") in {"high", "blocking"} or any(term in issue_type for term in risky_terms)
        if include:
            output.append({**row, "human_owner": "", "human_decision": "", "human_comment": ""})
    return output


def build_decision_template(
    main_rows: Sequence[Dict[str, str]],
    resource_rows: Sequence[Dict[str, str]],
    work_rows: Sequence[Dict[str, str]],
    rule_rows: Sequence[Dict[str, str]],
    supplemental_rows: Sequence[Dict[str, str]],
    issue_rows: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []

    def add(object_type: str, object_id: str, quota: str, field_group: str, current_value: str) -> None:
        output.append(
            {
                "object_type": object_type,
                "object_id": object_id,
                "quota_source_code": quota,
                "field_group": field_group,
                "current_value": current_value,
                "human_corrected_value": "",
                "decision_level": "",
                "decision_status": "pending",
                "reviewer": "",
                "review_date": "",
                "comment": "",
            }
        )

    for row in main_rows:
        add("main_quota", row["qa_sample_id"], row["quota_source_code"], "main_quota_price_and_unit", f"{row.get('match_status','')}|{row.get('issue_type','')}")
    for row in resource_rows:
        add("resource_detail", row["qa_sample_id"], row["quota_source_code"], "resource_alignment_and_fee", f"{row.get('resource_code','')}|{row.get('issue_type','')}")
    for row in work_rows:
        add("work_content", row["qa_sample_id"], row["quota_source_code_start"], "work_content_scope", row.get("applicable_quota_codes_json", ""))
    for row in rule_rows:
        add("quantity_rule", row["qa_sample_id"], "", "quantity_rule_scope", row.get("rule_no", ""))
    for row in supplemental_rows:
        add("supplemental_code", row["supplemental_quota_code"], row["supplemental_quota_code"], "supplemental_source_investigation", row.get("possible_reason", ""))
    for row in issue_rows:
        add("issue", row["issue_id"], row.get("quota_source_code", ""), row.get("issue_type", ""), row.get("issue_detail", ""))
    return output


def build_summary_rows(
    main_rows: Sequence[Dict[str, str]],
    resource_rows: Sequence[Dict[str, str]],
    work_rows: Sequence[Dict[str, str]],
    rule_rows: Sequence[Dict[str, str]],
    supplemental_rows: Sequence[Dict[str, str]],
    high_risk_rows: Sequence[Dict[str, str]],
    decision_rows: Sequence[Dict[str, str]],
    reconciliation: Sequence[Dict[str, str]],
    fee_summary: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    recon_counts = Counter(row.get("match_status", "") for row in reconciliation)
    fee_counts = Counter(row.get("resource_reconciliation_status", "") for row in fee_summary)
    severity_counts = Counter(row.get("severity", "") for row in high_risk_rows)
    return [
        {"metric": "main_quota_sample_rows", "value": len(main_rows), "remark": "target 30-45"},
        {"metric": "resource_sample_rows", "value": len(resource_rows), "remark": "target 30-50"},
        {"metric": "work_content_rows", "value": len(work_rows), "remark": "all work content candidates"},
        {"metric": "quantity_rule_rows", "value": len(rule_rows), "remark": "all quantity rule page-level rows"},
        {"metric": "supplemental_investigation_rows", "value": len(supplemental_rows), "remark": "all six xlsx-only supplemental codes"},
        {"metric": "high_risk_issue_rows", "value": len(high_risk_rows), "remark": "filtered issue review list"},
        {"metric": "high_or_blocking_issue_rows", "value": severity_counts.get("high", 0) + severity_counts.get("blocking", 0), "remark": "severity high/blocking only"},
        {"metric": "decision_template_rows", "value": len(decision_rows), "remark": "blank human decision rows"},
        {"metric": "reconciliation_status_counts", "value": json.dumps(dict(recon_counts), ensure_ascii=False), "remark": "source candidate run"},
        {"metric": "resource_fee_summary_status_counts", "value": json.dumps(dict(fee_counts), ensure_ascii=False), "remark": "source candidate run"},
        {"metric": "next_step_recommendation", "value": "qa_pack_ready_but_parser_refinement_likely", "remark": "resource alignment review remains substantial"},
    ]


def write_checklist(path: Path) -> int:
    text = """# A.1.1 PDF Structured Candidate Manual QA Checklist

## 1. 主项检查
- 定额编号是否正确；
- PDF 名称是否与原文一致；
- 单位是否正确；
- 人工费、材料费、机具费、管理费、合计是否与 PDF 一致；
- 与 Excel 差异是否可接受。

## 2. 资源明细检查
- 资源是否挂在正确 quota_source_code 下；
- 资源类别是否正确；
- 资源编码是否正确；
- 资源名称 / 规格 / 单位 / 单价 / 消耗量是否正确；
- resource_fee_calculated 是否合理。

## 3. 工作内容检查
- work_content 是否属于当前 quota group；
- 是否应扩大或缩小适用范围。

## 4. 工程量规则检查
- 是否为广东省定额内部规则；
- 适用章节是否正确；
- 不要与 GB/T 50854 工程量规则混淆。

## 5. 补充编号检查
- 6 个 xlsx-only supplemental codes 是否 PDF 漏抽；
- 是否在其他册或补充文件；
- 是否应作为 official supplemental quota；
- 是否应转为 enterprise supplement。

## 6. 审核结论等级
P0_reject
P1_keep_pending
P2_parser_fix_required
P3_candidate_accepted
P4_cost_department_confirmed
"""
    path.write_text(text, encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.strip())


def write_report(
    path: Path,
    input_dir: Path,
    output_dir: Path,
    main_rows: Sequence[Dict[str, str]],
    resource_rows: Sequence[Dict[str, str]],
    work_rows: Sequence[Dict[str, str]],
    rule_rows: Sequence[Dict[str, str]],
    supplemental_rows: Sequence[Dict[str, str]],
    high_risk_rows: Sequence[Dict[str, str]],
    decision_rows: Sequence[Dict[str, str]],
    summary_row_count: int,
    qa_instruction_row_count: int,
) -> None:
    main_counts = Counter(row.get("qa_category", "") for row in main_rows)
    resource_counts = Counter(row.get("resource_category_normalized", "") for row in resource_rows)
    severity_counts = Counter(row.get("severity", "") for row in high_risk_rows)
    xlsx_sheets = {
        "summary": summary_row_count,
        "main_quota_sample": len(main_rows),
        "resource_sample": len(resource_rows),
        "work_content_all": len(work_rows),
        "quantity_rule_all": len(rule_rows),
        "supplemental_investigation": len(supplemental_rows),
        "high_risk_issues": len(high_risk_rows),
        "decision_template": len(decision_rows),
        "qa_instructions": qa_instruction_row_count,
    }
    report = f"""# Stage GD2018-PDF-A111-QA-PACK-1 Report

## 1. Task Scope

本轮只生成人工 QA 包、抽样清单、风险清单和 QA 指引；不继续 PDF 解析，不写库，不改候选数据，不进入 Web。

## 2. Inputs

Input run directory: `{input_dir}`

Required candidate inputs were read from the structured candidate run and were not modified.

## 3. Main Quota QA Sample

- sample rows: {len(main_rows)}
- category count: `{json.dumps(dict(main_counts), ensure_ascii=False)}`

## 4. Resource Detail QA Sample

- sample rows: {len(resource_rows)}
- resource category count: `{json.dumps(dict(resource_counts), ensure_ascii=False)}`

## 5. Work Content QA

All {len(work_rows)} work-content rows are included because every applicable scope remains pending manual QA.

## 6. Quantity Rule QA

All {len(rule_rows)} quantity-rule page-level rows are included. Reviewers should confirm they are Guangdong quota internal rules and not GB/T 50854 rules.

## 7. Supplemental Code Investigation

All {len(supplemental_rows)} xlsx-only supplemental codes are included for source investigation.

## 8. High Risk Issues

- high/blocking issue rows: {severity_counts.get("high", 0) + severity_counts.get("blocking", 0)}
- high_risk_issue_review_A111.csv rows: {len(high_risk_rows)}

## 9. Excel QA Pack

Generated workbook: `{output_dir / "A111_PDF_Structured_QA_Pack.xlsx"}`

Sheet row counts: `{json.dumps(xlsx_sheets, ensure_ascii=False)}`

## 10. Next Step Recommendation

qa_pack_ready_but_parser_refinement_likely
"""
    path.write_text(report, encoding="utf-8")


def run(project_root: Path) -> Dict[str, Path]:
    input_dir = project_root / INPUT_DIR_REL
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    structured = read_csv(input_dir / "quota_pdf_structured_A111_candidate.csv")
    resources = read_csv(input_dir / "quota_pdf_resource_detail_A111_candidate.csv")
    fee_summary = read_csv(input_dir / "quota_pdf_resource_fee_summary_A111.csv")
    work_content = read_csv(input_dir / "quota_pdf_work_content_A111_candidate.csv")
    quantity_rule = read_csv(input_dir / "quota_pdf_quantity_rule_A111_candidate.csv")
    reconciliation = read_csv(input_dir / "quota_pdf_xlsx_reconciliation_A111.csv")
    issues = read_csv(input_dir / "quota_pdf_extraction_issues_A111.csv")
    required_report = input_dir / "stage_gd2018_pdf_a111_structured_candidate_report.md"
    if not required_report.exists():
        raise FileNotFoundError(required_report)

    main_rows = build_main_quota_sample(reconciliation, structured)
    resource_rows = build_resource_sample(resources, fee_summary, issues)
    work_rows = build_work_content_qa(work_content)
    rule_rows = build_quantity_rule_qa(quantity_rule)
    supplemental_rows = build_supplemental_investigation(reconciliation, structured)
    high_risk_rows = build_high_risk_issues(issues)
    decision_rows = build_decision_template(main_rows, resource_rows, work_rows, rule_rows, supplemental_rows, high_risk_rows)
    summary_rows = build_summary_rows(main_rows, resource_rows, work_rows, rule_rows, supplemental_rows, high_risk_rows, decision_rows, reconciliation, fee_summary)
    paths = {
        "main_quota_sample": output_dir / "manual_qa_main_quota_sample_A111.csv",
        "resource_sample": output_dir / "manual_qa_resource_sample_A111.csv",
        "work_content_sample": output_dir / "manual_qa_work_content_sample_A111.csv",
        "quantity_rule_sample": output_dir / "manual_qa_quantity_rule_sample_A111.csv",
        "supplemental": output_dir / "supplemental_code_investigation_A111.csv",
        "high_risk": output_dir / "high_risk_issue_review_A111.csv",
        "decision_template": output_dir / "qa_decision_template_A111.csv",
        "checklist": output_dir / "manual_qa_checklist_A111.md",
        "report": output_dir / "stage_gd2018_pdf_a111_qa_pack_report.md",
    }
    write_csv(paths["main_quota_sample"], MAIN_QA_FIELDS, main_rows)
    write_csv(paths["resource_sample"], RESOURCE_QA_FIELDS, resource_rows)
    write_csv(paths["work_content_sample"], WORK_CONTENT_QA_FIELDS, work_rows)
    write_csv(paths["quantity_rule_sample"], QUANTITY_RULE_QA_FIELDS, rule_rows)
    write_csv(paths["supplemental"], SUPPLEMENTAL_FIELDS, supplemental_rows)
    write_csv(paths["high_risk"], HIGH_RISK_FIELDS, high_risk_rows)
    write_csv(paths["decision_template"], DECISION_FIELDS, decision_rows)
    qa_instruction_row_count = write_checklist(paths["checklist"])
    write_report(
        paths["report"],
        input_dir,
        output_dir,
        main_rows,
        resource_rows,
        work_rows,
        rule_rows,
        supplemental_rows,
        high_risk_rows,
        decision_rows,
        len(summary_rows),
        qa_instruction_row_count,
    )
    return paths


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        paths = run(args.project_root)
    except Exception as exc:  # pragma: no cover - command-line guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Generated A.1.1 QA pack CSV/MD artifacts:")
    for name, path in paths.items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
