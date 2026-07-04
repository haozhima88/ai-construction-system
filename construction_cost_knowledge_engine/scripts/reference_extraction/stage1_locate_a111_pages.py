#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage 1 page registry locator for A.1.1 土石方工程.

This script is intentionally limited to directory-level extraction and page
boundary registration. It does not extract A1-1-* quota item details, does not
create standard_cost_item_reference candidates, and does not write any database.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("pypdf is required for Stage 1 PDF text extraction") from exc

DEFAULT_PDF_PATH = Path(
    r"C:\Users\haozh\Downloads\1. 广东省房屋建筑与装饰工程定额20190112(上册).pdf"
)
SOURCE_TYPE = "provincial_quota_pdf"
SOURCE_NAME = "广东省房屋建筑与装饰工程综合定额2018"
VOLUME = "上册"
SOURCE_PAGE_POLICY = "source_page = pdf_page"
CHAPTER_CODE = "A.1.1"
CHAPTER_NAME = "土石方工程"

REGISTRY_FIELDS = [
    "registry_id",
    "source_type",
    "source_name",
    "source_file",
    "source_file_hash",
    "volume",
    "chapter_code",
    "chapter_name",
    "section_code",
    "section_name",
    "registry_type",
    "book_start_page",
    "book_end_page",
    "pdf_start_page",
    "pdf_end_page",
    "pdf_start_page_index",
    "pdf_end_page_index",
    "toc_pdf_page",
    "source_page_policy",
    "evidence_text_sample",
    "extraction_confidence",
    "parse_issue",
    "remark",
]

