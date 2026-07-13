#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Parse an A02/A03 GD2018 building volume with the A01-v2 shared parser."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pdfplumber
from pypdf import PdfReader

import stage_gd2018_building_a01_full_parse as base


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
CONFIGS = {
    "A02": {
        "source_glob": "A02_*.pdf",
        "source_hash": "41ae25cd317d6236299bc80a3e98c14a23f024f895f3df033ce1b5cdc402508a",
        "page_count": 583,
        "chapter_numbers": tuple(range(12, 20)),
        "source_document_id": "SRC-GD2018-A02-2018",
        "source_volume": "中册",
        "output_run": "GD2018_BUILDING_A02_FULL_PARSE_1",
        "prefix": "a02",
    },
    "A03": {
        "source_glob": "A03_*.pdf",
        "source_hash": "a4deec195631217fd25f37eb57a0d0496e4873d0e74f4720c1a1b632adfe2c66",
        "page_count": 376,
        "chapter_numbers": tuple(range(20, 28)),
        "source_document_id": "SRC-GD2018-A03-2018",
        "source_volume": "下册",
        "output_run": "GD2018_BUILDING_A03_FULL_PARSE_1",
        "prefix": "a03",
    },
}


def configure(config: Dict[str, Any]) -> None:
    base.SOURCE_DOCUMENT_ID = config["source_document_id"]
    base.ARTIFACT_VOLUME_TAG = config["prefix"].upper()
    base.SOURCE_VOLUME = config["source_volume"]
    base.EXPECTED_SOURCE_HASH = config["source_hash"]
    base.EXPECTED_PAGE_COUNT = config["page_count"]


