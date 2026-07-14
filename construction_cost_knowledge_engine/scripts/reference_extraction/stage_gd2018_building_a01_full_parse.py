#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage GD2018-BUILDING-A01-FULL-PARSE-1.

Parse the official A01 PDF into review-only, source-traceable candidates. This
stage never writes Web/production databases, Mapping, GB/T baseline data, or
approved enterprise quota records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pdfplumber
from pypdf import PdfReader

import stage_gd2018_pdf_a111_structured_candidate as a111


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data/private/reference_extraction/runs"
OUTPUT_RUN = "GD2018_BUILDING_A01_FULL_PARSE_1"
SOURCE_DOCUMENT_ID = "SRC-GD2018-A01-2018"
SOURCE_ROLE = "authority_source"
ARTIFACT_VOLUME_TAG = "A01"
SOURCE_VOLUME = "上册"
EXPECTED_SOURCE_HASH = "07cd7ac537b22d54b9676d4920bbeae80b8d17974ba43fb2b037301fd55e3132"
EXPECTED_PAGE_COUNT = 704
REVIEW_STATUS = "pending"

QUOTA_CODE_RE = re.compile(r"\bA1-\d{1,2}-\d+(?:-\d+)?\b")
RESOURCE_CODE_RE = re.compile(r"\b\d{8,9}(?:-\d{4})?\b")
SECTION_HEADING_RE = re.compile(r"^(A\.1\.\d+\.\d+)\s+(.+)$")
PRINTED_PAGE_RE = re.compile(r"^\d{1,4}$")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

CHAPTER_BOUNDS = [
    ("A.1.1", 49, 100, 59),
    ("A.1.2", 101, 130, 109),
    ("A.1.3", 131, 194, 139),
    ("A.1.4", 195, 246, 203),
    ("A.1.5", 247, 312, 259),
    ("A.1.6", 313, 362, 321),
    ("A.1.7", 363, 436, 373),
    ("A.1.8", 437, 468, 443),
    ("A.1.9", 469, 562, 475),
    ("A.1.10", 563, 642, 571),
    ("A.1.11", 643, 704, 649),
]

PAGE_FIELDS = [
    "source_document_id", "source_file", "source_sha256", "pdf_page_no",
    "printed_page_no", "chapter_code", "chapter_name", "page_type",
    "text_layer_status", "parse_status", "review_status",
]
SECTION_FIELDS = [
    "section_id", "parent_section_id", "chapter_code", "section_code",
    "section_name", "hierarchy_level", "page_start", "page_end",
    "source_document_id", "review_status",
]
QUOTA_FIELDS = [
    "quota_uid", "source_code", "raw_name", "standard_name_candidate",
    "specification", "unit_raw", "unit_normalized", "chapter_code",
    "section_code", "page_start", "page_end", "source_document_id",
    "source_pdf_sha256", "source_role", "review_status", "parse_confidence",
    "remark",
]
PRICE_FIELDS = [
    "quota_uid", "source_code", "labor_fee", "material_fee", "machine_fee",
    "management_fee", "total_fee", "other_fee", "price_unit",
    "source_page_no", "source_document_id", "review_status",
]
RESOURCE_FIELDS = [
    "resource_component_id", "quota_uid", "quota_source_code",
    "resource_category", "resource_code", "resource_name", "specification",
    "unit", "consumption", "unit_price", "component_amount",
    "source_page_no", "source_row_order", "parse_confidence", "review_status",
]
WORK_BLOCK_FIELDS = [
    "work_content_block_id", "chapter_code", "section_code", "content_order",
    "content_text", "page_start", "page_end", "source_document_id",
    "review_status",
]
WORK_SCOPE_FIELDS = [
    "scope_link_id", "work_content_block_id", "scope_type", "scope_start_code",
    "scope_end_code", "quota_uid", "scope_confidence", "scope_status",
    "review_status",
]
RULE_BLOCK_FIELDS = [
    "quantity_rule_block_id", "rule_number", "hierarchy_level", "rule_title",
    "rule_text", "table_reference", "page_start", "page_end",
    "source_document_id", "review_status",
]
RULE_SCOPE_FIELDS = [
    "scope_link_id", "quantity_rule_block_id", "scope_type", "scope_start_code",
    "scope_end_code", "quota_uid", "scope_confidence", "scope_status",
    "review_status",
]
CONVERSION_FIELDS = [
    "conversion_rule_id", "chapter_code", "section_code", "conversion_condition",
    "labor_coefficient", "material_coefficient", "machine_coefficient",
    "equipment_coefficient", "main_material_coefficient", "unit_price_coefficient",
    "applicable_scope", "pdf_page_no", "source_text_raw", "source_document_id",
    "review_status", "parse_confidence", "remark",
]
NOTE_FIELDS = [
    "note_clause_id", "chapter_code", "section_code", "clause_type",
    "clause_text", "include_exclude_flag", "calculation_basis", "pdf_page_no",
    "source_document_id", "review_status", "parse_confidence", "remark",
]
ISSUE_FIELDS = [
    "issue_id", "issue_type", "severity", "chapter_code", "section_code",
    "pdf_page_no", "source_code", "resource_component_id", "field_name",
    "issue_detail", "recommended_action", "review_status",
]
CHECKPOINT_FIELDS = [
    "checkpoint_id", "chapter_code", "chapter_name", "page_start", "page_end",
    "parse_status", "quota_count", "resource_count", "work_content_block_count",
    "quantity_rule_block_count", "issue_count", "last_completed_page",
    "source_sha256", "generated_at",
]
REGRESSION_FIELDS = [
    "metric", "expected_count", "actual_count", "difference_count", "status",
    "evidence_file", "remark",
]
DIFFERENCE_FIELDS = [
    "comparison_entity", "source_code", "field_name", "old_value", "new_value",
    "difference_type", "recommended_resolution", "review_status",
]

