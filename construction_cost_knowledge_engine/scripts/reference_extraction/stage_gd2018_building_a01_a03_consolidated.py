#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Consolidate immutable A01/A02/A03 PDF-derived building candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data/private/reference_extraction/runs"
OUTPUT_RUN = "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
VOLUMES = [
    {"volume_code": "A01", "volume_name": "上册", "run": "GD2018_BUILDING_A01_FULL_PARSE_2", "prefix": "a01", "expected_hash": "07cd7ac537b22d54b9676d4920bbeae80b8d17974ba43fb2b037301fd55e3132", "expected_pages": 704},
    {"volume_code": "A02", "volume_name": "中册", "run": "GD2018_BUILDING_A02_FULL_PARSE_1", "prefix": "a02", "expected_hash": "41ae25cd317d6236299bc80a3e98c14a23f024f895f3df033ce1b5cdc402508a", "expected_pages": 583},
    {"volume_code": "A03", "volume_name": "下册", "run": "GD2018_BUILDING_A03_FULL_PARSE_1", "prefix": "a03", "expected_hash": "a4deec195631217fd25f37eb57a0d0496e4873d0e74f4720c1a1b632adfe2c66", "expected_pages": 376},
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    temp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(sha256(path).encode("ascii"))
    return digest.hexdigest()


def normalized_code(value: str) -> str:
    return "".join(str(value or "").upper().split())


def consolidated_uid(source_code: str) -> str:
    return f"GD:2018:A:{normalized_code(source_code)}"


def source_context(volume: Dict[str, Any], pages: List[Dict[str, str]]) -> Dict[str, str]:
    first = pages[0]
    return {
        "source_document_id": first["source_document_id"], "volume_code": volume["volume_code"],
        "volume_name": volume["volume_name"], "source_file": first["source_file"],
        "source_sha256": first["source_sha256"],
    }


def add_context(row: Dict[str, str], context: Dict[str, str], page_field: str) -> Dict[str, str]:
    result = dict(row)
    result.update(context)
    result["pdf_page_no"] = row.get(page_field, row.get("pdf_page_no", ""))
    return result


def fields_for(rows: List[Dict[str, Any]], leading: Sequence[str] = ()) -> List[str]:
    seen = set(leading)
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field); fields.append(field)
    return fields


