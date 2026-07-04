#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage 2A sample extractor for A.1.1 土石方工程.

This script extracts a bounded sample pack of main rows only. A main row is one
A1-1-* quota item code. Resource rows/codes, prices, quantities, labor/material/
machine consumption rows, and cost components are filtered from the candidate
sample output.

The script does not write databases, does not touch migrations or the existing
pipeline, and does not generate approved records or internal_price_library data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pdfplumber

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover - optional output
    Workbook = None

DEFAULT_PDF_PATH = Path(
    r"C:\Users\haozh\Downloads\1. 广东省房屋建筑与装饰工程定额20190112(上册).pdf"
)
SOURCE_TYPE = "provincial_quota_pdf"
SOURCE_NAME = "广东省房屋建筑与装饰工程综合定额2018"
CHAPTER_CODE = "A.1.1"
CHAPTER_NAME = "土石方工程"
REVIEW_STATUS = "pending"
UNIT_GLYPH = "\ue000"

SAMPLE_PAGES: Dict[str, List[int]] = {
    "A.1.1.1": [59, 60, 67, 70, 75, 79],
    "A.1.1.2": [80, 82, 91, 95],
    "A.1.1.3": [96, 97, 99],
}

SECTION_NAMES = {
    "A.1.1.1": "土方工程",
    "A.1.1.2": "石方工程",
    "A.1.1.3": "回填方及其他",
}

TABLE_INVENTORY_FIELDS = [
    "inventory_id",
    "source_type",
    "source_name",
    "source_file",
    "source_file_hash",
    "source_page",
    "chapter_code",
    "chapter_name",
    "section_code",
    "section_name",
    "item_group_name",
    "work_content_raw",
    "unit_raw",
    "unit_candidate",
    "source_code_list",
    "source_code_count",
    "table_text_sample",
    "extraction_method",
    "extraction_confidence",
    "parse_issue",
    "remark",
]

RAW_EXTRACT_FIELDS = [
    "raw_extract_id",
    "source_type",
    "source_name",
    "source_file",
    "source_file_hash",
    "source_page",
    "chapter_code",
    "chapter_name",
    "section_code",
    "section_name",
    "table_index_on_page",
    "raw_text_block",
    "raw_code_tokens",
    "raw_name_tokens",
    "raw_unit_tokens",
    "parse_issue",
    "extraction_confidence",
    "remark",
]

CANDIDATE_FIELDS = [
    "reference_id",
    "source_type",
    "source_name",
    "source_file",
    "source_file_hash",
    "source_page",
    "chapter_code",
    "chapter_name",
    "section_code",
    "section_name",
    "item_group_name",
    "source_code",
    "raw_name",
    "standard_name_candidate",
    "unit",
    "work_content",
    "keywords",
    "aliases",
    "feature_template",
    "extraction_confidence",
    "review_status",
    "reviewer",
    "remark",
]

ISSUE_FIELDS = [
    "issue_id",
    "source_page",
    "section_code",
    "issue_type",
    "issue_detail",
    "affected_source_codes",
    "severity",
    "suggested_action",
]


@dataclass
class ParsedTable:
    page: int
    table_index: int
    section_code: str
    section_name: str
    item_group_name: str
    work_content: str
    unit_raw: str
    unit_candidate: str
    codes: List[str]
    names_by_code: Dict[str, str]
    units_by_code: Dict[str, str]
    name_part_counts: Dict[str, int]
    parse_issues: List[str]
    raw_text: str
    raw_name_tokens: List[str]
    raw_unit_tokens: List[str]
    confidence: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def compact_text(value: Optional[str], limit: Optional[int] = None) -> str:
    if not value:
        return ""
    compacted = re.sub(r"\s+", " ", str(value)).strip()
    return compacted[:limit] if limit else compacted


def clean_cell(value: Any) -> str:
    return compact_text(value).replace("\n", " ").strip()


def lightly_normalize_name(value: str) -> str:
    text = compact_text(value)
    text = re.sub(r"\s+([、，。；：）)])", r"\1", text)
    text = re.sub(r"([（(])\s+", r"\1", text)
    return text.replace("、 ", "、").strip()