def find_pdf(engine_root: Path, pattern: str) -> Path:
    matches = list((engine_root / "data/private/reference_extraction/source_standards").rglob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one authority PDF for {pattern}, found {len(matches)}")
    return matches[0]


def chapter_name(lines: Sequence[str], code: str) -> str:
    for index, line in enumerate(lines):
        value = base.compact(line)
        if value == code:
            return next((base.compact(item) for item in lines[index + 1 :] if base.compact(item)), "")
        if value.startswith(code + " "):
            return base.compact(value[len(code) :])
    return ""


def discover_chapters(texts: Sequence[str], numbers: Sequence[int]) -> List[Dict[str, Any]]:
    titles: Dict[int, Tuple[int, str]] = {}
    for page_no, text in enumerate(texts, start=1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for number in numbers:
            code = f"A.1.{number}"
            if number not in titles and any(base.compact(line) == code for line in lines):
                titles[number] = (page_no, chapter_name(lines, code))
    missing = [number for number in numbers if number not in titles]
    if missing:
        raise RuntimeError(f"Chapter title pages not found: {missing}")
    chapters: List[Dict[str, Any]] = []
    ordered = sorted(numbers)
    for index, number in enumerate(ordered):
        code = f"A.1.{number}"
        start, name = titles[number]
        end = titles[ordered[index + 1]][0] - 1 if index + 1 < len(ordered) else len(texts)
        code_re = re.compile(rf"\bA1-{number}-\d+(?:-\d+)?\b")
        pages = [page_no for page_no in range(start, end + 1) if code_re.search(texts[page_no - 1])]
        chapters.append({
            "chapter_code": code,
            "chapter_name": name,
            "page_start": start,
            "page_end": end,
            "table_start": min(pages) if pages else end + 1,
            "has_quota_codes": bool(pages),
        })
    return chapters


def empty_part() -> Dict[str, List[Dict[str, Any]]]:
    return {name: [] for name in base.ENTITY_FIELDS}


def parse_context_only_chapter(
    chapter: Dict[str, Any], texts: Sequence[str], page_to_section: Dict[int, Tuple[str, str]],
) -> Dict[str, List[Dict[str, Any]]]:
    part = empty_part()
    chapter_code = chapter["chapter_code"]
    for page_no in range(chapter["page_start"], chapter["page_end"] + 1):
        raw = base.compact(texts[page_no - 1])
        if not raw:
            continue
        section_code = page_to_section[page_no][0]
        part["a01_note_clause.csv"].append({
            "note_clause_id": base.volume_id("NOTE", chapter_code, page_no, "context_or_measure_table", raw),
            "chapter_code": chapter_code,
            "section_code": section_code,
            "clause_type": "措施项目说明或表格证据",
            "clause_text": raw,
            "include_exclude_flag": "",
            "calculation_basis": "计算口径" if any(token in raw for token in ("计算", "计取", "费率")) else "",
            "pdf_page_no": page_no,
            "source_document_id": base.SOURCE_DOCUMENT_ID,
            "review_status": base.REVIEW_STATUS,
            "parse_confidence": "0.70",
            "remark": "chapter contains no A1 quota code; retained as page-level authority evidence without fabricating quota rows",
        })
        if any(token in raw for token in ("换算", "系数", "乘以")):
            part["a01_conversion_rule.csv"].append({
                "conversion_rule_id": base.volume_id("CONV", chapter_code, page_no, raw),
                "chapter_code": chapter_code,
                "section_code": section_code,
                "conversion_condition": raw,
                "labor_coefficient": base.coefficient(raw, ["人工"]),
                "material_coefficient": base.coefficient(raw, ["材料"]),
                "machine_coefficient": base.coefficient(raw, ["机具", "机械"]),
                "equipment_coefficient": base.coefficient(raw, ["设备"]),
                "main_material_coefficient": base.coefficient(raw, ["主材"]),
                "unit_price_coefficient": base.coefficient(raw, ["基价", "单价"]),
                "applicable_scope": chapter_code,
                "pdf_page_no": page_no,
                "source_text_raw": raw,
                "source_document_id": base.SOURCE_DOCUMENT_ID,
                "review_status": base.REVIEW_STATUS,
                "parse_confidence": "0.60",
                "remark": "context-only chapter coefficient candidate; pending human review",
            })
    part["a01_parse_issues.csv"].append(base.make_issue(
        "manual_review_required", "medium", chapter_code,
        "The chapter contains authority measure-item descriptions or fee tables but no A1 quota codes.",
        "Review the retained page-level evidence; do not fabricate quota rows.",
        pdf_page_no=chapter["page_start"], field_name="chapter_context",
    ))
    return part


def protected_state(engine_root: Path) -> Dict[str, str]:
    roots = [
        engine_root / "data/private/reference_extraction/runs/GD2018_BUILDING_A01_FULL_PARSE_1",
        engine_root / "data/private/reference_extraction/runs/GD2018_BUILDING_A01_FULL_PARSE_2",
        engine_root / "data/private/reference_extraction/runs/GOLDEN_SLICE_GD2018_A111_V2_CANDIDATE",
    ]
    state: Dict[str, str] = {}
    for root in roots:
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(base.sha256(path).encode("ascii"))
        state[root.name] = digest.hexdigest()
    db = engine_root / "web_collab_prototype/data/web_collab_readonly.sqlite"
    state[db.name] = base.sha256(db)
    return state


def rename_output(name: str, prefix: str) -> str:
    return name.replace("a01_", f"{prefix}_", 1)


def run(project_root: Path, volume_code: str) -> Dict[str, Any]:
    config = CONFIGS[volume_code]
    configure(config)
    engine_root = project_root / base.ENGINE_REL
    output_dir = project_root / base.RUNS_REL / config["output_run"]
    report_path = output_dir / f"stage_gd2018_building_{config['prefix']}_full_parse_report.md"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"Historical/current run exists; refusing to overwrite: {output_dir}")
    output_dir.mkdir(parents=True)
    parts_dir = output_dir / ".checkpoint_parts"
    checkpoint_path = output_dir / f"{config['prefix']}_parse_checkpoint.csv"

    pdf_path = find_pdf(engine_root, config["source_glob"])
    source_hash = base.sha256(pdf_path)
    reader = PdfReader(str(pdf_path))
    if source_hash != config["source_hash"] or len(reader.pages) != config["page_count"]:
        raise RuntimeError(f"blocked_{config['prefix']}_source_integrity_failed")
    texts = [page.extract_text() or "" for page in reader.pages]
    chapters = discover_chapters(texts, config["chapter_numbers"])
    sections, page_to_section = base.build_sections(texts, chapters)
    pre_protected = protected_state(engine_root)
    pre_web = base.web_state(engine_root)

    checkpoints = [{
        "checkpoint_id": f"CHECKPOINT-{config['prefix'].upper()}-{chapter['chapter_code'].replace('.', '-')}",
        "chapter_code": chapter["chapter_code"], "chapter_name": chapter["chapter_name"],
        "page_start": chapter["page_start"], "page_end": chapter["page_end"],
        "parse_status": "not_started", "quota_count": 0, "resource_count": 0,
        "work_content_block_count": 0, "quantity_rule_block_count": 0,
        "issue_count": 0, "last_completed_page": "", "source_sha256": source_hash,
        "generated_at": base.now_iso(),
    } for chapter in chapters]
    base.write_csv(checkpoint_path, base.CHECKPOINT_FIELDS, checkpoints)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for chapter, checkpoint in zip(chapters, checkpoints):
            checkpoint["parse_status"] = "in_progress"
            checkpoint["generated_at"] = base.now_iso()
            base.write_csv(checkpoint_path, base.CHECKPOINT_FIELDS, checkpoints)
            if chapter["has_quota_codes"]:
                part = base.parse_chapter(pdf_path, pdf, texts, chapter, page_to_section, source_hash, [], [])
            else:
                part = parse_context_only_chapter(chapter, texts, page_to_section)
            base.save_part(parts_dir, chapter["chapter_code"], part)
            blocking = any(row["severity"] == "blocking" for row in part["a01_parse_issues.csv"])
            checkpoint.update({
                "parse_status": "blocked" if blocking else ("completed_with_issues" if part["a01_parse_issues.csv"] else "completed"),
                "quota_count": len(part["a01_quota_item_candidate.csv"]),
                "resource_count": len(part["a01_resource_component.csv"]),
                "work_content_block_count": len(part["a01_work_content_block.csv"]),
                "quantity_rule_block_count": len(part["a01_quantity_rule_block.csv"]),
                "issue_count": len(part["a01_parse_issues.csv"]),
                "last_completed_page": chapter["page_end"] if not blocking else "",
                "source_sha256": source_hash, "generated_at": base.now_iso(),
            })
            base.write_csv(checkpoint_path, base.CHECKPOINT_FIELDS, checkpoints)

    merged = empty_part()
    for chapter in chapters:
        part = base.load_part(parts_dir, chapter["chapter_code"])
        for name in merged:
            merged[name].extend(part.get(name, []))
    for name, fields in base.ENTITY_FIELDS.items():
        base.write_csv(output_dir / rename_output(name, config["prefix"]), fields, merged[name])

    issue_pages = {int(row["pdf_page_no"]) for row in merged["a01_parse_issues.csv"] if base.compact(row.get("pdf_page_no"))}
    pages = base.build_page_registry(pdf_path, source_hash, texts, chapters, page_to_section, issue_pages)
    base.write_csv(output_dir / f"{config['prefix']}_source_page_registry.csv", base.PAGE_FIELDS, pages)
    base.write_csv(output_dir / f"{config['prefix']}_chapter_section_registry.csv", base.SECTION_FIELDS, sections)

    quota = merged["a01_quota_item_candidate.csv"]
    resources = merged["a01_resource_component.csv"]
    issues = merged["a01_parse_issues.csv"]
    source_codes = [row["source_code"] for row in quota]
    quota_uids = {row["quota_uid"] for row in quota}
    raw_codes = set(base.QUOTA_CODE_RE.findall(" ".join(texts)))
    extracted_codes = set(source_codes)
    target = [row for row in resources if row["resource_code"] == "99450760"]
    duplicate_count = len(source_codes) - len(extracted_codes)
    orphan_count = sum(row["quota_uid"] not in quota_uids for row in resources)
    approved_count = sum(
        str(row.get("review_status", "")).lower() == "approved"
        for rows in merged.values() for row in rows
    )
    all_pending = all(
        row.get("review_status", base.REVIEW_STATUS) == base.REVIEW_STATUS
        for rows in merged.values() for row in rows
    ) and all(row["review_status"] == base.REVIEW_STATUS for row in pages + sections)
    blocking_count = sum(row["severity"] == "blocking" for row in issues)
    unit_unparsed_count = sum(row["issue_type"] == "unit_unparsed" for row in issues)
    category_fix_ok = all(row["resource_category"] == "material" for row in target)
    systematic_unit_error = unit_unparsed_count > max(5, len(quota) // 100)
    systematic_category_error = not category_fix_ok
    post_protected = protected_state(engine_root)
    post_web = base.web_state(engine_root)
    protection_ok = pre_protected == post_protected and pre_web == post_web and base.sha256(pdf_path) == source_hash
    integrity_ok = (
        raw_codes == extracted_codes and duplicate_count == 0 and orphan_count == 0
        and approved_count == 0 and all_pending and protection_ok
        and all(row["parse_status"] in {"completed", "completed_with_issues"} for row in checkpoints)
    )
    if blocking_count or not integrity_ok:
        status = f"blocked_{config['prefix']}_parse_integrity_failed"
    elif systematic_unit_error or systematic_category_error:
        status = f"blocked_{config['prefix']}_systematic_parser_error"
    elif issues:
        status = f"{config['prefix']}_full_parse_ready_with_nonblocking_review_backlog"
    else:
        status = f"{config['prefix']}_full_parse_ready_for_consolidation"

    issue_counts = Counter(row["issue_type"] for row in issues)
    metrics = {
        "status": status, "source_file": str(pdf_path), "source_sha256": source_hash,
        "page_count": len(reader.pages), "chapter_count": len(chapters),
        "quota_count": len(quota), "unique_quota_code_count": len(extracted_codes),
        "duplicate_quota_count": duplicate_count, "resource_count": len(resources),
        "orphan_resource_count": orphan_count, "issue_count": len(issues),
        "unit_unparsed_count": unit_unparsed_count, "blocking_issue_count": blocking_count,
        "approved_count": approved_count, "other_material_count": len(target),
        "other_material_material_count": sum(row["resource_category"] == "material" for row in target),
        "protected_state_unchanged": protection_ok,
    }
    report = f"""# Stage {config['output_run'].replace('_', '-')} Report

## Final Status

`{status}`

## Authority Source

- file: `{pdf_path}`
- SHA256: `{source_hash}`
- page_count: {len(reader.pages)}
- source_role: `authority_source`
- text layer used; no OCR and no source modification

## Parse Integrity

- chapters/checkpoints: {len(chapters)}/{len(checkpoints)}
- quota_count / unique / duplicate: {len(quota)} / {len(extracted_codes)} / {duplicate_count}
- resource_count / orphan: {len(resources)} / {orphan_count}
- issue_count: {len(issues)}
- issue distribution: `{json.dumps(dict(issue_counts), ensure_ascii=False)}`
- unit_unparsed: {unit_unparsed_count}
- 99450760 material: {sum(row['resource_category'] == 'material' for row in target)}/{len(target)}
- approved_count: {approved_count}; all business rows remain pending: {str(all_pending).lower()}

## Governance

- A01 V1/V2 and A1.1 V1/V2 protected state unchanged: {str(pre_protected == post_protected).lower()}
- existing A1.1 Web SQLite unchanged: {str(pre_web == post_web).lower()}
- normalized XLSX was not used to add or fill source records
- official PDF blanks were preserved
- context-only chapters were retained as evidence without fabricated quota rows

Output directory: `{output_dir}`
"""
    report_path.write_text(report, encoding="utf-8")
    checkpoint_md = output_dir / f"checkpoint_{config['prefix']}_complete.md"
    checkpoint_md.write_text(
        f"# {volume_code} Parse Checkpoint\n\n- status: `{status}`\n- source_sha256: `{source_hash}`\n"
        f"- quota_count: {len(quota)}\n- resource_count: {len(resources)}\n- issue_count: {len(issues)}\n"
        f"- output_manifest_sha256: `{manifest_hash(output_dir, exclude={checkpoint_md.name})}`\n",
        encoding="utf-8",
    )
    return {**metrics, "output_dir": str(output_dir), "report": str(report_path), "checkpoint": str(checkpoint_md)}


def manifest_hash(root: Path, exclude: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    excluded = exclude or set()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name not in excluded):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(base.sha256(path).encode("ascii"))
    return digest.hexdigest()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--volume", choices=sorted(CONFIGS), required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args.project_root, args.volume)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
