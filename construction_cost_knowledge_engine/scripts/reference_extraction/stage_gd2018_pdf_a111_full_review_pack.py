#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage GD2018-PDF-A111-FULL-REVIEW-PACK-1.

Build a full manual review pack from the existing A.1.1 PDF structured
candidate CSVs. This stage does not parse PDFs, write databases, modify
candidate inputs, modify normalized Excel sources, touch web_collab_prototype,
or generate enterprise quota data.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape


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
PREVIOUS_QA_DIR_REL = (
    ENGINE_REL
    / "data"
    / "private"
    / "reference_extraction"
    / "runs"
    / "GD2018_PDF_A111_QA_PACK_1"
)
OUTPUT_DIR_REL = (
    ENGINE_REL
    / "data"
    / "private"
    / "reference_extraction"
    / "runs"
    / "GD2018_PDF_A111_FULL_REVIEW_PACK_1"
)

SUPPLEMENTAL_CODES = [
    "A1-1-56-1",
    "A1-1-56-2",
    "A1-1-56-3",
    "A1-1-56-4",
    "A1-1-118-1",
    "A1-1-118-2",
]

MAIN_FIELDS = [
    "quota_source_code",
    "quota_name_from_pdf",
    "quota_name_full_from_pdf",
    "quota_unit_raw",
    "quota_unit_normalized",
    "base_price",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "management_fee",
    "total_fee_calculated",
    "pdf_page_no",
    "book_page_no",
    "parse_confidence",
    "review_status",
    "human_decision",
    "human_corrected_name",
    "human_corrected_unit",
    "human_corrected_base_price",
    "human_comment",
]

RESOURCE_HUMAN_FIELDS = [
    "human_decision",
    "human_corrected_quota_source_code",
    "human_corrected_resource_category",
    "human_corrected_resource_code",
    "human_corrected_resource_name",
    "human_corrected_resource_unit",
    "human_corrected_resource_consumption",
    "human_corrected_resource_unit_price",
    "human_comment",
]

RESOURCE_SUMMARY_FIELDS = [
    "quota_source_code",
    "quota_name_from_pdf",
    "resource_row_count",
    "labor_resource_count",
    "material_resource_count",
    "machine_resource_count",
    "equipment_resource_count",
    "main_material_resource_count",
    "unknown_resource_count",
    "resource_labor_fee_sum",
    "resource_material_fee_sum",
    "resource_machine_fee_sum",
    "resource_total_fee_sum",
    "quota_labor_fee_from_main_table",
    "quota_material_fee_from_main_table",
    "quota_machine_fee_from_main_table",
    "quota_management_fee_from_main_table",
    "quota_base_price_from_main_table",
    "delta_labor",
    "delta_material",
    "delta_machine",
    "delta_resource_total_vs_base_price",
    "resource_reconciliation_status",
    "human_decision",
    "human_comment",
]

WORK_CONTENT_FIELDS = [
    "quota_source_code",
    "quota_name_from_pdf",
    "work_content_raw",
    "work_content_normalized",
    "source_quota_code_start",
    "source_quota_code_end",
    "source_work_content_id",
    "pdf_page_no",
    "book_page_no",
    "parse_confidence",
    "scope_issue",
    "human_corrected_work_content",
    "human_comment",
]

QUANTITY_RULE_FIELDS = [
    "quota_source_code",
    "quota_name_from_pdf",
    "applicable_rule_text",
    "rule_no",
    "rule_scope",
    "applicable_section",
    "applicable_quota_code_range",
    "requires_manual_scope_review",
    "pdf_page_no",
    "book_page_no",
    "human_corrected_rule_scope",
    "human_comment",
]

RECONCILIATION_FIELDS = [
    "quota_source_code",
    "present_in_pdf",
    "present_in_xlsx",
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
    "match_status",
    "issue_type",
    "human_decision",
    "human_comment",
]

COVERAGE_FIELDS = [
    "quota_source_code",
    "is_expected_base_code",
    "is_supplemental_code",
    "exists_in_main_quota_candidate",
    "exists_in_resource_display",
    "resource_row_count",
    "exists_in_resource_summary",
    "exists_in_work_content_expanded",
    "exists_in_quantity_rule_expanded",
    "exists_in_xlsx_reconciliation",
    "exists_in_issue_list",
    "main_quota_parse_confidence",
    "resource_min_parse_confidence",
    "has_high_or_blocking_issue",
    "coverage_status",
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
    "suggested_next_action",
    "human_decision",
    "human_comment",
]

SUMMARY_FIELDS = ["metric", "value", "remark"]
INSTRUCTION_FIELDS = ["line_no", "instruction"]

