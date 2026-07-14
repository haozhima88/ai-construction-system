#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage MAP-A1-BILL-CENTRIC-1 bill-centric review pack.

Builds a GB/T 50854 bill-item-first coverage table for all 472 bill items
against GD2018 A1 quota mapping candidates. Outputs are human review artifacts
only: no database writes, no approvals, no enterprise standard names, and no
bill_code write-back into quota references.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
GB_RUN_REL = RUNS_REL / "GB50854_2024_stageB_docx_full"
GD_A1_RUN_REL = RUNS_REL / "GD2018_stage2R_A1_full"
MAP_A1_RUN_REL = RUNS_REL / "MAP_A1_full_readiness"
OUTPUT_DIR_REL = RUNS_REL / "MAP_A1_bill_centric_review"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

REVIEW_STATUS = "pending"
STAGE_NAME = "MAP_A1_bill_centric_review"
RELEVANT_A1_APPENDICES = {"A", "B", "C", "E", "R"}

BILL_PATH_REL = GB_RUN_REL / "bill_item_reference_all_candidate.csv"
QUOTA_PATH_REL = GD_A1_RUN_REL / "standard_cost_item_reference_A1_candidate.csv"
MAPPING_PATH_REL = MAP_A1_RUN_REL / "quota_to_bill_mapping_A1_candidate.csv"
ISSUES_PATH_REL = MAP_A1_RUN_REL / "quota_to_bill_mapping_A1_issues.csv"

COVERAGE_FIELDS = [
    "bill_reference_id",
    "bill_code_9",
    "bill_name",
    "bill_appendix_code",
    "bill_appendix_name",
    "bill_section_code",
    "bill_section_name",
    "bill_unit",
    "bill_project_feature_raw",
    "bill_quantity_calculation_rule",
    "bill_work_content_raw",
    "total_a1_candidate_count",
    "direct_candidate_count",
    "feature_required_count",
    "work_content_component_count",
    "construction_method_only_count",
    "transport_or_disposal_count",
    "route_to_other_appendix_count",
    "no_direct_bill_item_count",
    "manual_review_required_count",
    "top_quota_source_codes",
    "top_quota_names",
    "top_quota_standard_name_candidates",
    "top_mapping_basis",
    "top_mapping_confidence",
    "coverage_status",
    "human_check_priority",
    "human_decision",
    "human_comment",
]

DETAIL_FIELDS = [
    "bill_code_9",
    "bill_name",
    "bill_appendix_code",
    "bill_appendix_name",
    "bill_section_code",
    "bill_section_name",
    "bill_unit",
    "quota_source_code",
    "quota_raw_name",
    "quota_standard_name_candidate",
    "quota_unit",
    "mapping_status",
    "mapping_type",
    "routing_status",
    "mapping_confidence",
    "mapping_basis",
    "review_status",
    "issue_types",
    "human_decision",
    "human_comment",
]

SUMMARY_FIELDS = [
    "bill_appendix_code",
    "bill_appendix_name",
    "bill_item_count",
    "bill_items_with_any_a1_candidate",
    "bill_items_with_direct_candidate",
    "bill_items_with_feature_required",
    "bill_items_with_work_content_component",
    "bill_items_with_transport_or_disposal",
    "bill_items_without_a1_candidate",
    "coverage_rate",
    "direct_coverage_rate",
    "readiness_level",
    "remark",
]

ISSUE_FIELDS = [
    "issue_id",
    "bill_code_9",
    "bill_name",
    "bill_appendix_code",
    "issue_type",
    "issue_detail",
    "severity",
    "suggested_action",
]

MANIFEST_FIELDS = [
    "stage_name",
    "artifact_name",
    "expected_path",
    "exists",
    "file_size_bytes",
    "row_count",
    "sha256",
    "created_or_modified_time",
    "source_file",
    "can_regenerate",
    "backup_required",
    "backup_path",
    "status",
    "remark",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT_DEFAULT))
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def row_count(path: Path) -> str:
    if path.suffix.lower() != ".csv" or not path.exists():
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return str(sum(1 for _ in csv.DictReader(handle)))