def unit_candidate_from_raw(unit_raw: str) -> str:
    return unit_raw.replace(UNIT_GLYPH, "m3") if unit_raw else ""


def has_unit_glyph(value: str) -> bool:
    return UNIT_GLYPH in (value or "")


def is_source_code(value: str) -> bool:
    return bool(re.fullmatch(r"A1-\d+-\d+", value or ""))


def resource_codes_in_text(text: str) -> List[str]:
    tokens = re.findall(r"\b(?:0\d{7}|9\d{8})\b", text or "")
    return sorted(set(tokens))


def is_unit_like(value: str) -> bool:
    if not value:
        return False
    text = value.strip()
    unit_re = r"(?:\d+(?:\.\d+)?\s*)?(?:㎡|m2|m3|元|台班|工日|" + UNIT_GLYPH + r")+"
    return bool(re.fullmatch(unit_re, text))


def extract_between(text: str, start_marker: str, end_marker: str) -> str:
    pattern = re.escape(start_marker) + r"(.*?)" + re.escape(end_marker)
    match = re.search(pattern, text, flags=re.S)
    return compact_text(match.group(1)) if match else ""


def extract_unit_raw(text: str) -> str:
    return extract_between(text, "计量单位：", "定额编号")


def extract_work_content(text: str) -> str:
    return extract_between(text, "工作内容：", "计量单位：")


def extract_item_group(text: str, section_code: str, section_name: str) -> str:
    before_work = compact_text(text.split("工作内容：", 1)[0])
    cleanup_tokens = [
        "A.1.1 土石方工程",
        f"{section_code} {section_name}",
        section_code,
        section_name,
    ]
    for token in cleanup_tokens:
        before_work = before_work.replace(token, " ")
    return compact_text(before_work) or section_name


def find_code_row(table: Sequence[Sequence[Any]]) -> Optional[int]:
    for row_index, row in enumerate(table):
        if any(is_source_code(clean_cell(cell)) for cell in row):
            return row_index
    return None


def find_name_row(table: Sequence[Sequence[Any]], start_index: int) -> Optional[int]:
    for row_index in range(start_index, len(table)):
        row_text = " ".join(clean_cell(cell) for cell in table[row_index])
        if "子目名称" in row_text:
            return row_index
    return None


def find_base_row(table: Sequence[Sequence[Any]], start_index: int) -> int:
    for row_index in range(start_index, len(table)):
        row_text = " ".join(clean_cell(cell) for cell in table[row_index])
        if "基价" in row_text:
            return row_index
    return len(table)


def horizontal_fill(
    row: Sequence[Any],
    source_cols: Sequence[int],
    previous_filled_rows: Optional[Sequence[Dict[int, str]]] = None,
) -> Dict[int, str]:
    filled: Dict[int, str] = {}
    current = ""
    current_col: Optional[int] = None
    for col in source_cols:
        value = clean_cell(row[col]) if col < len(row) else ""
        if value:
            current = value
            current_col = col
            filled[col] = current
            continue
        allowed_to_span = bool(current)
        if allowed_to_span and current_col is not None and previous_filled_rows:
            for previous in previous_filled_rows:
                if previous.get(col, "") != previous.get(current_col, ""):
                    allowed_to_span = False
                    break
        filled[col] = current if allowed_to_span else ""
    return filled


def extract_code_columns(code_row: Sequence[Any]) -> List[Tuple[int, str]]:
    code_cols: List[Tuple[int, str]] = []
    for col, cell in enumerate(code_row):
        value = clean_cell(cell)
        if is_source_code(value):
            code_cols.append((col, value))
    return code_cols