NUMERIC_FIELDS = {
    "base_price",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "management_fee",
    "total_fee_calculated",
    "pdf_page_no",
    "book_page_no",
    "parse_confidence",
    "resource_consumption",
    "resource_unit_price",
    "resource_market_price_ex_tax",
    "resource_market_price_tax_included",
    "tax_rate",
    "resource_fee_calculated",
    "resource_display_order",
    "column_index_in_table",
    "resource_row_count",
    "labor_resource_count",
    "material_resource_count",
    "machine_resource_count",
    "equipment_resource_count",
    "main_material_resource_count",
    "unknown_resource_count",
    "resource_labor_fee_sum",
    "resource_material_fee_sum",
    "resource_machine_fee_sum",
    "resource_total_fee_sum",
    "quota_labor_fee_from_main_table",
    "quota_material_fee_from_main_table",
    "quota_machine_fee_from_main_table",
    "quota_management_fee_from_main_table",
    "quota_base_price_from_main_table",
    "delta_labor",
    "delta_material",
    "delta_machine",
    "delta_resource_total_vs_base_price",
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
    "xlsx_labor_fee",
    "xlsx_material_fee",
    "xlsx_machine_fee",
    "xlsx_management_fee",
    "xlsx_total",
    "main_quota_parse_confidence",
    "resource_min_parse_confidence",
    "line_no",
    "value",
}

TEXT_CODE_FIELDS = {
    "quota_source_code",
    "quota_source_code_start",
    "quota_source_code_end",
    "source_quota_code_start",
    "source_quota_code_end",
    "supplemental_quota_code",
    "resource_code",
    "rule_no",
    "source_work_content_id",
    "issue_id",
}


def base_codes() -> List[str]:
    return [f"A1-1-{index}" for index in range(1, 138)]


def all_review_codes() -> List[str]:
    return base_codes() + SUPPLEMENTAL_CODES