def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def valid_source_code(value: str) -> bool:
    return bool(re.fullmatch(r"A1-\d+(?:-\d+){1,2}", (value or "").strip()))


def valid_bill_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{9}", (value or "").strip()))


def is_explicit_manual_review(row: Dict[str, str]) -> bool:
    return (
        row.get("mapping_status") == "manual_review_required"
        or row.get("mapping_type") == "needs_manual_review"
        or row.get("routing_status") == "routed_to_manual_review"
    )


def status_weight(row: Dict[str, str]) -> Tuple[int, float]:
    order = {
        "direct_bill_candidate": 7,
        "feature_required": 6,
        "transport_or_disposal_related": 5,
        "bill_work_content_component": 4,
        "route_to_other_appendix": 3,
        "construction_method_only": 2,
        "manual_review_required": 1,
        "no_direct_bill_item": 0,
    }
    return (order.get(row.get("mapping_status", ""), 0), to_float(row.get("mapping_confidence", "")))


def top_values(rows: Sequence[Dict[str, str]], key: str, limit: int = 8) -> str:
    values: List[str] = []
    seen = set()
    for row in rows:
        value = (row.get(key) or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
        if len(values) >= limit:
            break
    return ";".join(values)


def build_issue_lookup(issue_rows: Sequence[Dict[str, str]]) -> Dict[str, str]:
    by_quota: Dict[str, List[str]] = defaultdict(list)
    for row in issue_rows:
        code = row.get("quota_source_code", "")
        issue_type = row.get("issue_type", "")
        if code and issue_type and issue_type not in by_quota[code]:
            by_quota[code].append(issue_type)
    return {code: ";".join(types) for code, types in by_quota.items()}


def validate_inputs(
    bills: Sequence[Dict[str, str]],
    quotas: Sequence[Dict[str, str]],
    mappings: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    bill_codes = [row.get("bill_code_9", "") for row in bills]
    quota_codes = [row.get("source_code", "") for row in quotas]
    return {
        "bill_rows": len(bills),
        "invalid_bill_code_count": sum(1 for code in bill_codes if not valid_bill_code(code)),
        "duplicate_bill_code_count": sum(1 for _, count in Counter(bill_codes).items() if count > 1),
        "bill_non_pending_count": sum(1 for row in bills if row.get("review_status") != REVIEW_STATUS),
        "quota_rows": len(quotas),
        "invalid_quota_source_code_count": sum(1 for code in quota_codes if not valid_source_code(code)),
        "quota_non_pending_count": sum(1 for row in quotas if row.get("review_status") != REVIEW_STATUS),
        "mapping_rows": len(mappings),
        "mapping_missing_routing_count": sum(1 for row in mappings if not row.get("routing_status")),
        "mapping_approved_count": sum(1 for row in mappings if row.get("review_status") == "approved"),
        "mapping_non_pending_count": sum(1 for row in mappings if row.get("review_status") != REVIEW_STATUS),
    }


def classify_coverage(bill: Dict[str, str], counts: Counter, total: int) -> Tuple[str, str]:
    appendix = bill.get("appendix_code", "")
    relevant = appendix in RELEVANT_A1_APPENDICES
    if total == 0:
        if relevant:
            return "no_a1_candidate", "high" if appendix == "A" else "medium"
        return "not_relevant_to_gd2018_a1", "low"
    if counts.get("feature_required", 0) > 0:
        return "covered_feature_required", "high"
    if counts.get("transport_or_disposal_related", 0) > 0 or counts.get("manual_review_required", 0) > 0:
        return "needs_manual_review", "high"
    if counts.get("direct_bill_candidate", 0) > 0:
        return "covered_direct", "high" if total > 20 else "medium"
    if counts.get("bill_work_content_component", 0) > 0:
        return "covered_work_content_only", "medium"
    return "covered_weak", "medium" if relevant else "low"


def bill_identity(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "bill_reference_id": row.get("bill_reference_id", ""),
        "bill_code_9": row.get("bill_code_9", ""),
        "bill_name": row.get("bill_name", ""),
        "bill_appendix_code": row.get("appendix_code", ""),
        "bill_appendix_name": row.get("appendix_name", ""),
        "bill_section_code": row.get("section_code", ""),
        "bill_section_name": row.get("section_name", ""),
        "bill_unit": row.get("unit", ""),
        "bill_project_feature_raw": row.get("project_feature_raw", ""),
        "bill_quantity_calculation_rule": row.get("quantity_calculation_rule", ""),
        "bill_work_content_raw": row.get("work_content_raw", ""),
    }


def build_coverage_rows(
    bills: Sequence[Dict[str, str]],
    mappings_by_bill: Dict[str, List[Dict[str, str]]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for bill in bills:
        code = bill.get("bill_code_9", "")
        candidate_rows = sorted(mappings_by_bill.get(code, []), key=status_weight, reverse=True)
        counts = Counter(row.get("mapping_status", "") for row in candidate_rows)
        manual_review_count = sum(1 for row in candidate_rows if is_explicit_manual_review(row))
        total = len(candidate_rows)
        coverage_status, priority = classify_coverage(bill, counts, total)
        top_confidence = ""
        if candidate_rows:
            top_confidence = f"{max(to_float(row.get('mapping_confidence', '')) for row in candidate_rows):.2f}"
        row: Dict[str, Any] = {
            **bill_identity(bill),
            "total_a1_candidate_count": total,
            "direct_candidate_count": counts.get("direct_bill_candidate", 0),
            "feature_required_count": counts.get("feature_required", 0),
            "work_content_component_count": counts.get("bill_work_content_component", 0),
            "construction_method_only_count": counts.get("construction_method_only", 0),
            "transport_or_disposal_count": counts.get("transport_or_disposal_related", 0),
            "route_to_other_appendix_count": counts.get("route_to_other_appendix", 0),
            "no_direct_bill_item_count": counts.get("no_direct_bill_item", 0),
            "manual_review_required_count": manual_review_count,
            "top_quota_source_codes": top_values(candidate_rows, "quota_source_code"),
            "top_quota_names": top_values(candidate_rows, "quota_raw_name"),
            "top_quota_standard_name_candidates": top_values(candidate_rows, "quota_standard_name_candidate"),
            "top_mapping_basis": top_values(candidate_rows, "mapping_basis", limit=5),
            "top_mapping_confidence": top_confidence,
            "coverage_status": coverage_status,
            "human_check_priority": priority,
            "human_decision": "",
            "human_comment": "",
        }
        rows.append(row)
    return rows


def build_detail_rows(
    bill_by_code: Dict[str, Dict[str, str]],
    mappings: Sequence[Dict[str, str]],
    issue_lookup: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for mapping in sorted(
        (row for row in mappings if row.get("bill_code_9") in bill_by_code),
        key=lambda row: (row.get("bill_code_9", ""), row.get("quota_source_code", "")),
    ):
        bill = bill_by_code[mapping.get("bill_code_9", "")]
        rows.append(
            {
                "bill_code_9": bill.get("bill_code_9", ""),
                "bill_name": bill.get("bill_name", ""),
                "bill_appendix_code": bill.get("appendix_code", ""),
                "bill_appendix_name": bill.get("appendix_name", ""),
                "bill_section_code": bill.get("section_code", ""),
                "bill_section_name": bill.get("section_name", ""),
                "bill_unit": bill.get("unit", ""),
                "quota_source_code": mapping.get("quota_source_code", ""),
                "quota_raw_name": mapping.get("quota_raw_name", ""),
                "quota_standard_name_candidate": mapping.get("quota_standard_name_candidate", ""),
                "quota_unit": mapping.get("quota_unit", ""),
                "mapping_status": mapping.get("mapping_status", ""),
                "mapping_type": mapping.get("mapping_type", ""),
                "routing_status": mapping.get("routing_status", ""),
                "mapping_confidence": mapping.get("mapping_confidence", ""),
                "mapping_basis": mapping.get("mapping_basis", ""),
                "review_status": mapping.get("review_status", ""),
                "issue_types": issue_lookup.get(mapping.get("quota_source_code", ""), ""),
                "human_decision": "",
                "human_comment": "",
            }
        )
    return rows


def build_summary_rows(coverage_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in coverage_rows:
        grouped[row["bill_appendix_code"]].append(row)

    summary_rows: List[Dict[str, Any]] = []
    for appendix in sorted(grouped):
        rows = grouped[appendix]
        total = len(rows)
        any_count = sum(1 for row in rows if int(row["total_a1_candidate_count"]) > 0)
        direct = sum(1 for row in rows if int(row["direct_candidate_count"]) > 0)
        feature = sum(1 for row in rows if int(row["feature_required_count"]) > 0)
        work = sum(1 for row in rows if int(row["work_content_component_count"]) > 0)
        transport = sum(1 for row in rows if int(row["transport_or_disposal_count"]) > 0)
        without = total - any_count
        coverage_rate = any_count / total if total else 0.0
        direct_rate = direct / total if total else 0.0
        if appendix not in RELEVANT_A1_APPENDICES and any_count == 0:
            readiness = "not_applicable"
            remark = "No GD2018 A1 candidates and appendix is outside primary A1 review scope."
        elif transport > 0 or feature > 0:
            readiness = "manual_review_required"
            remark = "Contains feature-required or transport/disposal candidates; human review required."
        elif coverage_rate >= 0.65 and direct_rate >= 0.2:
            readiness = "high"
            remark = "Bill items have broad A1 candidate coverage with direct candidates present."
        elif coverage_rate >= 0.25:
            readiness = "medium"
            remark = "Bill items have partial A1 candidate coverage."
        elif any_count == 0:
            readiness = "manual_review_required" if appendix in RELEVANT_A1_APPENDICES else "not_applicable"
            remark = "No A1 candidates found; confirm whether this appendix should be outside A1."
        else:
            readiness = "low"
            remark = "Limited or weak A1 candidate coverage."
        summary_rows.append(
            {
                "bill_appendix_code": appendix,
                "bill_appendix_name": rows[0].get("bill_appendix_name", ""),
                "bill_item_count": total,
                "bill_items_with_any_a1_candidate": any_count,
                "bill_items_with_direct_candidate": direct,
                "bill_items_with_feature_required": feature,
                "bill_items_with_work_content_component": work,
                "bill_items_with_transport_or_disposal": transport,
                "bill_items_without_a1_candidate": without,
                "coverage_rate": f"{coverage_rate:.1%}",
                "direct_coverage_rate": f"{direct_rate:.1%}",
                "readiness_level": readiness,
                "remark": remark,
            }
        )
    return summary_rows


def add_issue(
    issues: List[Dict[str, str]],
    bill: Dict[str, Any],
    issue_type: str,
    detail: str,
    severity: str,
    action: str,
) -> None:
    issues.append(
        {
            "issue_id": f"ISSUE_BILL_CENTRIC_A1_{len(issues) + 1:05d}",
            "bill_code_9": bill.get("bill_code_9", ""),
            "bill_name": bill.get("bill_name", ""),
            "bill_appendix_code": bill.get("bill_appendix_code", ""),
            "issue_type": issue_type,
            "issue_detail": detail,
            "severity": severity,
            "suggested_action": action,
        }
    )


def build_issue_rows(coverage_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    add_issue(
        issues,
        {},
        "candidate_name_not_final_standard",
        "quota_standard_name_candidate values are lightly normalized quota descriptions, not final enterprise standard names.",
        "high",
        "Generate enterprise standard names only in reviewed mapping or enterprise template stages.",
    )
    for row in coverage_rows:
        total = int(row["total_a1_candidate_count"])
        appendix = row["bill_appendix_code"]
        if total == 0:
            severity = "high" if appendix == "A" else "medium" if appendix in RELEVANT_A1_APPENDICES else "low"
            add_issue(
                issues,
                row,
                "bill_without_a1_candidate",
                "This GB/T bill item has no attached GD2018 A1 quota candidate in the current mapping output.",
                severity,
                "Keep the bill item in review; confirm whether it is outside GD2018 A1 scope or requires additional extraction.",
            )
        if total > 25:
            add_issue(
                issues,
                row,
                "bill_with_too_many_candidates",
                f"This bill item has {total} A1 candidates and may be too broad for direct human confirmation.",
                "medium",
                "Review candidate grouping and project-feature boundaries before enterprise template drafting.",
            )
        direct = int(row["direct_candidate_count"])
        feature = int(row["feature_required_count"])
        work = int(row["work_content_component_count"])
        transport = int(row["transport_or_disposal_count"])
        route_other = int(row["route_to_other_appendix_count"])
        method = int(row["construction_method_only_count"])
        if transport > 0 and direct == 0 and feature == 0 and work == 0:
            add_issue(
                issues,
                row,
                "bill_with_transport_only_candidate",
                "Candidates for this bill are transport/disposal oriented rather than clear bill-item body rows.",
                "high",
                "Decide whether these rows are work content, disposal/transport cost, or manual review items.",
            )
        if total > 0 and direct == 0 and feature == 0 and work == 0 and transport == 0:
            add_issue(
                issues,
                row,
                "bill_with_only_weak_candidate",
                "This bill item only has weak, method, or route-to-other-appendix candidates.",
                "medium",
                "Do not treat the candidate as confirmed; require cost-department review.",
            )
        if route_other > 0 and appendix != "A":
            add_issue(
                issues,
                row,
                "appendix_mismatch",
                "GD2018 A1 quota rows were routed to a non-Appendix-A GB bill item.",
                "medium",
                "Confirm whether this is valid cross-appendix routing or a weak semantic candidate.",
            )
        if row["coverage_status"] in {"needs_manual_review", "covered_feature_required"} or method > 0:
            add_issue(
                issues,
                row,
                "manual_review_required",
                "This bill item has feature-required, transport/disposal, or construction-method-only candidates.",
                "high" if row["human_check_priority"] == "high" else "medium",
                "Have the cost department classify it before any enterprise standard or template use.",
            )
    return issues


def manifest_row(stage: str, artifact: str, path: Path, source_file: str, project_root: Path) -> Dict[str, str]:
    exists = path.exists()
    return {
        "stage_name": stage,
        "artifact_name": artifact,
        "expected_path": rel(path, project_root),
        "exists": str(exists).lower(),
        "file_size_bytes": str(path.stat().st_size) if exists else "",
        "row_count": row_count(path),
        "sha256": sha256(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": source_file,
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": "construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_MAP_A1_BILL_CENTRIC_1",
        "status": "generated" if exists else "missing",
        "remark": "bill-centric pending review artifact; private artifact; not tracked by Git; no approved mappings",
    }


def update_manifest(project_root: Path, output_dir: Path) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    docs_dir = manifest_path.parent
    docs_dir.mkdir(parents=True, exist_ok=True)
    existing: List[Dict[str, str]] = []
    if manifest_path.exists():
        existing = read_csv(manifest_path)

    source_file = ";".join(
        [
            rel(project_root / BILL_PATH_REL, project_root),
            rel(project_root / QUOTA_PATH_REL, project_root),
            rel(project_root / MAPPING_PATH_REL, project_root),
            rel(project_root / ISSUES_PATH_REL, project_root),
        ]
    )
    artifacts = [
        "bill_to_quota_coverage_472.csv",
        "bill_to_quota_detail_A1.csv",
        "bill_coverage_summary_by_appendix.csv",
        "bill_centric_review_issues.csv",
        "stage_map_A1_bill_centric_review_report.md",
    ]
    replacement = {
        (STAGE_NAME, artifact): manifest_row(STAGE_NAME, artifact, output_dir / artifact, source_file, project_root)
        for artifact in artifacts
    }
    filtered = [row for row in existing if (row.get("stage_name"), row.get("artifact_name")) not in replacement]
    filtered.extend(replacement.values())
    write_csv(manifest_path, MANIFEST_FIELDS, filtered)
    write_manifest_md(project_root, filtered)


def write_manifest_md(project_root: Path, rows: Sequence[Dict[str, str]]) -> None:
    md_path = project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md"
    registered = len(rows)
    existing = sum(1 for row in rows if row.get("exists") == "true")
    missing = registered - existing
    latest = [row for row in rows if row.get("stage_name") == STAGE_NAME]
    lines = [
        "# Reference Artifact Manifest",
        "",
        "## Governance",
        "",
        "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
        "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
        "- Each completed stage must back up its `runs` output directory after validation.",
        "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
        "- Readiness and bill-centric review outputs are pending review artifacts only and do not approve mappings.",
        "",
        "## Current Manifest Summary",
        "",
        f"- registered_artifacts: {registered}",
        f"- existing_artifacts: {existing}",
        f"- missing_artifacts: {missing}",
        "",
        "## Manifest CSV",
        "",
        "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
        "",
        "## Latest Bill-Centric Review Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_MAP_A1_BILL_CENTRIC_1/`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    path: Path,
    validation: Dict[str, Any],
    coverage_rows: Sequence[Dict[str, Any]],
    detail_rows: Sequence[Dict[str, Any]],
    summary_rows: Sequence[Dict[str, Any]],
    issue_rows: Sequence[Dict[str, str]],
) -> str:
    covered = sum(1 for row in coverage_rows if int(row["total_a1_candidate_count"]) > 0)
    no_candidate = len(coverage_rows) - covered
    high_priority = sum(1 for row in coverage_rows if row["human_check_priority"] == "high")
    status_counts = Counter(row["coverage_status"] for row in coverage_rows)
    recommendation = "bill_centric_review_ready_for_human_check"
    if validation["bill_rows"] != 472 or len(coverage_rows) != 472:
        recommendation = "bill_centric_review_partial_manual_intervention_required"
    if validation["mapping_missing_routing_count"] or validation["mapping_approved_count"] or validation["mapping_non_pending_count"]:
        recommendation = "bill_centric_review_partial_manual_intervention_required"

    lines = [
        "# Stage MAP-A1-BILL-CENTRIC-1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Generate a GB/T 50854 bill-centric review table for all 472 bill items against GD2018 A1 quota mapping candidates. This is a human review artifact only.",
        "",
        "## 2. Why Bill-Centric View Is Needed",
        "",
        "The previous readiness output is quota-centric: each GD2018 A1 quota row routes toward a bill item, work content, method, transport, or manual review. Cost reviewers also need the inverse view: each national bill item must remain visible even when no Guangdong A1 candidate exists.",
        "",
        "## 3. Input Files",
        "",
        f"- `{BILL_PATH_REL.as_posix()}`",
        f"- `{QUOTA_PATH_REL.as_posix()}`",
        f"- `{MAPPING_PATH_REL.as_posix()}`",
        f"- `{ISSUES_PATH_REL.as_posix()}`",
        "",
        "## 4. Bill Reference Summary",
        "",
        f"- bill item rows: {validation['bill_rows']}",
        f"- invalid bill_code_9: {validation['invalid_bill_code_count']}",
        f"- duplicate bill_code_9: {validation['duplicate_bill_code_count']}",
        f"- non-pending review_status: {validation['bill_non_pending_count']}",
        "",
        "## 5. A1 Quota Reference Summary",
        "",
        f"- A1 quota rows: {validation['quota_rows']}",
        f"- invalid source_code: {validation['invalid_quota_source_code_count']}",
        f"- non-pending quota review_status: {validation['quota_non_pending_count']}",
        f"- mapping rows: {validation['mapping_rows']}",
        f"- mapping rows missing routing_status: {validation['mapping_missing_routing_count']}",
        f"- approved mapping rows: {validation['mapping_approved_count']}",
        "",
        "## 6. Coverage Result for 472 Bill Items",
        "",
        f"- bill_to_quota_coverage_472 rows: {len(coverage_rows)}",
        f"- bill items with any A1 candidate: {covered}",
        f"- bill items without A1 candidate: {no_candidate}",
        f"- bill_to_quota_detail_A1 rows: {len(detail_rows)}",
        f"- high-priority human check items: {high_priority}",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## 7. Appendix-Level Coverage Summary",
            "",
            "| appendix | bill_items | with_candidate | without_candidate | coverage_rate | direct_rate | readiness |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['bill_appendix_code']} {row['bill_appendix_name']} | {row['bill_item_count']} | {row['bill_items_with_any_a1_candidate']} | {row['bill_items_without_a1_candidate']} | {row['coverage_rate']} | {row['direct_coverage_rate']} | {row['readiness_level']} |"
        )
    lines.extend(
        [
            "",
            "## 8. Key High-Priority Human Review Areas",
            "",
            "- Bill items with feature_required candidates need project-feature confirmation before any template use.",
            "- Transport/disposal candidates must not be treated as direct bill-item body rows without cost-department review.",
            "- Appendix A/B/C/E/R bill items without A1 candidates should be checked for scope gaps or intended non-applicability.",
            "- Bill items with too many candidates need grouping or feature-boundary review before enterprise template drafting.",
            "",
            "## 9. Name Governance",
            "",
            "- `standard_cost_item_reference_A1_candidate.standard_name_candidate` is not the final standard name.",
            "- It is only a lightly cleaned candidate name derived from the GD2018 normalized Excel reference source.",
            "- A phrase such as `人工挖沟槽土方 一、二类土 深度在4m内` should be treated as a quota candidate description.",
            "- Future enterprise standard names should be generated only in an enterprise_template or reviewed mapping stage.",
            "- This stage must not generate approved enterprise `standard_name` values.",
            "",
            "## 10. Not Approved / Not Final Statement",
            "",
            "All generated rows remain `pending`. This stage does not approve mappings, does not write databases, does not write bill_code back into quota candidates, does not create `internal_price_library`, and does not generate final enterprise standard names.",
            "",
            "## 11. Next Step Recommendation",
            "",
            recommendation,
            "",
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return recommendation


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root)
    bill_path = project_root / BILL_PATH_REL
    quota_path = project_root / QUOTA_PATH_REL
    mapping_path = project_root / MAPPING_PATH_REL
    issue_path = project_root / ISSUES_PATH_REL
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    for required in [bill_path, quota_path, mapping_path, issue_path]:
        if not required.exists():
            raise FileNotFoundError(f"blocked_missing_inputs: {required}")

    bills = read_csv(bill_path)
    quotas = read_csv(quota_path)
    mappings = read_csv(mapping_path)
    mapping_issues = read_csv(issue_path)
    validation = validate_inputs(bills, quotas, mappings)

    bill_by_code = {row.get("bill_code_9", ""): row for row in bills}
    mappings_by_bill: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in mappings:
        code = row.get("bill_code_9", "")
        if code in bill_by_code:
            mappings_by_bill[code].append(row)

    issue_lookup = build_issue_lookup(mapping_issues)
    coverage_rows = build_coverage_rows(bills, mappings_by_bill)
    detail_rows = build_detail_rows(bill_by_code, mappings, issue_lookup)
    summary_rows = build_summary_rows(coverage_rows)
    bill_issue_rows = build_issue_rows(coverage_rows)

    write_csv(output_dir / "bill_to_quota_coverage_472.csv", COVERAGE_FIELDS, coverage_rows)
    write_csv(output_dir / "bill_to_quota_detail_A1.csv", DETAIL_FIELDS, detail_rows)
    write_csv(output_dir / "bill_coverage_summary_by_appendix.csv", SUMMARY_FIELDS, summary_rows)
    write_csv(output_dir / "bill_centric_review_issues.csv", ISSUE_FIELDS, bill_issue_rows)
    recommendation = write_report(
        output_dir / "stage_map_A1_bill_centric_review_report.md",
        validation,
        coverage_rows,
        detail_rows,
        summary_rows,
        bill_issue_rows,
    )
    update_manifest(project_root, output_dir)

    covered = sum(1 for row in coverage_rows if int(row["total_a1_candidate_count"]) > 0)
    high_priority = sum(1 for row in coverage_rows if row["human_check_priority"] == "high")
    print(f"bill_coverage_rows={len(coverage_rows)}")
    print(f"bill_detail_rows={len(detail_rows)}")
    print(f"bill_items_with_candidates={covered}")
    print(f"bill_items_without_candidates={len(coverage_rows) - covered}")
    print(f"high_priority_human_check_items={high_priority}")
    print(f"recommendation={recommendation}")
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