def parse_names_and_units(
    table: Sequence[Sequence[Any]],
    code_cols: Sequence[Tuple[int, str]],
    name_start: int,
    base_row: int,
    unit_raw: str,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, int], List[str], List[str], List[str]]:
    source_cols = [col for col, _ in code_cols]
    code_by_col = {col: code for col, code in code_cols}
    name_parts: Dict[str, List[str]] = {code: [] for _, code in code_cols}
    units_by_code: Dict[str, str] = {}
    raw_name_tokens: List[str] = []
    raw_unit_tokens: List[str] = [unit_raw] if unit_raw else []
    parse_issues: List[str] = []

    previous_filled_rows: List[Dict[int, str]] = []
    for row_index in range(name_start, base_row):
        row = table[row_index]
        values = [clean_cell(row[col]) if col < len(row) else "" for col in source_cols]
        non_empty_values = [value for value in values if value]
        unit_row = bool(non_empty_values) and all(is_unit_like(value) for value in non_empty_values)
        if unit_raw == "见表" and unit_row:
            for col, value in zip(source_cols, values):
                if value:
                    units_by_code[code_by_col[col]] = value
                    raw_unit_tokens.append(value)
            continue

        filled = horizontal_fill(row, source_cols, previous_filled_rows)
        previous_filled_rows.append(filled)
        for col, code in code_cols:
            value = filled.get(col, "")
            if not value or value == "子目名称":
                continue
            if value not in raw_name_tokens:
                raw_name_tokens.append(value)
            if not name_parts[code] or name_parts[code][-1] != value:
                name_parts[code].append(value)

    names_by_code = {code: lightly_normalize_name(" ".join(parts)) for code, parts in name_parts.items()}
    part_counts = {code: len([part for part in parts if part]) for code, parts in name_parts.items()}
    if any(count > 1 for count in part_counts.values()):
        parse_issues.append("multi_line_name")
    return names_by_code, units_by_code, part_counts, raw_name_tokens, raw_unit_tokens, parse_issues


def table_confidence(parse_issues: Iterable[str], unit_raw: str) -> float:
    issues = set(parse_issues)
    confidence = 0.94
    if "multi_line_name" in issues:
        confidence = min(confidence, 0.86)
    if has_unit_glyph(unit_raw) or "unit_glyph_issue" in issues:
        confidence = min(confidence, 0.72)
    if "missing_work_content" in issues or "missing_unit" in issues:
        confidence = min(confidence, 0.68)
    if "missing_name" in issues:
        confidence = min(confidence, 0.45)
    return confidence


def candidate_confidence(table: ParsedTable, source_code: str) -> float:
    confidence = table.confidence
    if table.name_part_counts.get(source_code, 0) > 1:
        confidence = min(confidence, 0.86)
    unit = table.units_by_code.get(source_code) or table.unit_raw
    if has_unit_glyph(unit):
        confidence = min(confidence, 0.72)
    if not table.work_content:
        confidence = min(confidence, 0.68)
    if not table.names_by_code.get(source_code):
        confidence = min(confidence, 0.45)
    return confidence


def keywordize(name: str, item_group: str) -> str:
    source = f"{item_group} {name}"
    tokens = [token for token in re.split(r"[\s、，；;（）()]+", source) if len(token) >= 2]
    seen = set()
    result = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            result.append(token)
    return ";".join(result[:8])


def section_for_page(page: int) -> Tuple[str, str]:
    for section_code, pages in SAMPLE_PAGES.items():
        if page in pages:
            return section_code, SECTION_NAMES[section_code]
    raise ValueError(f"Page {page} is outside the Stage 2A sample plan")