def code_key(code: str) -> Tuple[int, int, str]:
    match = re.fullmatch(r"A1-1-(\d+)(?:-(\d+))?", code or "")
    if not match:
        return (99_999, 99_999, code or "")
    return (int(match.group(1)), int(match.group(2) or 0), code or "")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_headers(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def nstr(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def parse_decimal(value: Any) -> float:
    text = nstr(value).strip().replace(",", "")
    if not text or text in {"-", "—"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def fmt_money(value: float) -> str:
    return f"{value:.2f}"


def truthy(value: Any) -> bool:
    return nstr(value).strip().lower() in {"yes", "true", "1", "y"}


def join_unique(values: Iterable[Any], sep: str = ";") -> str:
    seen: List[str] = []
    for value in values:
        text = nstr(value).strip()
        if text and text not in seen:
            seen.append(text)
    return sep.join(seen)


def parse_code_list(row: Dict[str, str]) -> List[str]:
    raw = row.get("applicable_quota_codes_json", "")
    if raw.strip():
        try:
            parsed = json.loads(raw)
            codes = [nstr(item) for item in parsed if nstr(item)]
            if codes:
                return codes
        except json.JSONDecodeError:
            pass
    start = row.get("quota_source_code_start", "")
    end = row.get("quota_source_code_end", "")
    if start and end:
        start_key = code_key(start)[0]
        end_key = code_key(end)[0]
        if start_key <= end_key < 99_999:
            return [f"A1-1-{index}" for index in range(start_key, end_key + 1)]
    return [start] if start else []


def build_main_rows(structured: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    structured_by_code = {row.get("quota_source_code", ""): row for row in structured}
    rows: List[Dict[str, str]] = []
    for code in base_codes():
        source = structured_by_code.get(code, {})
        rows.append(
            {
                "quota_source_code": code,
                "quota_name_from_pdf": source.get("quota_name_from_pdf", ""),
                "quota_name_full_from_pdf": source.get("quota_name_full_from_pdf", ""),
                "quota_unit_raw": source.get("quota_unit_raw", ""),
                "quota_unit_normalized": source.get("quota_unit_normalized", ""),
                "base_price": source.get("base_price", ""),
                "labor_fee": source.get("labor_fee", ""),
                "material_fee": source.get("material_fee", ""),
                "machine_fee": source.get("machine_fee", ""),
                "management_fee": source.get("management_fee", ""),
                "total_fee_calculated": source.get("total_fee_calculated", ""),
                "pdf_page_no": source.get("pdf_page_no", ""),
                "book_page_no": source.get("book_page_no", ""),
                "parse_confidence": source.get("parse_confidence", ""),
                "review_status": "pending",
                "human_decision": "",
                "human_corrected_name": "",
                "human_corrected_unit": "",
                "human_corrected_base_price": "",
                "human_comment": "",
            }
        )
    return rows


def build_resource_display_rows(resource_display: Sequence[Dict[str, str]], headers: Sequence[str]) -> Tuple[List[str], List[Dict[str, str]]]:
    fields = list(headers) + [field for field in RESOURCE_HUMAN_FIELDS if field not in headers]
    rows: List[Dict[str, str]] = []
    for row in sorted(resource_display, key=lambda item: (code_key(item.get("quota_source_code", "")), item.get("resource_display_order", ""), item.get("resource_code", ""))):
        out = dict(row)
        for field in RESOURCE_HUMAN_FIELDS:
            out[field] = ""
        rows.append(out)
    return fields, rows


def build_resource_summary_rows(
    base_main_rows: Sequence[Dict[str, str]],
    resource_display: Sequence[Dict[str, str]],
    fee_summary: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    main_by_code = {row["quota_source_code"]: row for row in base_main_rows}
    fee_by_code = {row.get("quota_source_code", ""): row for row in fee_summary}
    resources_by_code: DefaultDict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in resource_display:
        resources_by_code[row.get("quota_source_code", "")].append(row)

    rows: List[Dict[str, str]] = []
    for code in base_codes():
        resources = resources_by_code.get(code, [])
        labor_count = sum(1 for row in resources if row.get("resource_category_normalized") == "labor" or truthy(row.get("is_labor")))
        material_count = sum(1 for row in resources if row.get("resource_category_normalized") == "material")
        machine_count = sum(1 for row in resources if row.get("resource_category_normalized") == "machine" or truthy(row.get("is_machine")))
        equipment_count = sum(1 for row in resources if truthy(row.get("is_equipment")))
        main_material_count = sum(1 for row in resources if truthy(row.get("is_main_material")))
        known_count = labor_count + material_count + machine_count + equipment_count
        unknown_count = max(0, len(resources) - known_count)

        def sum_fee(predicate: Any) -> float:
            return sum(parse_decimal(row.get("resource_fee_calculated")) for row in resources if predicate(row))

        labor_fee = sum_fee(lambda row: row.get("resource_category_normalized") == "labor" or truthy(row.get("is_labor")))
        material_fee = sum_fee(lambda row: row.get("resource_category_normalized") == "material")
        machine_fee = sum_fee(lambda row: row.get("resource_category_normalized") == "machine" or truthy(row.get("is_machine")))
        total_fee = sum(parse_decimal(row.get("resource_fee_calculated")) for row in resources)
        main = main_by_code.get(code, {})
        fee = fee_by_code.get(code, {})
        rows.append(
            {
                "quota_source_code": code,
                "quota_name_from_pdf": main.get("quota_name_from_pdf", ""),
                "resource_row_count": len(resources),
                "labor_resource_count": labor_count,
                "material_resource_count": material_count,
                "machine_resource_count": machine_count,
                "equipment_resource_count": equipment_count,
                "main_material_resource_count": main_material_count,
                "unknown_resource_count": unknown_count,
                "resource_labor_fee_sum": fmt_money(labor_fee),
                "resource_material_fee_sum": fmt_money(material_fee),
                "resource_machine_fee_sum": fmt_money(machine_fee),
                "resource_total_fee_sum": fmt_money(total_fee),
                "quota_labor_fee_from_main_table": fee.get("quota_labor_fee_from_main_table", main.get("labor_fee", "")),
                "quota_material_fee_from_main_table": fee.get("quota_material_fee_from_main_table", main.get("material_fee", "")),
                "quota_machine_fee_from_main_table": fee.get("quota_machine_fee_from_main_table", main.get("machine_fee", "")),
                "quota_management_fee_from_main_table": fee.get("quota_management_fee_from_main_table", main.get("management_fee", "")),
                "quota_base_price_from_main_table": fee.get("quota_base_price_from_main_table", main.get("base_price", "")),
                "delta_labor": fee.get("delta_labor", ""),
                "delta_material": fee.get("delta_material", ""),
                "delta_machine": fee.get("delta_machine", ""),
                "delta_resource_total_vs_base_price": fee.get("delta_resource_total_vs_base_price", ""),
                "resource_reconciliation_status": fee.get("resource_reconciliation_status", "no_resource_rows" if not resources else ""),
                "human_decision": "",
                "human_comment": "",
            }
        )
    return rows


def build_work_content_rows(base_main_rows: Sequence[Dict[str, str]], work_content: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    main_by_code = {row["quota_source_code"]: row for row in base_main_rows}
    blocks_by_code: DefaultDict[str, List[Dict[str, str]]] = defaultdict(list)
    for block in work_content:
        for code in parse_code_list(block):
            blocks_by_code[code].append(block)

    rows: List[Dict[str, str]] = []
    for code in base_codes():
        blocks = blocks_by_code.get(code, [])
        main = main_by_code.get(code, {})
        rows.append(
            {
                "quota_source_code": code,
                "quota_name_from_pdf": main.get("quota_name_from_pdf", ""),
                "work_content_raw": "\n\n".join(block.get("work_content_raw", "") for block in blocks if block.get("work_content_raw")),
                "work_content_normalized": "\n\n".join(block.get("work_content_normalized", "") for block in blocks if block.get("work_content_normalized")),
                "source_quota_code_start": join_unique(block.get("quota_source_code_start", "") for block in blocks),
                "source_quota_code_end": join_unique(block.get("quota_source_code_end", "") for block in blocks),
                "source_work_content_id": join_unique(block.get("source_block_id", "") for block in blocks),
                "pdf_page_no": join_unique(block.get("pdf_page_no", "") for block in blocks),
                "book_page_no": join_unique(block.get("book_page_no", "") for block in blocks),
                "parse_confidence": join_unique(block.get("parse_confidence", "") for block in blocks),
                "scope_issue": "" if blocks else "missing_work_content",
                "human_corrected_work_content": "",
                "human_comment": "",
            }
        )
    return rows


def range_applies_to_base(rule: Dict[str, str]) -> bool:
    value = rule.get("applicable_quota_code_range", "")
    return "A1-1-1" in value and "A1-1-137" in value


def build_quantity_rule_rows(base_main_rows: Sequence[Dict[str, str]], quantity_rules: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    main_by_code = {row["quota_source_code"]: row for row in base_main_rows}
    section_rules = [row for row in quantity_rules if range_applies_to_base(row)]
    rows: List[Dict[str, str]] = []
    for code in base_codes():
        main = main_by_code.get(code, {})
        rows.append(
            {
                "quota_source_code": code,
                "quota_name_from_pdf": main.get("quota_name_from_pdf", ""),
                "applicable_rule_text": "\n\n".join(row.get("rule_text_normalized") or row.get("rule_text_raw", "") for row in section_rules),
                "rule_no": join_unique(row.get("rule_no", "") for row in section_rules),
                "rule_scope": "section_level" if section_rules else "requires_manual_scope_review",
                "applicable_section": join_unique(row.get("applicable_section", "") for row in section_rules),
                "applicable_quota_code_range": join_unique(row.get("applicable_quota_code_range", "") for row in section_rules),
                "requires_manual_scope_review": "yes",
                "pdf_page_no": join_unique(row.get("pdf_page_no", "") for row in section_rules),
                "book_page_no": join_unique(row.get("book_page_no", "") for row in section_rules),
                "human_corrected_rule_scope": "",
                "human_comment": "",
            }
        )
    return rows


def build_reconciliation_rows(
    reconciliation: Sequence[Dict[str, str]],
    structured: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    recon_by_code = {row.get("quota_source_code", ""): row for row in reconciliation}
    pdf_codes = {row.get("quota_source_code", "") for row in structured}
    rows: List[Dict[str, str]] = []
    for code in all_review_codes():
        row = recon_by_code.get(code, {})
        rows.append(
            {
                "quota_source_code": code,
                "present_in_pdf": "yes" if code in pdf_codes and row.get("quota_name_from_pdf", "") else "no",
                "present_in_xlsx": "yes" if row.get("quota_name_from_xlsx", "") else "no",
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
                "match_status": row.get("match_status", ""),
                "issue_type": row.get("issue_type", ""),
                "human_decision": "",
                "human_comment": "",
            }
        )
    return rows


def build_supplemental_rows(
    reconciliation: Sequence[Dict[str, str]],
    structured: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    recon_by_code = {row.get("quota_source_code", ""): row for row in reconciliation}
    structured_by_code = {row.get("quota_source_code", ""): row for row in structured}
    nearby = {
        "A1-1-56-1": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-56-2": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-56-3": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-56-4": ["A1-1-53", "A1-1-54", "A1-1-55", "A1-1-56"],
        "A1-1-118-1": ["A1-1-117", "A1-1-118"],
        "A1-1-118-2": ["A1-1-117", "A1-1-118"],
    }
    rows: List[Dict[str, str]] = []
    for code in SUPPLEMENTAL_CODES:
        row = recon_by_code.get(code, {})
        nearby_codes = nearby[code]
        pages = sorted({structured_by_code.get(item, {}).get("pdf_page_no", "") for item in nearby_codes if structured_by_code.get(item, {}).get("pdf_page_no", "")})
        rows.append(
            {
                "supplemental_quota_code": code,
                "present_in_xlsx": "yes" if row.get("quota_name_from_xlsx") else "no",
                "present_in_pdf_candidate": "yes" if structured_by_code.get(code) else "no",
                "pdf_detected_nearby_page": ";".join(pages),
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
                "suggested_next_action": "manual_cost_department_decision_required",
                "human_decision": "",
                "human_comment": "",
            }
        )
    return rows


def issue_maps(issues: Sequence[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, bool]]:
    issue_count: Counter[str] = Counter()
    high_or_blocking: Dict[str, bool] = defaultdict(bool)
    for issue in issues:
        code = issue.get("quota_source_code", "")
        if not code:
            continue
        issue_count[code] += 1
        if issue.get("severity") in {"high", "blocking"}:
            high_or_blocking[code] = True
    return dict(issue_count), dict(high_or_blocking)


def build_coverage_rows(
    main_rows: Sequence[Dict[str, str]],
    resource_summary_rows: Sequence[Dict[str, str]],
    work_rows: Sequence[Dict[str, str]],
    rule_rows: Sequence[Dict[str, str]],
    reconciliation_rows: Sequence[Dict[str, str]],
    resource_display: Sequence[Dict[str, str]],
    issues: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    main_by_code = {row["quota_source_code"]: row for row in main_rows}
    summary_by_code = {row["quota_source_code"]: row for row in resource_summary_rows}
    work_by_code = {row["quota_source_code"]: row for row in work_rows}
    rule_by_code = {row["quota_source_code"]: row for row in rule_rows}
    recon_by_code = {row["quota_source_code"]: row for row in reconciliation_rows}
    resources_by_code: DefaultDict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in resource_display:
        resources_by_code[row.get("quota_source_code", "")].append(row)
    issue_count, high_or_blocking = issue_maps(issues)

    rows: List[Dict[str, str]] = []
    for code in all_review_codes():
        is_base = code in set(base_codes())
        is_supplement = code in set(SUPPLEMENTAL_CODES)
        main = main_by_code.get(code, {})
        summary = summary_by_code.get(code, {})
        work = work_by_code.get(code, {})
        rule = rule_by_code.get(code, {})
        recon = recon_by_code.get(code, {})
        resources = resources_by_code.get(code, [])
        resource_conf = [parse_decimal(row.get("parse_confidence")) for row in resources if row.get("parse_confidence")]
        exists_main = bool(main.get("quota_name_from_pdf"))
        exists_resources = len(resources) > 0
        exists_work = bool(work.get("work_content_raw") or work.get("work_content_normalized"))
        exists_rule = bool(rule.get("applicable_rule_text"))
        exists_recon = bool(recon)
        if is_supplement:
            status = "xlsx_only_supplemental"
        elif not exists_main:
            status = "missing_main_quota"
        elif not exists_resources:
            status = "missing_resource_detail"
        elif not exists_work:
            status = "missing_work_content"
        elif not exists_rule:
            status = "missing_quantity_rule_scope"
        elif high_or_blocking.get(code, False):
            status = "needs_manual_review"
        else:
            status = "complete_for_review"
        rows.append(
            {
                "quota_source_code": code,
                "is_expected_base_code": "yes" if is_base else "no",
                "is_supplemental_code": "yes" if is_supplement else "no",
                "exists_in_main_quota_candidate": "yes" if exists_main else "no",
                "exists_in_resource_display": "yes" if exists_resources else "no",
                "resource_row_count": summary.get("resource_row_count", len(resources) if resources else 0),
                "exists_in_resource_summary": "yes" if summary else "no",
                "exists_in_work_content_expanded": "yes" if exists_work else "no",
                "exists_in_quantity_rule_expanded": "yes" if exists_rule else "no",
                "exists_in_xlsx_reconciliation": "yes" if exists_recon else "no",
                "exists_in_issue_list": "yes" if issue_count.get(code, 0) > 0 else "no",
                "main_quota_parse_confidence": main.get("parse_confidence", ""),
                "resource_min_parse_confidence": f"{min(resource_conf):.2f}" if resource_conf else "",
                "has_high_or_blocking_issue": "yes" if high_or_blocking.get(code, False) else "no",
                "coverage_status": status,
                "human_decision": "",
                "human_comment": "",
            }
        )
    return rows


def build_summary_rows(
    main_rows: Sequence[Dict[str, str]],
    resource_display_rows: Sequence[Dict[str, str]],
    resource_summary_rows: Sequence[Dict[str, str]],
    work_rows: Sequence[Dict[str, str]],
    rule_rows: Sequence[Dict[str, str]],
    reconciliation_rows: Sequence[Dict[str, str]],
    coverage_rows: Sequence[Dict[str, str]],
    supplemental_rows: Sequence[Dict[str, str]],
) -> List[Dict[str, Any]]:
    resource_with_rows = sum(1 for row in resource_summary_rows if int(nstr(row.get("resource_row_count") or 0)) > 0)
    work_with_rows = sum(1 for row in work_rows if row.get("work_content_raw") or row.get("work_content_normalized"))
    rule_manual_count = sum(1 for row in rule_rows if row.get("requires_manual_scope_review") == "yes")
    coverage_counts = Counter(row.get("coverage_status", "") for row in coverage_rows)
    return [
        {"metric": "expected_base_codes", "value": 137, "remark": "A1-1-1..A1-1-137"},
        {"metric": "main_quota_all_rows", "value": len(main_rows), "remark": "full base-code table"},
        {"metric": "resource_display_all_rows", "value": len(resource_display_rows), "remark": "all resource display rows"},
        {"metric": "resource_summary_by_quota_rows", "value": len(resource_summary_rows), "remark": "one row per base code"},
        {"metric": "resource_quota_codes_with_rows", "value": resource_with_rows, "remark": "resource_row_count > 0"},
        {"metric": "resource_quota_codes_without_rows", "value": len(resource_summary_rows) - resource_with_rows, "remark": "resource_row_count = 0"},
        {"metric": "work_content_by_quota_rows", "value": len(work_rows), "remark": "one row per base code"},
        {"metric": "work_content_codes_with_content", "value": work_with_rows, "remark": "expanded from work-content blocks"},
        {"metric": "work_content_codes_missing_content", "value": len(work_rows) - work_with_rows, "remark": "requires human check if nonzero"},
        {"metric": "quantity_rule_by_quota_rows", "value": len(rule_rows), "remark": "one row per base code"},
        {"metric": "quantity_rule_requires_manual_scope_review", "value": rule_manual_count, "remark": "section-level rule scope"},
        {"metric": "xlsx_reconciliation_all_rows", "value": len(reconciliation_rows), "remark": "base codes plus supplemental codes"},
        {"metric": "code_coverage_matrix_rows", "value": len(coverage_rows), "remark": "base codes plus supplemental codes"},
        {"metric": "supplemental_investigation_rows", "value": len(supplemental_rows), "remark": "all xlsx-only supplemental codes"},
        {"metric": "coverage_status_counts", "value": json.dumps(dict(coverage_counts), ensure_ascii=False), "remark": "matrix distribution"},
        {"metric": "next_step_recommendation", "value": "full_review_pack_ready_but_parser_refinement_required", "remark": "full pack is ready; resource alignment and rule scope still need human confirmation"},
    ]


def build_instruction_rows() -> List[Dict[str, Any]]:
    instructions = [
        "本工作簿是 A.1.1 土石方工程全量人工核定包，不是抽样 QA 表。",
        "成本部可从 code_coverage_matrix 或 main_quota_all 按 A1-1-1 至 A1-1-137 逐条检索。",
        "main_quota_all 一编码一行，human_* 字段留空，review_status 固定为 pending。",
        "resource_display_all 保留候选资源全量 629 行，不因低置信度过滤。",
        "resource_summary_by_quota 一编码一行，显示资源数量、分类数量、费用汇总和差异。",
        "work_content_by_quota 已把原 work_content block 展开到每个定额编码。",
        "quantity_rule_by_quota 已把章节级工程量规则展开到每个定额编码，requires_manual_scope_review 表示需人工确认适用范围。",
        "xlsx_reconciliation_all 包含 137 个基础编码和 6 个 xlsx-only supplemental code。",
        "supplemental_investigation 用于确认 6 个 xlsx-only 编码的来源和后续处置。",
        "coverage_status 为 xlsx_only_supplemental 时，该编码不属于 PDF base-code candidate。",
        "coverage_status 为 needs_manual_review 时，优先核查高风险 issue 和解析置信度。",
        "请只在人审列填写人工意见，不要修改候选来源列。",
    ]
    return [{"line_no": index + 1, "instruction": text} for index, text in enumerate(instructions)]


def write_report(
    path: Path,
    input_dir: Path,
    previous_report: Path,
    output_dir: Path,
    main_rows: Sequence[Dict[str, str]],
    resource_display_rows: Sequence[Dict[str, str]],
    resource_summary_rows: Sequence[Dict[str, str]],
    work_rows: Sequence[Dict[str, str]],
    rule_rows: Sequence[Dict[str, str]],
    reconciliation_rows: Sequence[Dict[str, str]],
    coverage_rows: Sequence[Dict[str, str]],
    supplemental_rows: Sequence[Dict[str, str]],
    workbook_sheet_rows: Dict[str, int],
) -> None:
    main_missing = [row["quota_source_code"] for row in main_rows if not row.get("quota_name_from_pdf")]
    resource_without = [row["quota_source_code"] for row in resource_summary_rows if int(nstr(row.get("resource_row_count") or 0)) == 0]
    work_missing = [row["quota_source_code"] for row in work_rows if not (row.get("work_content_raw") or row.get("work_content_normalized"))]
    manual_rule_count = sum(1 for row in rule_rows if row.get("requires_manual_scope_review") == "yes")
    base_recon_rows = sum(1 for row in reconciliation_rows if row["quota_source_code"] in set(base_codes()))
    supplement_recon_rows = sum(1 for row in reconciliation_rows if row["quota_source_code"] in set(SUPPLEMENTAL_CODES))
    xlsx_only_rows = sum(1 for row in supplemental_rows if row.get("present_in_xlsx") == "yes" and row.get("present_in_pdf_candidate") == "no")
    coverage_counts = Counter(row.get("coverage_status", "") for row in coverage_rows)
    next_step = "full_review_pack_ready_but_parser_refinement_required"
    report = f"""# Stage GD2018-PDF-A111-FULL-REVIEW-PACK-1 Report

## 1. Task Scope

本轮生成 A.1.1 土石方工程全量人工核定包，不是抽样 QA 包；本轮只基于既有 candidate CSV 展开审核表，不重新解析 PDF，不写数据库，不修改候选输入，不修改 normalized Excel，不改 Web。

## 2. Inputs

- input run directory: `{input_dir}`
- previous QA report read: `{previous_report}`
- output directory: `{output_dir}`

## 3. Why Previous QA Pack Was Insufficient

上一轮 `main_quota_sample` / `resource_sample` 是抽样表，适合抽检解析质量，但不适合成本部逐条核定。A1-1-6、A1-1-7、A1-1-10 等编码未出现在抽样主项表，并不直接证明底层 candidate 缺失；本轮用全量展开表解决逐条检索和核定问题。

## 4. Full Main Quota Coverage

- expected base codes = 137
- main_quota_all rows = {len(main_rows)}
- missing main quota codes = {json.dumps(main_missing, ensure_ascii=False)}

## 5. Full Resource Coverage

- resource_display_all rows = {len(resource_display_rows)}
- quota codes with resource rows = {len(resource_summary_rows) - len(resource_without)}
- quota codes without resource rows = {len(resource_without)}
- quota codes without resource rows list = {json.dumps(resource_without, ensure_ascii=False)}

## 6. Work Content Expansion

- work_content_by_quota rows = {len(work_rows)}
- quota codes with work content = {len(work_rows) - len(work_missing)}
- quota codes missing work content = {len(work_missing)}

## 7. Quantity Rule Expansion

- quantity_rule_by_quota rows = {len(rule_rows)}
- requires_manual_scope_review count = {manual_rule_count}

## 8. Reconciliation Coverage

- base code rows = {base_recon_rows}
- supplemental code rows = {supplement_recon_rows}
- xlsx-only supplemental code rows = {xlsx_only_rows}

## 9. Code Coverage Matrix

coverage_status distribution: `{json.dumps(dict(coverage_counts), ensure_ascii=False)}`

## 10. Excel Workbook

Generated workbook: `{output_dir / "A111_PDF_Full_Review_Pack.xlsx"}`

Sheet row counts: `{json.dumps(workbook_sheet_rows, ensure_ascii=False)}`

## 11. Next Step Recommendation

{next_step}
"""
    path.write_text(report, encoding="utf-8")


def xml_text(value: Any) -> str:
    return escape(nstr(value), {'"': "&quot;"})


def to_excel_number(value: Any) -> Optional[str]:
    text = nstr(value).strip().replace(",", "")
    if not text or text in {"-", "—"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number.is_integer():
        return str(int(number))
    return repr(number)


def is_text_field(field: str) -> bool:
    return field in TEXT_CODE_FIELDS or field.endswith("_code") or field.endswith("_id") or field.startswith("is_") or field.startswith("exists_") or field.startswith("has_")


def excel_col(index: int) -> str:
    number = index + 1
    label = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(65 + remainder) + label
    return label


def cell_xml(row_index: int, col_index: int, field: str, value: Any, header: bool = False) -> str:
    ref = f"{excel_col(col_index)}{row_index}"
    if header:
        return f'<c r="{ref}" s="1" t="inlineStr"><is><t>{xml_text(value)}</t></is></c>'
    if value is None or nstr(value) == "":
        return f'<c r="{ref}"/>'
    if field in NUMERIC_FIELDS and not is_text_field(field):
        number = to_excel_number(value)
        if number is not None:
            return f'<c r="{ref}"><v>{number}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_text(value)}</t></is></c>'


def column_width(field: str, values: Sequence[Dict[str, Any]]) -> float:
    if field in {"applicable_rule_text", "work_content_raw", "work_content_normalized", "raw_row_json"}:
        return 70.0
    if field in {"instruction", "remark", "issue_type", "coverage_status"}:
        return 44.0
    if field in {"quota_name_from_pdf", "quota_name_full_from_pdf", "quota_name_from_xlsx", "resource_name", "resource_spec"}:
        return 32.0
    max_len = len(field)
    for row in values[:200]:
        max_len = max(max_len, len(nstr(row.get(field, ""))))
    return min(max(max_len + 2, 10), 28)


def sheet_xml(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    max_row = len(rows) + 1
    max_col = len(headers)
    last_ref = f"{excel_col(max_col - 1)}{max_row}"
    cols = []
    for index, field in enumerate(headers, start=1):
        width = column_width(field, rows)
        cols.append(f'<col min="{index}" max="{index}" width="{width:.2f}" customWidth="1"/>')
    row_xml: List[str] = []
    header_cells = "".join(cell_xml(1, index, field, field, header=True) for index, field in enumerate(headers))
    row_xml.append(f'<row r="1" spans="1:{max_col}">{header_cells}</row>')
    for row_number, row in enumerate(rows, start=2):
        cells = "".join(cell_xml(row_number, index, field, row.get(field, "")) for index, field in enumerate(headers))
        row_xml.append(f'<row r="{row_number}" spans="1:{max_col}">{cells}</row>')
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:{last_ref}"/>
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
      <selection pane="bottomLeft" activeCell="A2" sqref="A2"/>
    </sheetView>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>{''.join(cols)}</cols>
  <sheetData>{''.join(row_xml)}</sheetData>
  <autoFilter ref="A1:{last_ref}"/>
</worksheet>'''


def styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def write_xlsx(path: Path, sheets: Sequence[Tuple[str, Sequence[str], Sequence[Dict[str, Any]]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook_sheets = []
    workbook_rels = []
    content_overrides = []
    for index, (name, _headers, _rows) in enumerate(sheets, start=1):
        workbook_sheets.append(f'<sheet name="{xml_text(name)}" sheetId="{index}" r:id="rId{index}"/>')
        workbook_rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
        content_overrides.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    style_rel_id = len(sheets) + 1
    workbook_rels.append(f'<Relationship Id="rId{style_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>{''.join(workbook_sheets)}</sheets>
</workbook>'''
    workbook_rels_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(workbook_rels)}</Relationships>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {''.join(content_overrides)}
</Types>'''
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>A111 PDF Full Review Pack</dc:title>
  <dc:creator>AI Construction System</dc:creator>
  <cp:lastModifiedBy>AI Construction System</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''
    app_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>AI Construction System</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>{len(sheets)}</vt:i4></vt:variant></vt:vector></HeadingPairs>
  <TitlesOfParts><vt:vector size="{len(sheets)}" baseType="lpstr">{''.join(f"<vt:lpstr>{xml_text(name)}</vt:lpstr>" for name, _headers, _rows in sheets)}</vt:vector></TitlesOfParts>
  <Company>AI Construction System</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0300</AppVersion>
</Properties>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", styles_xml())
        for index, (_name, headers, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(headers, rows))


def run(project_root: Path) -> Dict[str, Path]:
    input_dir = project_root / INPUT_DIR_REL
    previous_report = project_root / PREVIOUS_QA_DIR_REL / "stage_gd2018_pdf_a111_qa_pack_report.md"
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    structured_path = input_dir / "quota_pdf_structured_A111_candidate.csv"
    resource_display_path = input_dir / "quota_pdf_resource_display_A111_candidate.csv"
    required_input_names = [
        "quota_pdf_structured_A111_candidate.csv",
        "quota_pdf_resource_detail_A111_candidate.csv",
        "quota_pdf_resource_display_A111_candidate.csv",
        "quota_pdf_resource_fee_summary_A111.csv",
        "quota_pdf_work_content_A111_candidate.csv",
        "quota_pdf_quantity_rule_A111_candidate.csv",
        "quota_pdf_xlsx_reconciliation_A111.csv",
        "quota_pdf_extraction_issues_A111.csv",
        "stage_gd2018_pdf_a111_structured_candidate_report.md",
    ]
    for name in required_input_names:
        if not (input_dir / name).exists():
            raise FileNotFoundError(input_dir / name)
    if not previous_report.exists():
        raise FileNotFoundError(previous_report)
    previous_report.read_text(encoding="utf-8")

    structured = read_csv(structured_path)
    resource_display = read_csv(resource_display_path)
    resource_display_headers = read_headers(resource_display_path)
    fee_summary = read_csv(input_dir / "quota_pdf_resource_fee_summary_A111.csv")
    work_content = read_csv(input_dir / "quota_pdf_work_content_A111_candidate.csv")
    quantity_rule = read_csv(input_dir / "quota_pdf_quantity_rule_A111_candidate.csv")
    reconciliation = read_csv(input_dir / "quota_pdf_xlsx_reconciliation_A111.csv")
    issues = read_csv(input_dir / "quota_pdf_extraction_issues_A111.csv")

    main_rows = build_main_rows(structured)
    resource_fields, resource_display_rows = build_resource_display_rows(resource_display, resource_display_headers)
    resource_summary_rows = build_resource_summary_rows(main_rows, resource_display, fee_summary)
    work_rows = build_work_content_rows(main_rows, work_content)
    rule_rows = build_quantity_rule_rows(main_rows, quantity_rule)
    reconciliation_rows = build_reconciliation_rows(reconciliation, structured)
    coverage_rows = build_coverage_rows(main_rows, resource_summary_rows, work_rows, rule_rows, reconciliation_rows, resource_display, issues)
    supplemental_rows = build_supplemental_rows(reconciliation, structured)
    summary_rows = build_summary_rows(
        main_rows,
        resource_display_rows,
        resource_summary_rows,
        work_rows,
        rule_rows,
        reconciliation_rows,
        coverage_rows,
        supplemental_rows,
    )
    instruction_rows = build_instruction_rows()

    paths = {
        "xlsx": output_dir / "A111_PDF_Full_Review_Pack.xlsx",
        "main": output_dir / "main_quota_all_137.csv",
        "resource_display": output_dir / "resource_display_all_629.csv",
        "resource_summary": output_dir / "resource_summary_by_quota_137.csv",
        "work_content": output_dir / "work_content_by_quota_137.csv",
        "quantity_rule": output_dir / "quantity_rule_by_quota_137.csv",
        "reconciliation": output_dir / "xlsx_reconciliation_all_A111.csv",
        "coverage": output_dir / "code_coverage_matrix_A111.csv",
        "supplemental": output_dir / "supplemental_investigation_6.csv",
        "report": output_dir / "stage_gd2018_pdf_a111_full_review_pack_report.md",
    }

    write_csv(paths["main"], MAIN_FIELDS, main_rows)
    write_csv(paths["resource_display"], resource_fields, resource_display_rows)
    write_csv(paths["resource_summary"], RESOURCE_SUMMARY_FIELDS, resource_summary_rows)
    write_csv(paths["work_content"], WORK_CONTENT_FIELDS, work_rows)
    write_csv(paths["quantity_rule"], QUANTITY_RULE_FIELDS, rule_rows)
    write_csv(paths["reconciliation"], RECONCILIATION_FIELDS, reconciliation_rows)
    write_csv(paths["coverage"], COVERAGE_FIELDS, coverage_rows)
    write_csv(paths["supplemental"], SUPPLEMENTAL_FIELDS, supplemental_rows)

    workbook_sheets = [
        ("summary", SUMMARY_FIELDS, summary_rows),
        ("code_coverage_matrix", COVERAGE_FIELDS, coverage_rows),
        ("main_quota_all", MAIN_FIELDS, main_rows),
        ("resource_summary_by_quota", RESOURCE_SUMMARY_FIELDS, resource_summary_rows),
        ("resource_display_all", resource_fields, resource_display_rows),
        ("work_content_by_quota", WORK_CONTENT_FIELDS, work_rows),
        ("quantity_rule_by_quota", QUANTITY_RULE_FIELDS, rule_rows),
        ("xlsx_reconciliation_all", RECONCILIATION_FIELDS, reconciliation_rows),
        ("supplemental_investigation", SUPPLEMENTAL_FIELDS, supplemental_rows),
        ("instructions", INSTRUCTION_FIELDS, instruction_rows),
    ]
    write_xlsx(paths["xlsx"], workbook_sheets)
    workbook_sheet_rows = {sheet_name: len(rows) for sheet_name, _fields, rows in workbook_sheets}
    write_report(
        paths["report"],
        input_dir,
        previous_report,
        output_dir,
        main_rows,
        resource_display_rows,
        resource_summary_rows,
        work_rows,
        rule_rows,
        reconciliation_rows,
        coverage_rows,
        supplemental_rows,
        workbook_sheet_rows,
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
    print("Generated A.1.1 full review pack artifacts:")
    for name, path in paths.items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