def run(project_root: Path) -> Dict[str, Any]:
    runs = project_root / RUNS_REL
    output_dir = runs / OUTPUT_RUN
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"Refusing to overwrite existing run: {output_dir}")
    output_dir.mkdir(parents=True)
    pre_hashes = {volume["run"]: tree_hash(runs / volume["run"]) for volume in VOLUMES}

    outputs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    documents: List[Dict[str, Any]] = []
    volume_metrics: List[Dict[str, Any]] = []
    source_code_volumes: Dict[str, set[str]] = defaultdict(set)

    for volume in VOLUMES:
        run_dir = runs / volume["run"]
        prefix = volume["prefix"]
        pages = read_csv(run_dir / f"{prefix}_source_page_registry.csv")
        context = source_context(volume, pages)
        if context["source_sha256"] != volume["expected_hash"] or len(pages) != volume["expected_pages"]:
            raise RuntimeError(f"Source integrity failed for {volume['volume_code']}")
        documents.append({
            **context, "source_role": "authority_source", "page_count": len(pages),
            "candidate_run": volume["run"], "review_status": "pending",
        })
        for row in pages:
            outputs["source_pages"].append({**row, **context})
        for row in read_csv(run_dir / f"{prefix}_chapter_section_registry.csv"):
            outputs["chapter_sections"].append(add_context(row, context, "page_start"))

        quota_rows = read_csv(run_dir / f"{prefix}_quota_item_candidate.csv")
        for row in quota_rows:
            code = normalized_code(row["source_code"])
            source_code_volumes[code].add(volume["volume_code"])
            outputs["quota_items"].append({
                **add_context(row, context, "page_start"), "source_code_normalized": code,
                "quota_uid": consolidated_uid(code), "original_quota_uid": row["quota_uid"],
            })
        for row in read_csv(run_dir / f"{prefix}_quota_price_snapshot.csv"):
            outputs["quota_price_snapshots"].append({
                **add_context(row, context, "source_page_no"),
                "quota_uid": consolidated_uid(row["source_code"]), "original_quota_uid": row["quota_uid"],
            })
        resource_rows = read_csv(run_dir / f"{prefix}_resource_component.csv")
        for row in resource_rows:
            outputs["resource_components"].append({
                **add_context(row, context, "source_page_no"),
                "quota_uid": consolidated_uid(row["quota_source_code"]), "original_quota_uid": row["quota_uid"],
            })
        for key, file_suffix, page_field in [
            ("work_content_blocks", "work_content_block", "page_start"),
            ("work_content_scope_links", "work_content_scope_link", ""),
            ("quantity_rule_blocks", "quantity_rule_block", "page_start"),
            ("quantity_rule_scope_links", "quantity_rule_scope_link", ""),
            ("conversion_rules", "conversion_rule", "pdf_page_no"),
            ("note_clauses", "note_clause", "pdf_page_no"),
            ("parse_issues", "parse_issues", "pdf_page_no"),
        ]:
            for row in read_csv(run_dir / f"{prefix}_{file_suffix}.csv"):
                item = add_context(row, context, page_field)
                if key.endswith("scope_links") and row.get("quota_uid"):
                    prefix_text = f"QUOTA-GD2018-{volume['volume_code']}-"
                    source_code = row["quota_uid"][len(prefix_text):] if row["quota_uid"].startswith(prefix_text) else ""
                    item["original_quota_uid"] = row["quota_uid"]
                    item["quota_uid"] = consolidated_uid(source_code) if source_code else ""
                outputs[key].append(item)
        volume_metrics.append({
            "volume_code": volume["volume_code"], "quota_count": len(quota_rows),
            "resource_count": len(resource_rows),
            "issue_count": len(read_csv(run_dir / f"{prefix}_parse_issues.csv")),
            "source_sha256": context["source_sha256"], "review_status": "pending",
        })

    quota = outputs["quota_items"]
    resources = outputs["resource_components"]
    uid_counts = Counter(row["quota_uid"] for row in quota)
    duplicate_rows = [{
        "quota_uid": uid, "source_code": next(row["source_code"] for row in quota if row["quota_uid"] == uid),
        "occurrence_count": count,
        "volume_codes": ";".join(sorted({row["volume_code"] for row in quota if row["quota_uid"] == uid})),
        "conflict_status": "blocking_duplicate", "review_status": "pending",
    } for uid, count in uid_counts.items() if count > 1]
    cross_volume_rows = [{
        "source_code_normalized": code, "volume_codes": ";".join(sorted(volumes)),
        "volume_count": len(volumes), "audit_status": "cross_volume_duplicate",
        "review_status": "pending",
    } for code, volumes in source_code_volumes.items() if len(volumes) > 1]
    quota_uids = set(uid_counts)
    orphan_rows = [{
        "resource_component_id": row["resource_component_id"], "quota_uid": row["quota_uid"],
        "quota_source_code": row["quota_source_code"], "volume_code": row["volume_code"],
        "orphan_reason": "quota_uid_not_found", "review_status": "pending",
    } for row in resources if row["quota_uid"] not in quota_uids]
    approved_count = sum(
        str(row.get("review_status", "")).lower() == "approved"
        for rows in outputs.values() for row in rows
    )
    all_pending = all(
        row.get("review_status", "pending") == "pending"
        for rows in outputs.values() for row in rows
    )
    post_hashes = {volume["run"]: tree_hash(runs / volume["run"]) for volume in VOLUMES}
    source_unchanged = pre_hashes == post_hashes
    status = (
        "blocked_consolidated_duplicate_conflict" if duplicate_rows or cross_volume_rows else
        "blocked_consolidated_integrity_failed" if orphan_rows or approved_count or not all_pending or not source_unchanged else
        "building_a_consolidated_ready_with_nonblocking_review_backlog" if outputs["parse_issues"] else
        "building_a_consolidated_ready_for_mapping"
    )

    file_map = {
        "source_pages": "gd_building_source_pages.csv", "chapter_sections": "gd_building_chapter_sections.csv",
        "quota_items": "gd_building_quota_items.csv", "quota_price_snapshots": "gd_building_quota_price_snapshots.csv",
        "resource_components": "gd_building_resource_components.csv", "work_content_blocks": "gd_building_work_content_blocks.csv",
        "work_content_scope_links": "gd_building_work_content_scope_links.csv", "quantity_rule_blocks": "gd_building_quantity_rule_blocks.csv",
        "quantity_rule_scope_links": "gd_building_quantity_rule_scope_links.csv", "conversion_rules": "gd_building_conversion_rules.csv",
        "note_clauses": "gd_building_note_clauses.csv", "parse_issues": "gd_building_parse_issues.csv",
    }
    write_csv(output_dir / "gd_building_source_documents.csv", fields_for(documents), documents)
    for key, name in file_map.items():
        leading = ["source_document_id", "volume_code", "volume_name", "source_file", "source_sha256", "pdf_page_no"]
        write_csv(output_dir / name, fields_for(outputs[key], leading), outputs[key])
    write_csv(output_dir / "gd_building_duplicate_audit.csv", ["quota_uid", "source_code", "occurrence_count", "volume_codes", "conflict_status", "review_status"], duplicate_rows)
    write_csv(output_dir / "gd_building_cross_volume_code_audit.csv", ["source_code_normalized", "volume_codes", "volume_count", "audit_status", "review_status"], cross_volume_rows)
    write_csv(output_dir / "gd_building_orphan_resource_audit.csv", ["resource_component_id", "quota_uid", "quota_source_code", "volume_code", "orphan_reason", "review_status"], orphan_rows)
    totals = {
        "volume_code": "TOTAL", "quota_count": len(quota), "resource_count": len(resources),
        "issue_count": len(outputs["parse_issues"]), "source_sha256": "three authority sources",
        "review_status": "pending",
    }
    dashboard = volume_metrics + [totals]
    for row in dashboard:
        row.update({
            "duplicate_quota_count": len(duplicate_rows), "cross_volume_duplicate_count": len(cross_volume_rows),
            "orphan_resource_count": len(orphan_rows), "approved_count": approved_count,
            "a04_count": 0, "c_count": 0, "d_count": 0, "e_count": 0,
            "final_status": status,
        })
    write_csv(output_dir / "gd_building_baseline_dashboard.csv", fields_for(dashboard), dashboard)

    report_path = output_dir / "stage_gd2018_building_a01_a03_consolidated_report.md"
    report_path.write_text(f"""# Stage GD2018-BUILDING-A01-A03-CONSOLIDATED-BASELINE-1 Report

## Final Status

`{status}`

## Consolidated Integrity

- source volumes: A01/A02/A03; A04/C/D/E rows: 0
- quota_count: {len(quota)}
- resource_count: {len(resources)}
- duplicate quota_uid: {len(duplicate_rows)}
- cross-volume duplicate code: {len(cross_volume_rows)}
- orphan resources: {len(orphan_rows)}
- parse issues retained: {len(outputs['parse_issues'])}
- approved_count: {approved_count}; all business records pending: {str(all_pending).lower()}

## Governance

- quota_uid format: `GD:2018:A:{{source_code_normalized}}`
- PDF authority records only; no XLSX supplementation or blank filling
- input run hashes unchanged: {str(source_unchanged).lower()}
- source document, volume, file, SHA256, PDF page, chapter and section lineage retained

Output directory: `{output_dir}`
""", encoding="utf-8")
    checkpoint = output_dir / "checkpoint_consolidation_complete.md"
    checkpoint.write_text(
        f"# Consolidation Checkpoint\n\n- status: `{status}`\n- quota_count: {len(quota)}\n"
        f"- resource_count: {len(resources)}\n- duplicate_count: {len(duplicate_rows)}\n"
        f"- orphan_resource_count: {len(orphan_rows)}\n- manifest_sha256: `{tree_hash(output_dir)}`\n",
        encoding="utf-8",
    )
    return {
        "status": status, "quota_count": len(quota), "resource_count": len(resources),
        "duplicate_count": len(duplicate_rows), "cross_volume_duplicate_count": len(cross_volume_rows),
        "orphan_resource_count": len(orphan_rows), "issue_count": len(outputs["parse_issues"]),
        "approved_count": approved_count, "source_hashes_unchanged": source_unchanged,
        "output_dir": str(output_dir), "report": str(report_path), "checkpoint": str(checkpoint),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    args = parser.parse_args()
    print(json.dumps(run(args.project_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