def parse_selected_table(page_obj: Any, page_num: int, table_index: int, table: Sequence[Sequence[Any]]) -> Optional[ParsedTable]:
    text = page_obj.extract_text() or ""
    section_code, section_name = section_for_page(page_num)
    code_row_index = find_code_row(table)
    if code_row_index is None:
        return None
    code_cols = extract_code_columns(table[code_row_index])
    if not code_cols:
        return None
    name_row_index = find_name_row(table, code_row_index + 1)
    if name_row_index is None:
        return None
    base_row_index = find_base_row(table, name_row_index + 1)

    item_group_name = extract_item_group(text, section_code, section_name)
    work_content = extract_work_content(text)
    unit_raw = extract_unit_raw(text)
    unit_candidate = unit_candidate_from_raw(unit_raw)

    names_by_code, units_by_code, part_counts, raw_name_tokens, raw_unit_tokens, name_issues = parse_names_and_units(
        table, code_cols, name_row_index, base_row_index, unit_raw
    )

    parse_issues = list(name_issues)
    if has_unit_glyph(unit_raw) or any(has_unit_glyph(unit) for unit in units_by_code.values()):
        parse_issues.append("unit_glyph_issue")
    if any(cell is None for row in table[: max(base_row_index, 1)] for cell in row):
        parse_issues.append("merged_header")
    if not work_content:
        parse_issues.append("missing_work_content")
    if not unit_raw:
        parse_issues.append("missing_unit")
    if any(not names_by_code.get(code) for _, code in code_cols):
        parse_issues.append("missing_name")
    if resource_codes_in_text(text):
        parse_issues.append("resource_code_filtered")

    confidence = table_confidence(parse_issues, unit_raw)
    return ParsedTable(
        page=page_num,
        table_index=table_index,
        section_code=section_code,
        section_name=section_name,
        item_group_name=item_group_name,
        work_content=work_content,
        unit_raw=unit_raw,
        unit_candidate=unit_candidate,
        codes=[code for _, code in code_cols],
        names_by_code=names_by_code,
        units_by_code=units_by_code,
        name_part_counts=part_counts,
        parse_issues=sorted(set(parse_issues)),
        raw_text=compact_text(text, 2000),
        raw_name_tokens=raw_name_tokens,
        raw_unit_tokens=raw_unit_tokens,
        confidence=confidence,
    )


def parse_sample_tables(pdf_path: Path) -> List[ParsedTable]:
    parsed_tables: List[ParsedTable] = []
    selected_pages = [page for pages in SAMPLE_PAGES.values() for page in pages]
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num in selected_pages:
            page = pdf.pages[page_num - 1]
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                parsed = parse_selected_table(page, page_num, table_index, table)
                if parsed:
                    parsed_tables.append(parsed)
                    break
    return parsed_tables


def table_to_inventory(parsed: ParsedTable, pdf_path: Path, source_hash: str) -> Dict[str, Any]:
    return {
        "inventory_id": f"INV_A111_P{parsed.page}_T{parsed.table_index}",
        "source_type": SOURCE_TYPE,
        "source_name": SOURCE_NAME,
        "source_file": pdf_path.name,
        "source_file_hash": source_hash,
        "source_page": parsed.page,
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": parsed.section_code,
        "section_name": parsed.section_name,
        "item_group_name": parsed.item_group_name,
        "work_content_raw": parsed.work_content,
        "unit_raw": parsed.unit_raw,
        "unit_candidate": parsed.unit_candidate,
        "source_code_list": ";".join(parsed.codes),
        "source_code_count": len(parsed.codes),
        "table_text_sample": compact_text(parsed.raw_text, 350),
        "extraction_method": "pdfplumber.extract_tables + page_text_context",
        "extraction_confidence": f"{parsed.confidence:.2f}",
        "parse_issue": ";".join(parsed.parse_issues),
        "remark": "Stage 2A sample table/group only; not full extraction.",
    }


def table_to_raw_extract(parsed: ParsedTable, pdf_path: Path, source_hash: str) -> Dict[str, Any]:
    return {
        "raw_extract_id": f"RAW_A111_P{parsed.page}_T{parsed.table_index}",
        "source_type": SOURCE_TYPE,
        "source_name": SOURCE_NAME,
        "source_file": pdf_path.name,
        "source_file_hash": source_hash,
        "source_page": parsed.page,
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": parsed.section_code,
        "section_name": parsed.section_name,
        "table_index_on_page": parsed.table_index,
        "raw_text_block": parsed.raw_text,
        "raw_code_tokens": ";".join(parsed.codes),
        "raw_name_tokens": ";".join(parsed.raw_name_tokens),
        "raw_unit_tokens": ";".join(token for token in parsed.raw_unit_tokens if token),
        "parse_issue": ";".join(parsed.parse_issues),
        "extraction_confidence": f"{parsed.confidence:.2f}",
        "remark": "Raw table-level sample extract; contains context but not database-ready enterprise standard names.",
    }