REGISTRY_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "registry_id": "GD2018_A111_DESCRIPTION",
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": "A.1.1",
        "section_name": "说明",
        "registry_type": "chapter_description",
        "book_start_page": 11,
        "book_end_page": 14,
        "pdf_start_page": 51,
        "pdf_end_page": 54,
        "toc_pdf_page": 7,
        "markers": ["本章定额包括土方工程、石方工程、回填方及其他", "土壤分类表", "岩石分类表"],
        "base_confidence": 0.86,
        "remark": "Stage 0 candidate retained; pdf_page 54 has no extractable text and requires visual/manual confirmation.",
    },
    {
        "registry_id": "GD2018_A111_QUANTITY_RULES",
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": "A.1.1_RULES",
        "section_name": "工程量计算规则",
        "registry_type": "quantity_calculation_rules",
        "book_start_page": 15,
        "book_end_page": 18,
        "pdf_start_page": 55,
        "pdf_end_page": 58,
        "toc_pdf_page": 7,
        "markers": ["工程量计算规则", "土石方体积换算系数表", "挖土方工程量"],
        "base_confidence": 0.86,
        "remark": "Stage 0 candidate retained; pdf_page 58 has no extractable text and requires visual/manual confirmation.",
    },
    {
        "registry_id": "GD2018_A111_1_EARTHWORK",
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": "A.1.1.1",
        "section_name": "土方工程",
        "registry_type": "section",
        "book_start_page": 19,
        "book_end_page": 39,
        "pdf_start_page": 59,
        "pdf_end_page": 79,
        "toc_pdf_page": 7,
        "markers": ["A.1.1.1 土方工程", "平整场地、原土打夯", "机械垂直运输土方"],
        "base_confidence": 0.98,
        "remark": "Stage 0 candidate confirmed by TOC and section heading evidence.",
    },
    {
        "registry_id": "GD2018_A111_2_ROCKWORK",
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": "A.1.1.2",
        "section_name": "石方工程",
        "registry_type": "section",
        "book_start_page": 40,
        "book_end_page": 55,
        "pdf_start_page": 80,
        "pdf_end_page": 95,
        "toc_pdf_page": 8,
        "markers": ["A.1.1.2 石方工程", "人工凿石方", "人工装石方"],
        "base_confidence": 0.98,
        "remark": "Stage 0 candidate confirmed by TOC and section heading evidence.",
    },
    {
        "registry_id": "GD2018_A111_3_BACKFILL_OTHER",
        "chapter_code": CHAPTER_CODE,
        "chapter_name": CHAPTER_NAME,
        "section_code": "A.1.1.3",
        "section_name": "回填方及其他",
        "registry_type": "section",
        "book_start_page": 56,
        "book_end_page": 62,
        "pdf_start_page": 96,
        "pdf_end_page": 102,
        "toc_pdf_page": 8,
        "markers": ["A.1.1.3 回填方及其他", "回填土", "支挡土板"],
        "base_confidence": 0.88,
        "remark": "Directory range retained, but extracted table text appears to end at pdf_page 99; pdf_page 101 contains an A.1.2 divider title.",
    },
    {
        "registry_id": "GD2018_A112_STOP_BOUNDARY",
        "chapter_code": "A.1.2",
        "chapter_name": "围护及支护工程",
        "section_code": "A.1.2",
        "section_name": "STOP_BOUNDARY",
        "registry_type": "stop_boundary",
        "book_start_page": 63,
        "book_end_page": 63,
        "pdf_start_page": 103,
        "pdf_end_page": 103,
        "toc_pdf_page": 8,
        "markers": ["本章定额包括打拔钢板桩", "高压旋喷桩", "围护及支护工程"],
        "base_confidence": 0.94,
        "remark": "Use pdf_page 103 as A.1.2正文 stop boundary; pdf_page 101 already shows an A.1.2 divider title.",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def compact_text(text: str, limit: int | None = None) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    return compacted[:limit] if limit else compacted


def page_text(reader: PdfReader, pdf_page: int) -> str:
    if pdf_page < 1 or pdf_page > len(reader.pages):
        return ""
    return reader.pages[pdf_page - 1].extract_text() or ""


def range_text(reader: PdfReader, start_page: int, end_page: int) -> str:
    return "\n".join(page_text(reader, page) for page in range(start_page, end_page + 1))


def blank_pages(reader: PdfReader, start_page: int, end_page: int) -> List[int]:
    blanks = []
    for page in range(start_page, end_page + 1):
        if not compact_text(page_text(reader, page)):
            blanks.append(page)
    return blanks


def find_evidence(text: str, markers: Iterable[str]) -> str:
    compacted = compact_text(text)
    if not compacted:
        return ""
    for marker in markers:
        idx = compacted.find(marker)
        if idx >= 0:
            start = max(0, idx - 35)
            end = min(len(compacted), idx + len(marker) + 140)
            return compacted[start:end]
    return compacted[:180]


def build_registry(reader: PdfReader, pdf_path: Path, source_hash: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for definition in REGISTRY_DEFINITIONS:
        start = int(definition["pdf_start_page"])
        end = int(definition["pdf_end_page"])
        text = range_text(reader, start, end)
        blanks = blank_pages(reader, start, end)
        evidence = find_evidence(text, definition["markers"])
        parse_issues: List[str] = []
        if blanks:
            parse_issues.append("no_extractable_text_pdf_pages=" + ",".join(str(p) for p in blanks))
        if definition["registry_id"] == "GD2018_A111_3_BACKFILL_OTHER":
            early_boundary = compact_text(page_text(reader, 101))
            if "A.1.2" in early_boundary:
                parse_issues.append("pdf_page_101_contains_A.1.2_divider_title")
        confidence = float(definition["base_confidence"])
        if not evidence:
            confidence = max(0.0, confidence - 0.25)
        if parse_issues:
            confidence = max(0.0, confidence - 0.02)

        record: Dict[str, Any] = {
            "registry_id": definition["registry_id"],
            "source_type": SOURCE_TYPE,
            "source_name": SOURCE_NAME,
            "source_file": pdf_path.name,
            "source_file_hash": source_hash,
            "volume": VOLUME,
            "chapter_code": definition["chapter_code"],
            "chapter_name": definition["chapter_name"],
            "section_code": definition["section_code"],
            "section_name": definition["section_name"],
            "registry_type": definition["registry_type"],
            "book_start_page": definition["book_start_page"],
            "book_end_page": definition["book_end_page"],
            "pdf_start_page": start,
            "pdf_end_page": end,
            "pdf_start_page_index": start - 1,
            "pdf_end_page_index": end - 1,
            "toc_pdf_page": definition["toc_pdf_page"],
            "source_page_policy": SOURCE_PAGE_POLICY,
            "evidence_text_sample": evidence,
            "extraction_confidence": f"{confidence:.2f}",
            "parse_issue": "; ".join(parse_issues),
            "remark": definition["remark"],
        }
        records.append(record)
    return records


def write_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def write_json(path: Path, records: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "records": records}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_toc_extract(path: Path, reader: PdfReader) -> None:
    lines = ["# TOC Extract - A.1.1", "", "source_page_policy: source_page = pdf_page", ""]
    for pdf_page in (7, 8):
        lines.append(f"## pdf_page {pdf_page} / pdf_page_index {pdf_page - 1}")
        lines.append("")
        lines.append(page_text(reader, pdf_page).strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(records: List[Dict[str, Any]]) -> str:
    headers = [
        "registry_id",
        "section_code",
        "section_name",
        "registry_type",
        "book_pages",
        "pdf_pages",
        "confidence",
        "parse_issue",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for record in records:
        row = [
            record["registry_id"],
            record["section_code"],
            record["section_name"],
            record["registry_type"],
            f"{record['book_start_page']}-{record['book_end_page']}",
            f"{record['pdf_start_page']}-{record['pdf_end_page']}",
            record["extraction_confidence"],
            record["parse_issue"] or "",
        ]
        lines.append("| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |")
    return "\n".join(lines)


def write_report(path: Path, records: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    blank_pages_found = sorted(
        {
            int(page)
            for record in records
            for issue in [record.get("parse_issue", "")]
            for page in re.findall(r"no_extractable_text_pdf_pages=([0-9,]+)", issue)
            for page in page.split(",")
            if page
        }
    )
    boundary_note = "pdf_page 101 contains an A.1.2 divider title; pdf_page 103 is retained as the A.1.2正文 stop boundary."
    lines = [
        "# Stage 1 Page Registry Report - A.1.1 土石方工程",
        "",
        "## 1. Task Scope",
        "",
        "Stage 1 only: directory-level extraction, page registry creation, boundary confirmation, and file output. No A1-1-* quota details, no standard_cost_item_reference candidates, no database writes, no approval state changes, and no internal_price_library generation.",
        "",
        "## 2. Files and Hash",
        "",
        f"- source_file: `{metadata['source_file']}`",
        f"- source_file_hash: `{metadata['source_file_hash']}`",
        f"- pdf_page_count: {metadata['pdf_page_count']}",
        f"- generated_at: {metadata['generated_at']}",
        "",
        "## 3. Page Numbering Convention",
        "",
        "- `pdf_page_index`: programmatic 0-based page index.",
        "- `pdf_page`: PDF physical page number, 1-based.",
        "- `book_page`: printed page number inside the book.",
        "- `source_page_policy`: `source_page = pdf_page`.",
        "- In the A.1.1 range, `book_page = pdf_page - 40` is broadly observed, but registry evidence must be kept and blank/divider pages require manual confirmation.",
        "",
        "## 4. Page Registry Result",
        "",
        markdown_table(records),
        "",
        "## 5. Evidence Text Samples",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"### {record['registry_id']}",
                "",
                f"- section: {record['section_code']} {record['section_name']}",
                f"- pdf_pages: {record['pdf_start_page']}-{record['pdf_end_page']}",
                f"- evidence_text_sample: {record['evidence_text_sample']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 6. Confirmed Boundaries",
            "",
            "- TOC pages are confirmed at pdf_page 7-8.",
            "- A.1.1 description range is retained as book_page 11-14 / pdf_page 51-54.",
            "- A.1.1 quantity calculation rules range is retained as book_page 15-18 / pdf_page 55-58.",
            "- A.1.1.1 is confirmed as book_page 19-39 / pdf_page 59-79.",
            "- A.1.1.2 is confirmed as book_page 40-55 / pdf_page 80-95.",
            "- A.1.1.3 is retained as book_page 56-62 / pdf_page 96-102, with a boundary note below.",
            f"- {boundary_note}",
            "",
            "## 7. Parse Issues",
            "",
            f"- no_extractable_text_pdf_pages: {', '.join(str(p) for p in blank_pages_found) if blank_pages_found else 'none'}",
            "- Unit glyph issues such as private-use glyphs are not repaired in Stage 1; they are only registered as Stage 2 risk.",
            "- No page offset abnormality blocks Stage 2, but pdf_page 101 should be visually reviewed as an A.1.2 divider title before table-level extraction.",
            "",
            "## 8. Stage 2 Readiness",
            "",
            "Stage 2 may proceed after the page registry is accepted. Stage 2 should extract table-level source_code values and item candidates only within the confirmed A.1.1 ranges, while preserving `source_file`, `source_file_hash`, and `source_page` for every candidate.",
            "",
            "## 9. Go / No-Go Recommendation",
            "",
            "Go for Stage 2 planning/execution, with two controls: keep all item candidates as `pending`, and treat pdf_page 101 plus no-text pages as boundary/visual QA checkpoints.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_registry_doc(path: Path, records: List[Dict[str, Any]]) -> None:
    lines = [
        "# Stage 1 Page Registry - A.1.1 土石方工程",
        "",
        "This document mirrors the generated Stage 1 page registry for review. It is directory-level only and does not contain A1-1-* quota item detail candidates.",
        "",
        markdown_table(records),
        "",
        "## Notes",
        "",
        "- `source_page` uses `pdf_page`.",
        "- `pdf_page_index` is 0-based.",
        "- `book_page` is the printed page number inside the source book.",
        "- `data/private/reference_extraction/runs/A111_stage1/` contains generated private run artifacts and should not be committed.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Locate Stage 1 A.1.1 page registry boundaries.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH, help="Target Guangdong 2018 upper-volume PDF path.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="construction_cost_knowledge_engine project root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf
    project_root = args.project_root
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    private_run_dir = project_root / "data" / "private" / "reference_extraction" / "runs" / "A111_stage1"
    docs_dir = project_root / "docs" / "reference_extraction"
    private_run_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path))
    source_hash = sha256_file(pdf_path)
    records = build_registry(reader, pdf_path, source_hash)
    metadata = {
        "source_type": SOURCE_TYPE,
        "source_name": SOURCE_NAME,
        "source_file": pdf_path.name,
        "source_file_hash": source_hash,
        "volume": VOLUME,
        "pdf_page_count": len(reader.pages),
        "source_page_policy": SOURCE_PAGE_POLICY,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    csv_path = private_run_dir / "page_registry_A111.csv"
    json_path = private_run_dir / "page_registry_A111.json"
    toc_path = private_run_dir / "toc_extract_A111.txt"
    report_path = private_run_dir / "stage1_report_A111.md"
    registry_doc_path = docs_dir / "stage1_page_registry_A111.md"

    write_csv(csv_path, records)
    write_json(json_path, records, metadata)
    write_toc_extract(toc_path, reader)
    write_report(report_path, records, metadata)
    write_registry_doc(registry_doc_path, records)

    print(f"records={len(records)}")
    print(f"csv={csv_path}")
    print(f"json={json_path}")
    print(f"toc={toc_path}")
    print(f"report={report_path}")
    print(f"registry_doc={registry_doc_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