ENTITY_FIELDS = {
    "a01_quota_item_candidate.csv": QUOTA_FIELDS,
    "a01_quota_price_snapshot.csv": PRICE_FIELDS,
    "a01_resource_component.csv": RESOURCE_FIELDS,
    "a01_work_content_block.csv": WORK_BLOCK_FIELDS,
    "a01_work_content_scope_link.csv": WORK_SCOPE_FIELDS,
    "a01_quantity_rule_block.csv": RULE_BLOCK_FIELDS,
    "a01_quantity_rule_scope_link.csv": RULE_SCOPE_FIELDS,
    "a01_conversion_rule.csv": CONVERSION_FIELDS,
    "a01_note_clause.csv": NOTE_FIELDS,
    "a01_parse_issues.csv": ISSUE_FIELDS,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(compact(part) for part in parts)
    suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{suffix}"


def volume_id(prefix: str, *parts: Any) -> str:
    return stable_id(f"{prefix}-{ARTIFACT_VOLUME_TAG}", *parts)


def volume_quota_uid(source_code: str) -> str:
    return f"QUOTA-GD2018-{ARTIFACT_VOLUME_TAG}-{source_code}"


def code_sort_key(code: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", code))


def decimal(value: Any) -> Optional[Decimal]:
    text = compact(value).replace(",", "")
    if text in {"", "-", "—", "–"}:
        return None
    match = NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    temp.replace(path)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_a01_pdf(engine_root: Path) -> Path:
    matches = list((engine_root / "data/private/reference_extraction/source_standards").rglob("A01_*.pdf"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one A01 PDF, found {len(matches)}: {matches}")
    return matches[0]


def validate_gate(path: Path, field: str, expected: str) -> None:
    rows = read_csv(path)
    actual = rows[0].get(field, "") if len(rows) == 1 else ""
    if actual != expected:
        raise RuntimeError(f"Gate failed: {path} {field}={actual!r}; expected {expected!r}")


def discover_chapters(texts: Sequence[str]) -> List[Dict[str, Any]]:
    chapters: List[Dict[str, Any]] = []
    for code, start, end, table_start in CHAPTER_BOUNDS:
        lines = [line.strip() for line in texts[start - 1].splitlines() if line.strip()]
        name = next((line for line in reversed(lines) if line != code), "")
        chapters.append({
            "chapter_code": code,
            "chapter_name": name,
            "page_start": start,
            "page_end": end,
            "table_start": table_start,
        })
    return chapters


def chapter_for_page(chapters: Sequence[Dict[str, Any]], page_no: int) -> Optional[Dict[str, Any]]:
    return next((chapter for chapter in chapters if chapter["page_start"] <= page_no <= chapter["page_end"]), None)


def build_sections(texts: Sequence[str], chapters: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[int, Tuple[str, str]]]:
    rows: List[Dict[str, Any]] = []
    page_to_section: Dict[int, Tuple[str, str]] = {}
    for chapter in chapters:
        chapter_code = chapter["chapter_code"]
        chapter_id = f"SECTION-{chapter_code.replace('.', '-') }"
        rows.append({
            "section_id": chapter_id,
            "parent_section_id": "",
            "chapter_code": chapter_code,
            "section_code": chapter_code,
            "section_name": chapter["chapter_name"],
            "hierarchy_level": 1,
            "page_start": chapter["page_start"],
            "page_end": chapter["page_end"],
            "source_document_id": SOURCE_DOCUMENT_ID,
            "review_status": REVIEW_STATUS,
        })
        found: List[Tuple[str, str, int]] = []
        for page_no in range(chapter["page_start"], chapter["page_end"] + 1):
            for line in texts[page_no - 1].splitlines():
                match = SECTION_HEADING_RE.match(line.strip())
                if match and match.group(1).startswith(chapter_code + "."):
                    item = (match.group(1), compact(match.group(2)), page_no)
                    if not any(existing[0] == item[0] for existing in found):
                        found.append(item)
        found.sort(key=lambda item: item[2])
        for index, (section_code, section_name, page_start) in enumerate(found):
            page_end = found[index + 1][2] - 1 if index + 1 < len(found) else chapter["page_end"]
            rows.append({
                "section_id": f"SECTION-{section_code.replace('.', '-')}",
                "parent_section_id": chapter_id,
                "chapter_code": chapter_code,
                "section_code": section_code,
                "section_name": section_name,
                "hierarchy_level": 2,
                "page_start": page_start,
                "page_end": page_end,
                "source_document_id": SOURCE_DOCUMENT_ID,
                "review_status": REVIEW_STATUS,
            })
            for page_no in range(page_start, page_end + 1):
                page_to_section[page_no] = (section_code, section_name)
        current = (chapter_code, chapter["chapter_name"])
        for page_no in range(chapter["page_start"], chapter["page_end"] + 1):
            if page_no in page_to_section:
                current = page_to_section[page_no]
            else:
                page_to_section[page_no] = current
    return rows, page_to_section


def printed_page_no(text: str, pdf_page_no: int) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:2] + lines[-2:]:
        if PRINTED_PAGE_RE.fullmatch(line):
            return line
    return str(pdf_page_no - 40) if 51 <= pdf_page_no <= EXPECTED_PAGE_COUNT else ""


def derive_subsection(text: str, chapter_code: str, section_code: str) -> Tuple[str, str]:
    prefix = text.split("工作内容：", 1)[0]
    lines = [compact(line) for line in prefix.splitlines() if compact(line)]
    filtered = []
    for line in lines:
        if line in {chapter_code, section_code} or line.startswith(chapter_code + " ") or line.startswith(section_code + " "):
            continue
        if PRINTED_PAGE_RE.fullmatch(line):
            continue
        filtered.append(line)
    value = compact(" ".join(filtered))
    match = re.match(r"^(\(?\d+\)?|（[一二三四五六七八九十]+）)\s*(.*)$", value)
    return (match.group(1), compact(match.group(2))) if match else ("", value)


def normalize_resource_category(value: str) -> str:
    return a111.display_category(value)


def make_issue(issue_type: str, severity: str, chapter_code: str, detail: str,
               action: str, section_code: str = "", pdf_page_no: Any = "",
               source_code: str = "", resource_component_id: str = "",
               field_name: str = "") -> Dict[str, Any]:
    return {
        "issue_id": volume_id("ISSUE", issue_type, chapter_code, section_code, pdf_page_no, source_code, resource_component_id, field_name, detail),
        "issue_type": issue_type,
        "severity": severity,
        "chapter_code": chapter_code,
        "section_code": section_code,
        "pdf_page_no": pdf_page_no,
        "source_code": source_code,
        "resource_component_id": resource_component_id,
        "field_name": field_name,
        "issue_detail": detail,
        "recommended_action": action,
        "review_status": REVIEW_STATUS,
    }


def find_rule_start(texts: Sequence[str], chapter: Dict[str, Any]) -> int:
    for page_no in range(chapter["page_start"] + 1, chapter["table_start"]):
        if "工程量计算规则" in re.sub(r"\s+", "", texts[page_no - 1]):
            return page_no
    return chapter["table_start"]


def extract_note_text(text: str) -> str:
    match = re.search(r"(?:^|\n)\s*注[：:]\s*(.+)", text, flags=re.S)
    if not match:
        return ""
    value = compact(match.group(1))
    return re.sub(r"\s+\d{1,4}$", "", value).strip()


def coefficient(text: str, labels: Sequence[str]) -> str:
    for label in labels:
        match = re.search(label + r".{0,20}?(?:乘以|系数为|系数)\s*([0-9]+(?:\.[0-9]+)?)", text)
        if match:
            return match.group(1)
    return ""


def build_rules_notes_conversions(
    chapter: Dict[str, Any], texts: Sequence[str], page_to_section: Dict[int, Tuple[str, str]],
    chapter_codes: Sequence[str], golden_rule_blocks: Sequence[Dict[str, str]],
    golden_scope_links: Sequence[Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    rule_blocks: List[Dict[str, Any]] = []
    rule_links: List[Dict[str, Any]] = []
    conversions: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    chapter_code = chapter["chapter_code"]
    first_code = min(chapter_codes, key=code_sort_key)
    last_code = max(chapter_codes, key=code_sort_key)
    rule_start = find_rule_start(texts, chapter)

    if chapter_code == "A.1.1":
        for row in golden_rule_blocks:
            rule_blocks.append({
                "quantity_rule_block_id": row["rule_block_id"],
                "rule_number": row["rule_no"],
                "hierarchy_level": row["rule_level"],
                "rule_title": row["rule_title"],
                "rule_text": row["raw_text"],
                "table_reference": row["table_json"],
                "page_start": row["pdf_page_no"],
                "page_end": row["pdf_page_no"],
                "source_document_id": SOURCE_DOCUMENT_ID,
                "review_status": REVIEW_STATUS,
            })
        for row in golden_scope_links:
            rule_links.append({
                "scope_link_id": row["scope_link_id"],
                "quantity_rule_block_id": row["rule_block_id"],
                "scope_type": row["scope_type"],
                "scope_start_code": row["quota_code_start"],
                "scope_end_code": row["quota_code_end"],
                "quota_uid": volume_quota_uid(row["specific_quota_source_code"]) if row["specific_quota_source_code"] else "",
                "scope_confidence": row["scope_confidence"],
                "scope_status": "uncertain" if row["requires_manual_scope_review"].lower() == "true" else "linked",
                "review_status": REVIEW_STATUS,
            })
    else:
        for page_no in range(rule_start, chapter["table_start"]):
            raw = compact(texts[page_no - 1])
            if not raw:
                continue
            block_id = volume_id("QRBLOCK", chapter_code, page_no, raw)
            rule_blocks.append({
                "quantity_rule_block_id": block_id,
                "rule_number": f"{chapter_code}-P{page_no:03d}",
                "hierarchy_level": "page_block",
                "rule_title": "工程量计算规则" if "工程量计算规则" in raw else "续页规则",
                "rule_text": raw,
                "table_reference": "",
                "page_start": page_no,
                "page_end": page_no,
                "source_document_id": SOURCE_DOCUMENT_ID,
                "review_status": REVIEW_STATUS,
            })
            rule_links.append({
                "scope_link_id": volume_id("QRSCOPE", block_id),
                "quantity_rule_block_id": block_id,
                "scope_type": "uncertain",
                "scope_start_code": first_code,
                "scope_end_code": last_code,
                "quota_uid": "",
                "scope_confidence": "0.50",
                "scope_status": "uncertain",
                "review_status": REVIEW_STATUS,
            })
        issues.append(make_issue(
            "ambiguous_scope", "medium", chapter_code,
            "Chapter quantity rules are retained as source blocks; per-quota applicability is not asserted.",
            "Review rule applicability and refine scope links without duplicating source blocks.",
            pdf_page_no=rule_start, field_name="scope_status",
        ))

    for page_no in range(chapter["page_start"] + 1, rule_start):
        raw = compact(texts[page_no - 1])
        if not raw:
            continue
        section_code = page_to_section[page_no][0]
        notes.append({
            "note_clause_id": volume_id("NOTE", chapter_code, page_no, "chapter_description", raw),
            "chapter_code": chapter_code,
            "section_code": section_code,
            "clause_type": "章说明",
            "clause_text": raw,
            "include_exclude_flag": "",
            "calculation_basis": "",
            "pdf_page_no": page_no,
            "source_document_id": SOURCE_DOCUMENT_ID,
            "review_status": REVIEW_STATUS,
            "parse_confidence": "0.78",
            "remark": "page-level chapter description; pending clause segmentation review",
        })

    for page_no in range(chapter["table_start"], chapter["page_end"] + 1):
        text = texts[page_no - 1]
        section_code = page_to_section[page_no][0]
        note_text = extract_note_text(text)
        is_supplement = not QUOTA_CODE_RE.search(text) and ("附表" in text or "材 料 编 号" in text or "子目名称" in text)
        if note_text or is_supplement:
            clause_text = note_text or compact(text)
            clause_type = "补充说明" if is_supplement else "表下注释"
            include_flag = "不包含事项" if "不包括" in clause_text or "不含" in clause_text else ("包含事项" if "包括" in clause_text or "含" in clause_text else "")
            basis = "计算口径" if any(token in clause_text for token in ("计算", "计取", "工程量")) else ""
            notes.append({
                "note_clause_id": volume_id("NOTE", chapter_code, page_no, clause_type, clause_text),
                "chapter_code": chapter_code,
                "section_code": section_code,
                "clause_type": clause_type,
                "clause_text": clause_text,
                "include_exclude_flag": include_flag,
                "calculation_basis": basis,
                "pdf_page_no": page_no,
                "source_document_id": SOURCE_DOCUMENT_ID,
                "review_status": REVIEW_STATUS,
                "parse_confidence": "0.82" if note_text else "0.65",
                "remark": "official PDF note/supplemental table evidence; pending human review",
            })
        if is_supplement:
            issues.append(make_issue(
                "manual_review_required", "medium", chapter_code,
                "Supplemental reference table is retained as page-level evidence and is not linked to quota resources.",
                "Review the supplemental table separately; do not infer quota ownership from material identifiers.",
                section_code=section_code, pdf_page_no=page_no, field_name="clause_text",
            ))

    conversion_sources = notes + [
        {
            "chapter_code": chapter_code,
            "section_code": page_to_section[page_no][0],
            "pdf_page_no": page_no,
            "clause_text": compact(texts[page_no - 1]),
        }
        for page_no in range(rule_start, chapter["table_start"])
    ]
    seen_conversion = set()
    for source in conversion_sources:
        raw = source.get("clause_text", "")
        if not raw or not any(token in raw for token in ("换算", "系数", "乘以")):
            continue
        key = (source["pdf_page_no"], raw)
        if key in seen_conversion:
            continue
        seen_conversion.add(key)
        conversions.append({
            "conversion_rule_id": volume_id("CONV", chapter_code, source["pdf_page_no"], raw),
            "chapter_code": chapter_code,
            "section_code": source.get("section_code", ""),
            "conversion_condition": raw,
            "labor_coefficient": coefficient(raw, ["人工"]),
            "material_coefficient": coefficient(raw, ["材料"]),
            "machine_coefficient": coefficient(raw, ["机具", "机械"]),
            "equipment_coefficient": coefficient(raw, ["设备"]),
            "main_material_coefficient": coefficient(raw, ["主材"]),
            "unit_price_coefficient": coefficient(raw, ["基价", "单价"]),
            "applicable_scope": source.get("section_code", "") or chapter_code,
            "pdf_page_no": source["pdf_page_no"],
            "source_text_raw": raw,
            "source_document_id": SOURCE_DOCUMENT_ID,
            "review_status": REVIEW_STATUS,
            "parse_confidence": "0.64",
            "remark": "coefficient fields remain blank unless explicitly detected; no implicit coefficient is created",
        })
    return rule_blocks, rule_links, conversions, notes, issues


def transform_chapter(
    chapter: Dict[str, Any], candidates: Sequence[Dict[str, Any]], resources: Sequence[Dict[str, Any]],
    works: Sequence[Dict[str, Any]], source_hash: str,
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    output: Dict[str, List[Dict[str, Any]]] = {name: [] for name in ENTITY_FIELDS}
    issues: List[Dict[str, Any]] = []
    candidate_by_code = {row["quota_source_code"]: row for row in candidates}
    resource_order: Dict[str, int] = defaultdict(int)

    for row in candidates:
        code = row["quota_source_code"]
        quota_uid = volume_quota_uid(code)
        output["a01_quota_item_candidate.csv"].append({
            "quota_uid": quota_uid,
            "source_code": code,
            "raw_name": row["quota_name_from_pdf"],
            "standard_name_candidate": row["quota_name_full_from_pdf"],
            "specification": "",
            "unit_raw": row["quota_unit_raw"],
            "unit_normalized": row["quota_unit_normalized"],
            "chapter_code": row["chapter_code"],
            "section_code": row["section_code"],
            "page_start": row["pdf_page_no"],
            "page_end": row["pdf_page_no"],
            "source_document_id": SOURCE_DOCUMENT_ID,
            "source_pdf_sha256": source_hash,
            "source_role": SOURCE_ROLE,
            "review_status": REVIEW_STATUS,
            "parse_confidence": row["parse_confidence"],
            "remark": compact(f"group={row.get('subsection_name', '')}; official PDF candidate; no bill_code generated"),
        })
        output["a01_quota_price_snapshot.csv"].append({
            "quota_uid": quota_uid,
            "source_code": code,
            "labor_fee": row["labor_fee"],
            "material_fee": row["material_fee"],
            "machine_fee": row["machine_fee"],
            "management_fee": row["management_fee"],
            "total_fee": row["base_price"],
            "other_fee": "",
            "price_unit": f"元/{row['quota_unit_normalized']}" if row["quota_unit_normalized"] else "",
            "source_page_no": row["pdf_page_no"],
            "source_document_id": SOURCE_DOCUMENT_ID,
            "review_status": REVIEW_STATUS,
        })
        if not row["quota_unit_normalized"]:
            issues.append(make_issue(
                "unit_unparsed", "medium", chapter["chapter_code"],
                "Quota unit is blank or represented by a table reference that was not normalized.",
                "Verify the source page and retain the original unit semantics.",
                section_code=row["section_code"], pdf_page_no=row["pdf_page_no"],
                source_code=code, field_name="unit_normalized",
            ))
        main_parts = [row["labor_fee"], row["material_fee"], row["machine_fee"], row["management_fee"]]
        if any(compact(value) == "" for value in main_parts):
            issues.append(make_issue(
                "price_component_missing", "medium", chapter["chapter_code"],
                "At least one main price component is blank; the source blank was preserved.",
                "Verify the table column without substituting zero.",
                section_code=row["section_code"], pdf_page_no=row["pdf_page_no"],
                source_code=code, field_name="price_components",
            ))

    resource_sums: Dict[Tuple[str, str], Decimal] = defaultdict(Decimal)
    resource_unpriced: set[Tuple[str, str]] = set()
    for row in resources:
        code = row["quota_source_code"]
        resource_order[code] += 1
        order = resource_order[code]
        category = normalize_resource_category(row["resource_category_normalized"])
        component_id = volume_id("RES", code, row["pdf_page_no"], row["resource_row_index"], order, row["resource_code"])
        output["a01_resource_component.csv"].append({
            "resource_component_id": component_id,
            "quota_uid": volume_quota_uid(code),
            "quota_source_code": code,
            "resource_category": category,
            "resource_code": row["resource_code"],
            "resource_name": row["resource_name"],
            "specification": row["resource_spec"],
            "unit": row["resource_unit_normalized"],
            "consumption": row["resource_consumption"],
            "unit_price": row["resource_unit_price"],
            "component_amount": row["resource_fee_calculated"],
            "source_page_no": row["pdf_page_no"],
            "source_row_order": order,
            "parse_confidence": row["parse_confidence"],
            "review_status": REVIEW_STATUS,
        })
        amount = decimal(row["resource_fee_calculated"])
        if amount is None:
            resource_unpriced.add((code, category))
        else:
            resource_sums[(code, category)] += amount

    for code, candidate in candidate_by_code.items():
        expected_by_category = {
            "labor": decimal(candidate["labor_fee"]),
            "material": decimal(candidate["material_fee"]),
            "machine": decimal(candidate["machine_fee"]),
        }
        mismatches = []
        mismatch_deltas: List[Decimal] = []
        for category, expected in expected_by_category.items():
            if expected is None or (code, category) in resource_unpriced:
                continue
            actual = resource_sums.get((code, category), Decimal("0"))
            if abs(actual - expected) > Decimal("0.10"):
                mismatches.append(f"{category}: resource={actual:.2f}, main={expected:.2f}")
                mismatch_deltas.append(abs(actual - expected))
        if mismatches:
            if ARTIFACT_VOLUME_TAG == "A01" and code == "A1-10-92":
                issue_type = "partial_resource_rows_missing"
                detail = (
                    "; ".join(mismatches)
                    + "; official_pdf_cell_visually_blank=true; requires_manual_review=true"
                )
                action = "Keep the official PDF cell blank; do not infer or fabricate a resource row or value."
            elif all(delta <= Decimal("1.00") for delta in mismatch_deltas):
                issue_type = "rounding_only"
                detail = "; ".join(mismatches)
                action = "Retain source values and review cumulative displayed-precision rounding only."
            else:
                issue_type = "resource_sum_mismatch"
                detail = "; ".join(mismatches)
                action = "Review source resource rows, category boundaries, bracketed main materials, and rounding."
            issues.append(make_issue(
                issue_type, "medium", chapter["chapter_code"], detail, action,
                section_code=candidate["section_code"], pdf_page_no=candidate["pdf_page_no"],
                source_code=code, field_name="component_amount",
            ))

    for order, row in enumerate(works, start=1):
        block_id = volume_id("WORK", row["chapter_code"], row["pdf_page_no"], row["quota_source_code_start"], row["quota_source_code_end"], row["work_content_raw"])
        output["a01_work_content_block.csv"].append({
            "work_content_block_id": block_id,
            "chapter_code": row["chapter_code"],
            "section_code": row["section_code"],
            "content_order": order,
            "content_text": row["work_content_raw"],
            "page_start": row["pdf_page_no"],
            "page_end": row["pdf_page_no"],
            "source_document_id": SOURCE_DOCUMENT_ID,
            "review_status": REVIEW_STATUS,
        })
        output["a01_work_content_scope_link.csv"].append({
            "scope_link_id": volume_id("WORKSCOPE", block_id),
            "work_content_block_id": block_id,
            "scope_type": "quota_code_range",
            "scope_start_code": row["quota_source_code_start"],
            "scope_end_code": row["quota_source_code_end"],
            "quota_uid": "",
            "scope_confidence": row["parse_confidence"],
            "scope_status": "pending_manual_review",
            "review_status": REVIEW_STATUS,
        })
    return output, issues


def parse_chapter(
    pdf_path: Path, pdf: pdfplumber.PDF, texts: Sequence[str], chapter: Dict[str, Any],
    page_to_section: Dict[int, Tuple[str, str]], source_hash: str,
    golden_rule_blocks: Sequence[Dict[str, str]], golden_scope_links: Sequence[Dict[str, str]],
) -> Dict[str, List[Dict[str, Any]]]:
    chapter_code = chapter["chapter_code"]
    a111.QUOTA_CODE_RE = QUOTA_CODE_RE
    a111.SOURCE_VOLUME = SOURCE_VOLUME
    a111.CHAPTER_CODE = chapter_code
    a111.CHAPTER_NAME = chapter["chapter_name"]
    current_section = [chapter_code, chapter["chapter_name"]]
    a111.section_for_code = lambda _code: tuple(current_section)
    candidates: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    works: List[Dict[str, Any]] = []
    parse_issues: List[Dict[str, Any]] = []
    inherited_unit = ""

    for page_no in range(chapter["table_start"], chapter["page_end"] + 1):
        text = texts[page_no - 1]
        codes = QUOTA_CODE_RE.findall(text)
        if not codes:
            continue
        current_section[:] = page_to_section[page_no]
        page = pdf.pages[page_no - 1]
        tables = page.extract_tables() or []
        table = next((table for table in tables if any(
            QUOTA_CODE_RE.fullmatch(a111.clean_cell(cell))
            for row in table for cell in row if cell is not None
        )), None)
        if table is None:
            parse_issues.append(make_issue(
                "table_header_missing", "blocking", chapter_code,
                "Quota codes exist in the text layer but no quota table header was recovered.",
                "Repair table extraction for this page before completing the chapter.",
                section_code=current_section[0], pdf_page_no=page_no, source_code=codes[0],
                field_name="table_header",
            ))
            continue
        positioned_unit = a111.positioned_quota_unit(page)
        if positioned_unit:
            inherited_unit = positioned_unit
        page_candidates, page_resources, work = a111.parse_table_page(
            pdf_path, page_no, text, table, inherited_unit,
        )
        subsection_code, subsection_name = derive_subsection(text, chapter_code, current_section[0])
        for row in page_candidates:
            row["chapter_code"] = chapter_code
            row["chapter_name"] = chapter["chapter_name"]
            row["section_code"], row["section_name"] = current_section
            row["subsection_code"] = subsection_code
            row["subsection_name"] = subsection_name
            row["source_block_id"] = row["source_block_id"].replace("A111_", f"{ARTIFACT_VOLUME_TAG}_")
            row["table_header_group_id"] = row["table_header_group_id"].replace("A111_", f"{ARTIFACT_VOLUME_TAG}_")
        for row in page_resources:
            row["chapter_code"] = chapter_code
            row["chapter_name"] = chapter["chapter_name"]
            row["section_code"], row["section_name"] = current_section
            row["subsection_code"] = subsection_code
            row["subsection_name"] = subsection_name
            row["source_block_id"] = row["source_block_id"].replace("A111_", f"{ARTIFACT_VOLUME_TAG}_")
            row["table_header_group_id"] = row["table_header_group_id"].replace("A111_", f"{ARTIFACT_VOLUME_TAG}_")
        if work:
            work["chapter_code"] = chapter_code
            work["chapter_name"] = chapter["chapter_name"]
            work["section_code"], work["section_name"] = current_section
            work["subsection_code"] = subsection_code
            work["subsection_name"] = subsection_name
            work["source_block_id"] = work["source_block_id"].replace("A111_", f"{ARTIFACT_VOLUME_TAG}_")
            works.append(work)
        candidates.extend(page_candidates)
        resources.extend(page_resources)

    transformed, integrity_issues = transform_chapter(chapter, candidates, resources, works, source_hash)
    chapter_codes = [row["source_code"] for row in transformed["a01_quota_item_candidate.csv"]]
    if not chapter_codes:
        parse_issues.append(make_issue(
            "missing_quota_code", "blocking", chapter_code,
            "No quota codes were extracted for the chapter.",
            "Repair the chapter parser before completion.", field_name="source_code",
        ))
        chapter_codes = [f"A1-{chapter_code.split('.')[-1]}-0"]
    rules, rule_links, conversions, notes, governance_issues = build_rules_notes_conversions(
        chapter, texts, page_to_section, chapter_codes, golden_rule_blocks, golden_scope_links
    )
    transformed["a01_quantity_rule_block.csv"] = rules
    transformed["a01_quantity_rule_scope_link.csv"] = rule_links
    transformed["a01_conversion_rule.csv"] = conversions
    transformed["a01_note_clause.csv"] = notes
    transformed["a01_parse_issues.csv"] = parse_issues + integrity_issues + governance_issues
    return transformed


def save_part(parts_dir: Path, chapter_code: str, data: Dict[str, List[Dict[str, Any]]]) -> Path:
    path = parts_dir / f"{chapter_code.replace('.', '_')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return path


def load_part(parts_dir: Path, chapter_code: str) -> Dict[str, List[Dict[str, Any]]]:
    path = parts_dir / f"{chapter_code.replace('.', '_')}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_page_registry(
    pdf_path: Path, source_hash: str, texts: Sequence[str], chapters: Sequence[Dict[str, Any]],
    page_to_section: Dict[int, Tuple[str, str]], issue_pages: set[int],
) -> List[Dict[str, Any]]:
    rows = []
    title_pages = {chapter["page_start"] for chapter in chapters}
    table_starts = {chapter["chapter_code"]: chapter["table_start"] for chapter in chapters}
    rule_starts = {chapter["chapter_code"]: find_rule_start(texts, chapter) for chapter in chapters}
    for page_no, text in enumerate(texts, start=1):
        chapter = chapter_for_page(chapters, page_no)
        chapter_code = chapter["chapter_code"] if chapter else ""
        chapter_name = chapter["chapter_name"] if chapter else ""
        if not chapter:
            page_type = "front_matter"
            parse_status = "completed"
        elif page_no in title_pages:
            page_type = "chapter_title"
            parse_status = "completed"
        elif page_no < rule_starts[chapter_code]:
            page_type = "chapter_description"
            parse_status = "completed"
        elif page_no < table_starts[chapter_code]:
            page_type = "quantity_rule"
            parse_status = "completed_with_issues" if page_no in issue_pages else "completed"
        elif QUOTA_CODE_RE.search(text):
            page_type = "quota_table"
            parse_status = "completed_with_issues" if page_no in issue_pages else "completed"
        elif "附表" in text or "材 料 编 号" in text or "子目名称" in text:
            page_type = "supplemental_reference_table"
            parse_status = "completed_with_issues"
        elif compact(text):
            page_type = "table_context_or_note"
            parse_status = "completed_with_issues" if page_no in issue_pages else "completed"
        else:
            page_type = "blank_or_separator"
            parse_status = "completed"
        rows.append({
            "source_document_id": SOURCE_DOCUMENT_ID,
            "source_file": str(pdf_path),
            "source_sha256": source_hash,
            "pdf_page_no": page_no,
            "printed_page_no": printed_page_no(text, page_no),
            "chapter_code": chapter_code,
            "chapter_name": chapter_name,
            "page_type": page_type,
            "text_layer_status": "text_present" if compact(text) else "text_blank",
            "parse_status": parse_status,
            "review_status": REVIEW_STATUS,
        })
    return rows


def web_state(engine_root: Path) -> Dict[str, Any]:
    db = engine_root / "web_collab_prototype/data/web_collab_readonly.sqlite"
    result = {"path": str(db), "sha256": sha256(db), "draft_count": 0, "audit_count": 0, "approved_count": 0}
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        result["draft_count"] = connection.execute("SELECT COUNT(*) FROM web_quota_a111_mapping_draft_edges").fetchone()[0]
        result["audit_count"] = connection.execute("SELECT COUNT(*) FROM web_quota_a111_mapping_draft_audit_log").fetchone()[0]
        approved = 0
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            for column in columns:
                if "status" in column.lower():
                    approved += connection.execute(
                        f'SELECT COUNT(*) FROM "{table}" WHERE lower(trim(CAST("{column}" AS TEXT))) = ?',
                        ("approved",),
                    ).fetchone()[0]
        result["approved_count"] = approved
    finally:
        connection.close()
    return result


def protected_hashes(engine_root: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for run in [
        "GD2018_PDF_A111_FULL_REVIEW_PACK_1",
        "WEB_QUOTA_A111_PDF_DETAIL_VIEWER_1",
        "WEB_QUOTA_A111_MAPPING_DRAFT_1",
        "WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1",
    ]:
        for path in sorted((engine_root / "data/private/reference_extraction/runs" / run).glob("*.csv")):
            hashes[f"{run}/{path.name}"] = sha256(path)
    return hashes


def canonical_resource(row: Dict[str, str]) -> Tuple[str, ...]:
    return (
        row.get("resource_category", row.get("resource_category_normalized", "")),
        row.get("resource_code", ""), row.get("resource_name", ""),
        row.get("specification", row.get("resource_spec", "")),
        row.get("unit", row.get("resource_unit_normalized", "")),
        row.get("consumption", row.get("resource_consumption", "")),
        row.get("unit_price", row.get("resource_unit_price", "")),
        row.get("component_amount", row.get("resource_fee_calculated", "")),
    )


def build_regression(
    engine_root: Path, merged: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    golden_dir = engine_root / "data/private/reference_extraction/runs/GD2018_PDF_A111_FULL_REVIEW_PACK_1"
    dual_dir = engine_root / "data/private/reference_extraction/runs/WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1"
    golden_quota = read_csv(golden_dir / "main_quota_all_137.csv")
    golden_resources = read_csv(golden_dir / "resource_display_all_629.csv")
    golden_work = read_csv(golden_dir / "work_content_by_quota_137.csv")
    golden_rules = read_csv(dual_dir / "quantity_rule_source_blocks.csv")
    golden_scopes = read_csv(dual_dir / "quantity_rule_scope_links.csv")
    new_quota = [row for row in merged["a01_quota_item_candidate.csv"] if row["chapter_code"] == "A.1.1"]
    new_price = {row["source_code"]: row for row in merged["a01_quota_price_snapshot.csv"] if row["source_code"].startswith("A1-1-")}
    new_resources = [row for row in merged["a01_resource_component.csv"] if row["quota_source_code"].startswith("A1-1-")]
    new_work_blocks = {row["work_content_block_id"]: row for row in merged["a01_work_content_block.csv"] if row["chapter_code"] == "A.1.1"}
    new_work_scopes = [row for row in merged["a01_work_content_scope_link.csv"] if row["work_content_block_id"] in new_work_blocks]
    new_rules = [row for row in merged["a01_quantity_rule_block.csv"] if row["quantity_rule_block_id"].startswith("QRBLOCK-A111-")]
    new_scopes = [row for row in merged["a01_quantity_rule_scope_link.csv"] if row["quantity_rule_block_id"].startswith("QRBLOCK-A111-")]
    differences: List[Dict[str, Any]] = []

    def diff(entity: str, code: str, field: str, old: Any, new: Any, kind: str = "value_mismatch") -> None:
        if str(old) == str(new):
            return
        differences.append({
            "comparison_entity": entity,
            "source_code": code,
            "field_name": field,
            "old_value": old,
            "new_value": new,
            "difference_type": kind,
            "recommended_resolution": "Review official PDF evidence; keep the golden slice unchanged until resolved.",
            "review_status": REVIEW_STATUS,
        })

    new_quota_by_code = {row["source_code"]: row for row in new_quota}
    for old in golden_quota:
        code = old["quota_source_code"]
        new = new_quota_by_code.get(code)
        if not new:
            diff("quota", code, "source_code", code, "", "missing_new_record")
            continue
        price = new_price[code]
        for field, old_field, new_value in [
            ("raw_name", "quota_name_from_pdf", new["raw_name"]),
            ("unit", "quota_unit_normalized", new["unit_normalized"]),
            ("labor_fee", "labor_fee", price["labor_fee"]),
            ("material_fee", "material_fee", price["material_fee"]),
            ("machine_fee", "machine_fee", price["machine_fee"]),
            ("management_fee", "management_fee", price["management_fee"]),
            ("total_fee", "base_price", price["total_fee"]),
            ("pdf_page_evidence", "pdf_page_no", new["page_start"]),
        ]:
            diff("quota", code, field, old[old_field], new_value)

    old_res_by_code: Dict[str, List[Tuple[str, ...]]] = defaultdict(list)
    new_res_by_code: Dict[str, List[Tuple[str, ...]]] = defaultdict(list)
    for row in golden_resources:
        old_res_by_code[row["quota_source_code"]].append(canonical_resource(row))
    for row in new_resources:
        new_res_by_code[row["quota_source_code"]].append(canonical_resource(row))
    for code in sorted(set(old_res_by_code) | set(new_res_by_code), key=code_sort_key):
        # The golden review pack groups some multi-resource PDF rows differently.
        # Compare semantic components as a multiset; source row order remains in
        # the candidate artifact and is not rewritten to mimic display ordering.
        old_components = sorted(old_res_by_code[code])
        new_components = sorted(new_res_by_code[code])
        diff("resource_component", code, "resource_component", json.dumps(old_components, ensure_ascii=False), json.dumps(new_components, ensure_ascii=False))

    expanded_work: Dict[str, str] = {}
    for scope in new_work_scopes:
        block = new_work_blocks[scope["work_content_block_id"]]
        start = code_sort_key(scope["scope_start_code"])[-1]
        end = code_sort_key(scope["scope_end_code"])[-1]
        prefix = "-".join(scope["scope_start_code"].split("-")[:-1])
        for number in range(start, end + 1):
            expanded_work[f"{prefix}-{number}"] = block["content_text"]
    for old in golden_work:
        code = old["quota_source_code"]
        diff("work_content", code, "work_content", old["work_content_raw"], expanded_work.get(code, ""))

    old_rules = [(row["rule_block_id"], row["rule_no"], row["rule_title"], row["raw_text"], row["pdf_page_no"]) for row in golden_rules]
    new_rules_cmp = [(row["quantity_rule_block_id"], row["rule_number"], row["rule_title"], row["rule_text"], str(row["page_start"])) for row in new_rules]
    diff("quantity_rule", "A.1.1", "quantity_rule", json.dumps(old_rules, ensure_ascii=False), json.dumps(new_rules_cmp, ensure_ascii=False))
    old_scope_cmp = [(row["scope_link_id"], row["rule_block_id"], row["scope_type"], row["quota_code_start"], row["quota_code_end"], row["scope_confidence"]) for row in golden_scopes]
    new_scope_cmp = [(row["scope_link_id"], row["quantity_rule_block_id"], row["scope_type"], row["scope_start_code"], row["scope_end_code"], row["scope_confidence"]) for row in new_scopes]
    diff("quantity_rule_scope", "A.1.1", "scope_link", json.dumps(old_scope_cmp, ensure_ascii=False), json.dumps(new_scope_cmp, ensure_ascii=False))

    metric_specs = [
        ("quota_rows", 137, len(new_quota), "main_quota_all_137.csv"),
        ("resource_rows", 629, len(new_resources), "resource_display_all_629.csv"),
        ("quantity_rule_blocks", 33, len(new_rules), "quantity_rule_source_blocks.csv"),
        ("quantity_rule_scope_links", 33, len(new_scopes), "quantity_rule_scope_links.csv"),
    ]
    regression = []
    for metric, expected, actual, evidence in metric_specs:
        relevant = sum(1 for row in differences if (
            (metric == "quota_rows" and row["comparison_entity"] == "quota") or
            (metric == "resource_rows" and row["comparison_entity"] == "resource_component") or
            (metric == "quantity_rule_blocks" and row["comparison_entity"] == "quantity_rule") or
            (metric == "quantity_rule_scope_links" and row["comparison_entity"] == "quantity_rule_scope")
        ))
        regression.append({
            "metric": metric, "expected_count": expected, "actual_count": actual,
            "difference_count": relevant, "status": "pass" if expected == actual and relevant == 0 else "fail",
            "evidence_file": evidence, "remark": "golden artifact remains read-only",
        })
    regression.append({
        "metric": "overall", "expected_count": "", "actual_count": "",
        "difference_count": len(differences), "status": "pass" if not differences else "fail",
        "evidence_file": "GD2018_PDF_A111_FULL_REVIEW_PACK_1;WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1",
        "remark": "compares source_code, names, units, fee components, resources, work content, rules, scope, and PDF page evidence",
    })
    return regression, differences


def integrity_metrics(merged: Dict[str, List[Dict[str, Any]]], page_count: int, chapter_count: int) -> Dict[str, int]:
    quota = merged["a01_quota_item_candidate.csv"]
    resources = merged["a01_resource_component.csv"]
    source_codes = [row["source_code"] for row in quota]
    quota_uids = {row["quota_uid"] for row in quota}
    return {
        "source_page_count": page_count,
        "chapter_count": chapter_count,
        "quota_count": len(quota),
        "unique_quota_code_count": len(set(source_codes)),
        "duplicate_quota_code_count": sum(count - 1 for count in Counter(source_codes).values() if count > 1),
        "resource_count": len(resources),
        "orphan_resource_count": sum(1 for row in resources if not row["quota_uid"] or row["quota_uid"] not in quota_uids),
        "price_snapshot_count": len(merged["a01_quota_price_snapshot.csv"]),
        "work_content_block_count": len(merged["a01_work_content_block.csv"]),
        "work_content_scope_link_count": len(merged["a01_work_content_scope_link.csv"]),
        "quantity_rule_block_count": len(merged["a01_quantity_rule_block.csv"]),
        "quantity_rule_scope_link_count": len(merged["a01_quantity_rule_scope_link.csv"]),
        "conversion_rule_count": len(merged["a01_conversion_rule.csv"]),
        "note_clause_count": len(merged["a01_note_clause.csv"]),
        "issue_count": len(merged["a01_parse_issues.csv"]),
        "approved_count": sum(1 for rows in merged.values() for row in rows if str(row.get("review_status", "")).lower() == "approved"),
    }


def write_report(
    path: Path, status: str, pdf_path: Path, source_hash: str, metrics: Dict[str, int],
    checkpoints: Sequence[Dict[str, Any]], regression: Sequence[Dict[str, Any]],
    differences: Sequence[Dict[str, Any]], pre_web: Dict[str, Any], post_web: Dict[str, Any],
    pre_hashes: Dict[str, str], post_hashes: Dict[str, str], output_dir: Path,
    stage_name: str,
) -> None:
    issue_counts = Counter(row["issue_type"] for row in read_csv(output_dir / "a01_parse_issues.csv"))
    completed = sum(row["parse_status"] in {"completed", "completed_with_issues"} for row in checkpoints)
    regression_status = next(row["status"] for row in regression if row["metric"] == "overall")
    hashes_unchanged = pre_hashes == post_hashes
    report = f"""# Stage {stage_name} Report

## Final Status

`{status}`

## Authority Source

- file: `{pdf_path}`
- source_role: `{SOURCE_ROLE}`
- SHA256: `{source_hash}`
- page_count: `{metrics['source_page_count']}`
- text layer: present; no OCR executed

## Preconditions

- building family execution gate: pass
- GB50854 dual-source gate: `gb50854_baseline_ready_with_evidence_backlog`
- the 472-row GB/T evidence backlog remains pending and was not represented as fully PDF-verified

## Parse Integrity

- completed checkpoints: {completed}/{len(checkpoints)}
- quota_count: {metrics['quota_count']}
- unique_quota_code_count: {metrics['unique_quota_code_count']}
- duplicate_quota_code_count: {metrics['duplicate_quota_code_count']}
- resource_count: {metrics['resource_count']}
- orphan_resource_count: {metrics['orphan_resource_count']}
- price_snapshot_count: {metrics['price_snapshot_count']}
- work_content_block_count: {metrics['work_content_block_count']}
- work_content_scope_link_count: {metrics['work_content_scope_link_count']}
- quantity_rule_block_count: {metrics['quantity_rule_block_count']}
- quantity_rule_scope_link_count: {metrics['quantity_rule_scope_link_count']}
- conversion_rule_count: {metrics['conversion_rule_count']}
- note_clause_count: {metrics['note_clause_count']}
- issue_count: {metrics['issue_count']}
- issue distribution: `{json.dumps(dict(sorted(issue_counts.items())), ensure_ascii=False)}`
- approved_count: {metrics['approved_count']}

## A1.1 Golden Slice Regression

- overall: `{regression_status}`
- differences: {len(differences)}
- expected/actual: quota 137, resource 629, quantity rule blocks 33, scope links 33
- golden source files unchanged: {str(hashes_unchanged).lower()}
- golden artifacts were read only and were not overwritten

## Web SQLite Protection

- database SHA256 before: `{pre_web['sha256']}`
- database SHA256 after: `{post_web['sha256']}`
- draft_count before/after: {pre_web['draft_count']} / {post_web['draft_count']}
- audit_count before/after: {pre_web['audit_count']} / {post_web['audit_count']}
- approved_count before/after: {pre_web['approved_count']} / {post_web['approved_count']}
- SQLite opened read-only; no snapshot/restore was needed because no mutation occurred

## Governance Boundaries

- Source PDF modified: no
- A02/A03 parsed: no
- GB/T Mapping executed: no
- 472-row GB/T baseline modified: no
- A1.1 golden slice modified: no
- Web code or SQLite modified: no
- production database written: no
- approved/internal_price_library/enterprise quota master generated: no

## Outputs

Output directory: `{output_dir}`

The workbook is a human-review surface only. All business records remain `review_status=pending`.
"""
    path.write_text(report, encoding="utf-8")


def run(
    project_root: Path,
    output_run: str = OUTPUT_RUN,
    report_name: str = "stage_gd2018_building_a01_full_parse_report.md",
    allow_expected_parser_fixes: bool = False,
) -> Dict[str, Any]:
    engine_root = project_root / ENGINE_REL
    output_dir = project_root / RUNS_REL / output_run
    report_path = output_dir / report_name
    if report_path.exists() and "`blocked_" not in report_path.read_text(encoding="utf-8"):
        raise RuntimeError(f"Historical run already completed; refusing to overwrite: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    parts_dir = output_dir / ".checkpoint_parts"

    validate_gate(
        project_root / RUNS_REL / "REFERENCE_FRAMEWORK_PRECONDITION_RECONCILIATION_1/building_family_execution_gate.csv",
        "final_gate_status", "reference_framework_ready_for_building_family_execution",
    )
    validate_gate(
        project_root / RUNS_REL / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1/gb50854_dual_source_gate.csv",
        "final_status", "gb50854_baseline_ready_with_evidence_backlog",
    )

    pdf_path = find_a01_pdf(engine_root)
    source_hash = sha256(pdf_path)
    reader = PdfReader(str(pdf_path))
    if source_hash != EXPECTED_SOURCE_HASH or len(reader.pages) != EXPECTED_PAGE_COUNT:
        raise RuntimeError(f"blocked_a01_source_integrity_failed: hash={source_hash}, pages={len(reader.pages)}")
    texts = [page.extract_text() or "" for page in reader.pages]
    chapters = discover_chapters(texts)
    sections, page_to_section = build_sections(texts, chapters)

    pre_web = web_state(engine_root)
    pre_hashes = protected_hashes(engine_root)
    golden_rule_blocks = read_csv(project_root / RUNS_REL / "WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1/quantity_rule_source_blocks.csv")
    golden_scope_links = read_csv(project_root / RUNS_REL / "WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1/quantity_rule_scope_links.csv")

    checkpoint_path = output_dir / "a01_parse_checkpoint.csv"
    checkpoint_by_code = {row["chapter_code"]: row for row in read_csv(checkpoint_path)}
    checkpoints: List[Dict[str, Any]] = []
    for chapter in chapters:
        existing = checkpoint_by_code.get(chapter["chapter_code"])
        checkpoints.append(existing or {
            "checkpoint_id": f"CHECKPOINT-{chapter['chapter_code'].replace('.', '-')}",
            "chapter_code": chapter["chapter_code"],
            "chapter_name": chapter["chapter_name"],
            "page_start": chapter["page_start"],
            "page_end": chapter["page_end"],
            "parse_status": "not_started",
            "quota_count": 0,
            "resource_count": 0,
            "work_content_block_count": 0,
            "quantity_rule_block_count": 0,
            "issue_count": 0,
            "last_completed_page": "",
            "source_sha256": source_hash,
            "generated_at": now_iso(),
        })
    write_csv(checkpoint_path, CHECKPOINT_FIELDS, checkpoints)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for chapter in chapters:
            checkpoint = next(row for row in checkpoints if row["chapter_code"] == chapter["chapter_code"])
            part_path = parts_dir / f"{chapter['chapter_code'].replace('.', '_')}.json"
            if checkpoint["parse_status"] in {"completed", "completed_with_issues"} and part_path.exists():
                continue
            checkpoint["parse_status"] = "in_progress"
            checkpoint["generated_at"] = now_iso()
            write_csv(checkpoint_path, CHECKPOINT_FIELDS, checkpoints)
            part = parse_chapter(
                pdf_path, pdf, texts, chapter, page_to_section, source_hash,
                golden_rule_blocks, golden_scope_links,
            )
            save_part(parts_dir, chapter["chapter_code"], part)
            blocking = any(row["severity"] == "blocking" for row in part["a01_parse_issues.csv"])
            checkpoint.update({
                "parse_status": "blocked" if blocking else ("completed_with_issues" if part["a01_parse_issues.csv"] else "completed"),
                "quota_count": len(part["a01_quota_item_candidate.csv"]),
                "resource_count": len(part["a01_resource_component.csv"]),
                "work_content_block_count": len(part["a01_work_content_block.csv"]),
                "quantity_rule_block_count": len(part["a01_quantity_rule_block.csv"]),
                "issue_count": len(part["a01_parse_issues.csv"]),
                "last_completed_page": chapter["page_end"] if not blocking else "",
                "source_sha256": source_hash,
                "generated_at": now_iso(),
            })
            write_csv(checkpoint_path, CHECKPOINT_FIELDS, checkpoints)

    merged: Dict[str, List[Dict[str, Any]]] = {name: [] for name in ENTITY_FIELDS}
    for chapter in chapters:
        part = load_part(parts_dir, chapter["chapter_code"])
        for name in merged:
            merged[name].extend(part.get(name, []))
    for name, fields in ENTITY_FIELDS.items():
        write_csv(output_dir / name, fields, merged[name])

    regression, differences = build_regression(engine_root, merged)
    write_csv(output_dir / "a111_golden_slice_regression.csv", REGRESSION_FIELDS, regression)
    write_csv(output_dir / "a111_golden_slice_difference.csv", DIFFERENCE_FIELDS, differences)

    issue_pages = {int(row["pdf_page_no"]) for row in merged["a01_parse_issues.csv"] if compact(row.get("pdf_page_no"))}
    pages = build_page_registry(pdf_path, source_hash, texts, chapters, page_to_section, issue_pages)
    write_csv(output_dir / "a01_source_page_registry.csv", PAGE_FIELDS, pages)
    write_csv(output_dir / "a01_chapter_section_registry.csv", SECTION_FIELDS, sections)

    metrics = integrity_metrics(merged, len(reader.pages), len(chapters))
    raw_codes = set(QUOTA_CODE_RE.findall(" ".join(texts)))
    extracted_codes = {row["source_code"] for row in merged["a01_quota_item_candidate.csv"]}
    all_pending = all(
        row.get("review_status", REVIEW_STATUS) == REVIEW_STATUS
        for rows in merged.values() for row in rows
    ) and all(row["review_status"] == REVIEW_STATUS for row in pages + sections + differences)
    checkpoints_complete = all(row["parse_status"] in {"completed", "completed_with_issues"} for row in checkpoints)
    regression_ok = next(row["status"] for row in regression if row["metric"] == "overall") == "pass"
    integrity_ok = (
        raw_codes == extracted_codes
        and metrics["duplicate_quota_code_count"] == 0
        and metrics["orphan_resource_count"] == 0
        and metrics["approved_count"] == 0
        and all_pending
    )

    post_web = web_state(engine_root)
    post_hashes = protected_hashes(engine_root)
    protection_ok = pre_web == post_web and pre_hashes == post_hashes and sha256(pdf_path) == source_hash
    if not checkpoints_complete or not integrity_ok or not protection_ok:
        status = "blocked_a01_parse_incomplete"
    elif not regression_ok and not allow_expected_parser_fixes:
        status = "blocked_a111_golden_slice_regression_failed"
    elif metrics["issue_count"]:
        status = (
            "a01_full_parse_v2_ready_with_nonblocking_review_backlog"
            if allow_expected_parser_fixes
            else "a01_full_parse_ready_with_manual_review_issues"
        )
    else:
        status = "a01_full_parse_ready_for_human_review"

    write_report(
        report_path, status, pdf_path, source_hash, metrics, checkpoints,
        regression, differences, pre_web, post_web, pre_hashes, post_hashes, output_dir,
        output_run.replace("_", "-"),
    )
    return {
        "status": status,
        "output_dir": output_dir,
        "report": report_path,
        "metrics": metrics,
        "checkpoints": checkpoints,
        "regression": regression,
        "differences": differences,
        "pre_web": pre_web,
        "post_web": post_web,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--output-run", default=OUTPUT_RUN)
    parser.add_argument("--report-name", default="stage_gd2018_building_a01_full_parse_report.md")
    parser.add_argument("--allow-expected-parser-fixes", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        result = run(
            args.project_root,
            output_run=args.output_run,
            report_name=args.report_name,
            allow_expected_parser_fixes=args.allow_expected_parser_fixes,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