def table_to_candidates(parsed: ParsedTable, pdf_path: Path, source_hash: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source_code in parsed.codes:
        raw_name = parsed.names_by_code.get(source_code, "")
        standard_name_candidate = lightly_normalize_name(raw_name)
        unit = parsed.units_by_code.get(source_code) or parsed.unit_raw
        issues = []
        if parsed.name_part_counts.get(source_code, 0) > 1:
            issues.append("multi_line_name")
        if has_unit_glyph(unit):
            issues.append("unit_glyph_issue")
        if not parsed.work_content:
            issues.append("missing_work_content")
        if not raw_name:
            issues.append("missing_name")
        if "merged_header" in parsed.parse_issues:
            issues.append("merged_header")
        confidence = candidate_confidence(parsed, source_code)
        rows.append(
            {
                "reference_id": f"GD2018_A111_{source_code}",
                "source_type": SOURCE_TYPE,
                "source_name": SOURCE_NAME,
                "source_file": pdf_path.name,
                "source_file_hash": source_hash,
                "source_page": parsed.page,
                "chapter_code": CHAPTER_CODE,
                "chapter_name": CHAPTER_NAME,
                "section_code": parsed.section_code,
                "section_name": parsed.section_name,
                "item_group_name": parsed.item_group_name,
                "source_code": source_code,
                "raw_name": raw_name,
                "standard_name_candidate": standard_name_candidate,
                "unit": unit,
                "work_content": parsed.work_content,
                "keywords": keywordize(standard_name_candidate, parsed.item_group_name),
                "aliases": "",
                "feature_template": "",
                "extraction_confidence": f"{confidence:.2f}",
                "review_status": REVIEW_STATUS,
                "reviewer": "",
                "remark": ";".join(sorted(set(issues))) or "Stage 2A sample candidate; pending human review.",
            }
        )
    return rows


def build_issues(parsed_tables: List[ParsedTable]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []

    def add_issue(page: int, section_code: str, issue_type: str, detail: str, codes: Iterable[str], severity: str, action: str) -> None:
        issues.append(
            {
                "issue_id": f"ISSUE_A111_{len(issues) + 1:03d}",
                "source_page": page,
                "section_code": section_code,
                "issue_type": issue_type,
                "issue_detail": detail,
                "affected_source_codes": ";".join(codes),
                "severity": severity,
                "suggested_action": action,
            }
        )

    for parsed in parsed_tables:
        codes = parsed.codes
        if "unit_glyph_issue" in parsed.parse_issues:
            add_issue(
                parsed.page,
                parsed.section_code,
                "unit_glyph_issue",
                f"Unit text contains private-use glyph in raw unit tokens: {';'.join(parsed.raw_unit_tokens)}",
                codes,
                "medium",
                "Manually confirm whether the glyph represents m3 or another unit before Stage 2B normalization.",
            )
        if "multi_line_name" in parsed.parse_issues:
            add_issue(
                parsed.page,
                parsed.section_code,
                "multi_line_name",
                "Candidate names were assembled from merged/multi-line subitem headers.",
                codes,
                "medium",
                "Review raw_name against the PDF before accepting the join rule for full extraction.",
            )
        if "merged_header" in parsed.parse_issues:
            add_issue(
                parsed.page,
                parsed.section_code,
                "merged_header",
                "pdfplumber table contains merged header cells represented as blanks/None.",
                codes,
                "medium",
                "Keep column-level visual QA for this page when moving to Stage 2B.",
            )
        resources = resource_codes_in_text(parsed.raw_text)
        if resources:
            add_issue(
                parsed.page,
                parsed.section_code,
                "resource_code_filtered",
                "Resource codes were present in raw text but filtered from candidate source_code.",
                codes,
                "low",
                "Confirm source_code column accepts only A1-1-* quota numbers.",
            )
        if parsed.confidence < 0.75:
            add_issue(
                parsed.page,
                parsed.section_code,
                "low_confidence",
                f"Table confidence is {parsed.confidence:.2f} due to parse issues: {';'.join(parsed.parse_issues)}",
                codes,
                "medium",
                "Prioritize this table during manual QA.",
            )

    for page, section_code in [(54, "A.1.1"), (58, "A.1.1_RULES"), (100, "A.1.1.3"), (102, "A.1.1.3")]:
        add_issue(
            page,
            section_code,
            "no_extractable_text",
            "Stage 1 identified this page as having no extractable text.",
            [],
            "low",
            "No Stage 2A candidates are taken from this page; visually review only if boundary/content completeness is questioned.",
        )
    add_issue(
        101,
        "A.1.1.3",
        "boundary_page",
        "Stage 1 found an A.1.2 divider title on pdf_page 101; Stage 2A does not extract candidates from this page.",
        [],
        "high",
        "Keep page 101 as a boundary QA checkpoint and exclude it from A.1.1.3 item extraction.",
    )
    return issues


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path: Path, sheets: Sequence[Tuple[str, Sequence[str], Sequence[Dict[str, Any]]]]) -> bool:
    if Workbook is None:
        return False
    wb = Workbook()
    wb.remove(wb.active)
    for sheet_name, fields, rows in sheets:
        ws = wb.create_sheet(title=sheet_name[:31])
        ws.append(list(fields))
        for row in rows:
            ws.append([row.get(field, "") for field in fields])
        for col in ws.columns:
            max_length = max(len(str(cell.value or "")) for cell in col[:100])
            ws.column_dimensions[col[0].column_letter].width = min(max(max_length + 2, 12), 48)
    wb.save(path)
    return True


def markdown_count_table(counter: Counter) -> str:
    lines = ["| Section | Count |", "|---|---:|"]
    for key in sorted(counter.keys()):
        lines.append(f"| {key} | {counter[key]} |")
    return "\n".join(lines)


def write_report(
    path: Path,
    pdf_path: Path,
    registry_path: Path,
    source_hash: str,
    inventory_rows: List[Dict[str, Any]],
    candidate_rows: List[Dict[str, Any]],
    issue_rows: List[Dict[str, Any]],
    xlsx_created: bool,
) -> None:
    candidate_section_counts = Counter(row["section_code"] for row in candidate_rows)
    table_section_counts = Counter(row["section_code"] for row in inventory_rows)
    issue_counts = Counter(row["issue_type"] for row in issue_rows)

    required_candidate_fields = [
        "reference_id",
        "source_type",
        "source_name",
        "source_file",
        "source_file_hash",
        "source_page",
        "chapter_code",
        "chapter_name",
        "section_code",
        "section_name",
        "source_code",
        "raw_name",
        "standard_name_candidate",
        "extraction_confidence",
        "review_status",
    ]
    missing = []
    for idx, row in enumerate(candidate_rows, start=1):
        for field in required_candidate_fields:
            if not str(row.get(field, "")).strip():
                missing.append(f"row {idx} missing {field}")
    invalid_codes = [row["source_code"] for row in candidate_rows if not is_source_code(row["source_code"])]
    non_pending = [row["source_code"] for row in candidate_rows if row.get("review_status") != REVIEW_STATUS]
    a12_rows = [row["source_code"] for row in candidate_rows if row.get("section_code") == "A.1.2"]

    go = (
        30 <= len(candidate_rows) <= 50
        and candidate_section_counts["A.1.1.1"] >= 15
        and candidate_section_counts["A.1.1.2"] >= 10
        and candidate_section_counts["A.1.1.3"] >= 5
        and len(inventory_rows) >= 6
        and not missing
        and not invalid_codes
        and not non_pending
        and not a12_rows
    )

    lines = [
        "# Stage 2A Sample Extraction Report - A.1.1 土石方工程",
        "",
        "## 1. Task Scope",
        "",
        "Stage 2A extracts a bounded main row sample pack only. A main row is one `A1-1-*` quota item. This run does not perform full extraction, does not write any database, does not modify migrations or the existing pipeline, and does not generate approved data or `internal_price_library`.",
        "",
        "## 2. Input Files",
        "",
        f"- target_pdf: `{pdf_path}`",
        f"- source_file_hash: `{source_hash}`",
        f"- stage1_registry: `{registry_path}`",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- xlsx_created: {xlsx_created}",
        "",
        "## 3. Page Registry Used",
        "",
        "- A.1.1.1 土方工程: pdf_page 59-79",
        "- A.1.1.2 石方工程: pdf_page 80-95",
        "- A.1.1.3 回填方及其他: pdf_page 96-102",
        "- A.1.2 STOP_BOUNDARY: pdf_page 103",
        "- pdf_page 101 is treated as boundary QA only and is not extracted as A.1.1.3 sample data.",
        "",
        "## 4. Sampling Strategy",
        "",
        "- Sample pages were selected from each section's start, middle, and boundary-near area.",
        "- A.1.1.1 sample pages: 59, 60, 67, 70, 75, 79.",
        "- A.1.1.2 sample pages: 80, 82, 91, 95.",
        "- A.1.1.3 sample pages: 96, 97, 99.",
        "- Pages 100-102 were not used for candidates because Stage 1 identified no-text/boundary concerns.",
        "",
        "## 5. Table Inventory Summary",
        "",
        f"- table_inventory_rows: {len(inventory_rows)}",
        markdown_count_table(table_section_counts),
        "",
        "## 6. Candidate Row Summary",
        "",
        f"- candidate_rows: {len(candidate_rows)}",
        markdown_count_table(candidate_section_counts),
        "",
        "## 7. Section Coverage",
        "",
        "- A.1.1.1 target >= 15: " + str(candidate_section_counts["A.1.1.1"]),
        "- A.1.1.2 target >= 10: " + str(candidate_section_counts["A.1.1.2"]),
        "- A.1.1.3 target >= 5: " + str(candidate_section_counts["A.1.1.3"]),
        "- All three sections have at least two table/group samples.",
        "",
        "## 8. Field Completeness Check",
        "",
        f"- missing_required_candidate_fields: {'; '.join(missing) if missing else 'none'}",
        f"- invalid_source_codes: {'; '.join(invalid_codes) if invalid_codes else 'none'}",
        f"- non_pending_review_status: {'; '.join(non_pending) if non_pending else 'none'}",
        f"- A.1.2_candidate_rows: {'; '.join(a12_rows) if a12_rows else 'none'}",
        "",
        "## 9. Parse Issues",
        "",
        markdown_count_table(issue_counts),
        "",
        "Major issues are unit glyphs, merged/multi-line headers, resource code filtering, and boundary/no-text pages inherited from Stage 1.",
        "",
        "## 10. Manual QA Checklist",
        "",
        "- Confirm `source_page` can be located in the source PDF.",
        "- Confirm `source_code` is a real `A1-1-*` quota item number.",
        "- Confirm no resource codes such as `00010010` or `990123010` entered `source_code`.",
        "- Confirm `raw_name` is close to the PDF text.",
        "- Confirm `standard_name_candidate` is only lightly normalized and not an invented enterprise standard name.",
        "- Confirm `unit` is correct or unit glyph issues are marked.",
        "- Confirm `work_content` is inherited from the correct table/group.",
        "- Confirm all `review_status` values are `pending`.",
        "",
        "## 11. Go / No-Go Recommendation for Stage 2B Full Extraction",
        "",
        "Go for Stage 2B full extraction after manual QA of this sample pack." if go else "No-Go until the failed checks above are fixed.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def validate_outputs(candidate_rows: List[Dict[str, Any]], inventory_rows: List[Dict[str, Any]]) -> None:
    if not 30 <= len(candidate_rows) <= 50:
        raise SystemExit(f"Candidate sample count out of range: {len(candidate_rows)}")
    counts = Counter(row["section_code"] for row in candidate_rows)
    if counts["A.1.1.1"] < 15 or counts["A.1.1.2"] < 10 or counts["A.1.1.3"] < 5:
        raise SystemExit(f"Section coverage failed: {dict(counts)}")
    if len(inventory_rows) < 6:
        raise SystemExit(f"Table inventory count below minimum: {len(inventory_rows)}")
    table_counts = Counter(row["section_code"] for row in inventory_rows)
    for section in ("A.1.1.1", "A.1.1.2", "A.1.1.3"):
        if table_counts[section] < 2:
            raise SystemExit(f"Table/group coverage below minimum for {section}: {table_counts[section]}")
    for row in candidate_rows:
        if not is_source_code(row["source_code"]):
            raise SystemExit(f"Invalid source_code: {row['source_code']}")
        if row["review_status"] != REVIEW_STATUS:
            raise SystemExit(f"Non-pending review_status for {row['source_code']}")
        if row["section_code"] == "A.1.2":
            raise SystemExit(f"A.1.2 row leaked into sample: {row['source_code']}")


def load_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Stage 1 registry not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Stage 2A sample main rows for A.1.1.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="construction_cost_knowledge_engine project root.",
    )
    parser.add_argument("--no-xlsx", action="store_true", help="Skip optional XLSX output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    pdf_path = args.pdf
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    stage1_registry_path = project_root / "data" / "private" / "reference_extraction" / "runs" / "A111_stage1" / "page_registry_A111.json"
    load_registry(stage1_registry_path)

    output_dir = project_root / "data" / "private" / "reference_extraction" / "runs" / "A111_stage2_sample"
    output_dir.mkdir(parents=True, exist_ok=True)

    source_hash = sha256_file(pdf_path)
    parsed_tables = parse_sample_tables(pdf_path)
    inventory_rows = [table_to_inventory(parsed, pdf_path, source_hash) for parsed in parsed_tables]
    raw_rows = [table_to_raw_extract(parsed, pdf_path, source_hash) for parsed in parsed_tables]
    candidate_rows = [row for parsed in parsed_tables for row in table_to_candidates(parsed, pdf_path, source_hash)]
    issue_rows = build_issues(parsed_tables)

    validate_outputs(candidate_rows, inventory_rows)

    inventory_path = output_dir / "table_inventory_A111_sample.csv"
    raw_path = output_dir / "raw_table_extract_A111_sample.csv"
    candidate_path = output_dir / "standard_cost_item_reference_sample_A111.csv"
    issue_path = output_dir / "extraction_issues_A111_sample.csv"
    report_path = output_dir / "stage2_sample_report_A111.md"
    xlsx_path = output_dir / "standard_cost_item_reference_sample_A111.xlsx"

    write_csv(inventory_path, TABLE_INVENTORY_FIELDS, inventory_rows)
    write_csv(raw_path, RAW_EXTRACT_FIELDS, raw_rows)
    write_csv(candidate_path, CANDIDATE_FIELDS, candidate_rows)
    write_csv(issue_path, ISSUE_FIELDS, issue_rows)

    xlsx_created = False
    if not args.no_xlsx:
        xlsx_created = write_xlsx(
            xlsx_path,
            [
                ("table_inventory", TABLE_INVENTORY_FIELDS, inventory_rows),
                ("raw_table_extract", RAW_EXTRACT_FIELDS, raw_rows),
                ("reference_sample", CANDIDATE_FIELDS, candidate_rows),
                ("extraction_issues", ISSUE_FIELDS, issue_rows),
            ],
        )

    write_report(
        report_path,
        pdf_path,
        stage1_registry_path,
        source_hash,
        inventory_rows,
        candidate_rows,
        issue_rows,
        xlsx_created,
    )

    section_counts = Counter(row["section_code"] for row in candidate_rows)
    issue_counts = Counter(row["issue_type"] for row in issue_rows)
    print(f"table_inventory_rows={len(inventory_rows)}")
    print(f"raw_table_extract_rows={len(raw_rows)}")
    print(f"candidate_rows={len(candidate_rows)}")
    print(f"issue_rows={len(issue_rows)}")
    print("section_candidate_counts=" + json.dumps(dict(section_counts), ensure_ascii=False, sort_keys=True))
    print("issue_counts=" + json.dumps(dict(issue_counts), ensure_ascii=False, sort_keys=True))
    print(f"inventory_csv={inventory_path}")
    print(f"raw_csv={raw_path}")
    print(f"candidate_csv={candidate_path}")
    print(f"issues_csv={issue_path}")
    print(f"report={report_path}")
    if xlsx_created:
        print(f"xlsx={xlsx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
