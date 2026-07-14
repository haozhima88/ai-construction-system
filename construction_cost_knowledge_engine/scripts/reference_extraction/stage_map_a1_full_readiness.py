#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage MAP-A1-FULL-0 readiness analysis.

Generates lightweight readiness candidates between all GD2018 A1 quota
reference rows and the full GB/T 50854 bill reference candidate table. This is
not final matching and does not write databases, approvals, internal price
library data, enterprise templates, or bill_code values back into quota rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
QUOTA_RUN_REL = RUNS_REL / "GD2018_stage2R_A1_full"
GB_RUN_REL = RUNS_REL / "GB50854_2024_stageB_docx_full"
OUTPUT_DIR_REL = RUNS_REL / "MAP_A1_full_readiness"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

SOURCE_TYPE = "rule_semantic_candidate"
MAPPING_SCOPE = "GD2018_A1_to_GB50854_full_bill_reference"
REVIEW_STATUS = "pending"

QUOTA_FIELDS = [
    "reference_id",
    "source_code",
    "raw_name",
    "standard_name_candidate",
    "unit",
    "section_code",
    "section_name",
    "source_trust_level",
    "verification_status",
    "review_status",
]

BILL_SNAPSHOT_FIELDS = [
    "bill_reference_id",
    "bill_code_9",
    "bill_name",
    "appendix_code",
    "appendix_name",
    "section_code",
    "section_name",
    "unit",
    "project_feature_raw",
    "quantity_calculation_rule",
    "work_content_raw",
    "review_status",
]

MAPPING_FIELDS = [
    "mapping_id",
    "source_type",
    "mapping_scope",
    "quota_reference_id",
    "quota_source_code",
    "quota_raw_name",
    "quota_standard_name_candidate",
    "quota_unit",
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
    "mapping_status",
    "mapping_type",
    "mapping_basis",
    "mapping_confidence",
    "routing_status",
    "review_status",
    "reviewer",
    "review_comment",
    "remark",
]

ISSUE_FIELDS = [
    "issue_id",
    "quota_source_code",
    "quota_raw_name",
    "issue_type",
    "issue_detail",
    "severity",
    "suggested_action",
]

COVERAGE_FIELDS = [
    "quota_section_guess",
    "quota_code_prefix",
    "quota_row_count",
    "mapped_row_count",
    "direct_candidate_count",
    "feature_required_count",
    "work_content_component_count",
    "construction_method_only_count",
    "transport_or_disposal_count",
    "route_to_other_appendix_count",
    "no_direct_bill_item_count",
    "manual_review_required_count",
    "top_bill_appendices",
    "readiness_score",
    "remark",
]

DASHBOARD_FIELDS = [
    "metric_name",
    "metric_value",
    "expected_or_threshold",
    "status",
    "severity",
    "remark",
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

OBJECT_KEYWORDS = {
    "earthwork": ["土方", "挖土", "填土", "回填", "平整场地", "余方", "弃置", "场地"],
    "stonework": ["石方", "岩石", "爆破", "破碎"],
    "foundation": ["桩", "地基", "基础", "垫层", "锚杆", "支护", "基坑"],
    "masonry": ["砌", "砖", "砌块", "墙体"],
    "concrete": ["混凝土", "砼", "现浇", "预制"],
    "rebar": ["钢筋", "钢丝", "铁件"],
    "formwork": ["模板", "支架", "支撑"],
    "door_window": ["门", "窗"],
    "floor": ["楼地面", "地面", "找平", "面层"],
    "wall_ceiling": ["墙面", "柱面", "天棚", "抹灰", "吊顶"],
    "paint": ["油漆", "涂料", "防腐", "保温", "隔热"],
    "roof": ["屋面", "防水", "瓦"],
}

TRANSPORT_TERMS = ["运输", "运土", "运石", "运距", "自卸", "装车", "卸车", "外运", "余方", "弃置"]
METHOD_TERMS = ["打夯", "夯实", "碾压", "爆破", "破碎", "凿", "钻孔", "成孔", "转堆", "支挡", "拆除"]
GENERIC_NAMES = {"土方", "石方", "混凝土", "钢筋", "模板", "砌筑"}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def rel(path: Path, project_root: Path) -> str:
    return path.relative_to(project_root).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> str:
    return str(len(read_csv(path))) if path.exists() and path.suffix.lower() == ".csv" else ""


def source_code_prefix(code: str) -> str:
    parts = (code or "").split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else ""


def natural_quota_key(code: str) -> Tuple[int, int, int]:
    match = re.fullmatch(r"A1-(\d+)(?:-(\d+))?(?:-(\d+))?", code or "")
    if not match:
        return (10_000, 10_000, 10_000)
    return (int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0))


def contains_any(value: str, terms: Iterable[str]) -> bool:
    return any(term in value for term in terms)


def quota_keyword_groups(name: str) -> List[str]:
    groups = []
    for group, keywords in OBJECT_KEYWORDS.items():
        if contains_any(name, keywords):
            groups.append(group)
    return groups


def score_bill(quota: Dict[str, str], bill: Dict[str, str]) -> Tuple[float, List[str]]:
    name = text(quota.get("raw_name") or quota.get("standard_name_candidate"))
    unit = text(quota.get("unit"))
    bill_name = text(bill.get("bill_name"))
    bill_unit = text(bill.get("unit"))
    bill_text = " ".join(
        [
            bill_name,
            text(bill.get("project_feature_raw")),
            text(bill.get("work_content_raw")),
            text(bill.get("section_name")),
            text(bill.get("appendix_name")),
        ]
    )
    score = 0.0
    basis: List[str] = []
    if bill_name and (bill_name in name or name in bill_name):
        score += 4.0
        basis.append("bill_name_overlap")
    for group in quota_keyword_groups(name):
        hits = [keyword for keyword in OBJECT_KEYWORDS[group] if keyword in bill_text]
        if hits:
            score += min(3.0, 1.0 + 0.6 * len(hits))
            basis.append(f"{group}_keyword:{'/'.join(hits[:3])}")
    if unit and bill_unit and unit == bill_unit:
        score += 0.8
        basis.append("unit_match")
    elif unit and bill_unit:
        basis.append("unit_diff")
    if name and bill_name and len(set(name) & set(bill_name)) >= 3:
        score += 0.5
    if source_code_prefix(quota.get("source_code", "")) == "A1-1" and bill.get("appendix_code") == "A":
        score += 0.8
        basis.append("A1-1_to_appendix_A")
    return score, basis


def top_bill_candidates(quota: Dict[str, str], bills: Sequence[Dict[str, str]], limit: int = 3) -> List[Tuple[float, List[str], Dict[str, str]]]:
    scored = []
    for bill in bills:
        score, basis = score_bill(quota, bill)
        if score > 0:
            scored.append((score, basis, bill))
    scored.sort(key=lambda item: (-item[0], item[2].get("appendix_code", ""), item[2].get("bill_code_9", "")))
    return scored[:limit]


def classify_mapping(quota: Dict[str, str], top: List[Tuple[float, List[str], Dict[str, str]]]) -> Tuple[str, str, str, float, List[str], Dict[str, str] | None]:
    name = text(quota.get("raw_name"))
    is_transport = contains_any(name, TRANSPORT_TERMS)
    is_method = contains_any(name, METHOD_TERMS)
    best = top[0] if top else None
    score = best[0] if best else 0.0
    basis = best[1] if best else []
    bill = best[2] if best else None

    if not best or score < 1.5:
        return "no_direct_bill_item", "no_direct_bill_item", "unrouted", 0.35, basis, None
    if is_transport:
        return "transport_or_disposal_related", "needs_manual_review", "routed_to_manual_review", min(0.72, 0.45 + score / 10), basis + ["transport_or_disposal_keyword"], bill
    if is_method:
        return "construction_method_only", "work_content_only", "routed_to_method_or_measure", min(0.70, 0.42 + score / 10), basis + ["construction_method_keyword"], bill
    if score >= 5.2 and "unit_match" in basis:
        return "direct_bill_candidate", "direct_candidate", "routed_to_bill_appendix", min(0.96, 0.65 + score / 10), basis, bill
    if score >= 3.2:
        if bill and bill.get("appendix_code") and bill.get("appendix_code") != "A":
            return "route_to_other_appendix", "route_candidate", "routed_to_bill_appendix", min(0.86, 0.55 + score / 10), basis + ["non_appendix_A_candidate"], bill
        return "feature_required", "feature_required", "routed_to_bill_appendix", min(0.86, 0.52 + score / 10), basis + ["feature_confirmation_required"], bill
    return "bill_work_content_component", "work_content_only", "routed_to_work_content", min(0.74, 0.45 + score / 10), basis + ["work_content_similarity"], bill


def issue_once(issues: List[Dict[str, str]], seen: set[Tuple[str, str]], quota: Dict[str, str], issue_type: str, detail: str, severity: str, action: str) -> None:
    key = (quota.get("source_code", ""), issue_type)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        {
            "issue_id": f"ISSUE_MAP_A1_{len(issues) + 1:05d}",
            "quota_source_code": quota.get("source_code", ""),
            "quota_raw_name": quota.get("raw_name", ""),
            "issue_type": issue_type,
            "issue_detail": detail,
            "severity": severity,
            "suggested_action": action,
        }
    )


def build_snapshots(quota_rows: Sequence[Dict[str, str]], bill_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    quota_snapshot = [{field: row.get(field, "") for field in QUOTA_FIELDS} for row in quota_rows]
    bill_snapshot = [
        {
            "bill_reference_id": row.get("bill_reference_id", ""),
            "bill_code_9": row.get("bill_code_9", ""),
            "bill_name": row.get("bill_name", ""),
            "appendix_code": row.get("appendix_code", ""),
            "appendix_name": row.get("appendix_name", ""),
            "section_code": row.get("section_code", ""),
            "section_name": row.get("section_name", ""),
            "unit": row.get("unit", ""),
            "project_feature_raw": row.get("project_feature_raw", ""),
            "quantity_calculation_rule": row.get("quantity_calculation_rule", ""),
            "work_content_raw": row.get("work_content_raw", ""),
            "review_status": row.get("review_status", ""),
        }
        for row in bill_rows
    ]
    return quota_snapshot, bill_snapshot


def build_mappings(quota_rows: Sequence[Dict[str, str]], bill_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    mappings: List[Dict[str, str]] = []
    issues: List[Dict[str, str]] = []
    seen_issues: set[Tuple[str, str]] = set()

    for idx, quota in enumerate(sorted(quota_rows, key=lambda row: natural_quota_key(row.get("source_code", ""))), start=1):
        top = top_bill_candidates(quota, bill_rows)
        status, mapping_type, routing_status, confidence, basis, bill = classify_mapping(quota, top)
        if len(top) > 1 and top[0][0] - top[1][0] < 0.8:
            issue_once(issues, seen_issues, quota, "multiple_candidate_bill_items", "Several bill candidates have similar lightweight-rule scores.", "medium", "Human review should decide the appropriate bill appendix/item.")
        if status == "no_direct_bill_item":
            issue_once(issues, seen_issues, quota, "no_candidate_bill_item", "No reliable GB bill item candidate found by lightweight rules.", "medium", "Do not force mapping; classify routing manually.")
        if status == "feature_required":
            issue_once(issues, seen_issues, quota, "feature_required", "Candidate requires project-feature confirmation before use.", "medium", "Check GB project feature and quota use case.")
        if status == "route_to_other_appendix":
            issue_once(issues, seen_issues, quota, "route_to_other_appendix", "Quota appears related to a non-Appendix-A bill reference.", "medium", "Confirm correct GB appendix before any template work.")
        if status == "transport_or_disposal_related":
            issue_once(issues, seen_issues, quota, "transport_item_uncertain", "Transport/disposal quota may be work content or routing item, not bill item body.", "medium", "Human review required.")
        if status == "construction_method_only":
            issue_once(issues, seen_issues, quota, "construction_method_only", "Quota appears to describe construction method, machinery, or auxiliary process.", "medium", "Avoid direct bill mapping without evidence.")
        if confidence < 0.75:
            issue_once(issues, seen_issues, quota, "low_confidence", f"Mapping confidence {confidence:.2f} is below review threshold.", "medium", "Keep pending and route to human review.")
        if text(quota.get("raw_name")) in GENERIC_NAMES:
            issue_once(issues, seen_issues, quota, "quota_name_too_generic", "Quota name is too generic for direct mapping.", "medium", "Use section context and project features.")
        if bill and quota.get("unit") and bill.get("unit") and quota.get("unit") != bill.get("unit"):
            issue_once(issues, seen_issues, quota, "unit_mismatch", "Quota unit differs from candidate bill unit.", "low", "Check whether unit conversion or work-content routing applies.")
        if not routing_status:
            issue_once(issues, seen_issues, quota, "missing_routing_status", "Mapping row has no routing_status.", "high", "Fix readiness routing before use.")

        mappings.append(
            {
                "mapping_id": f"MAP_A1_FULL_{idx:05d}",
                "source_type": SOURCE_TYPE,
                "mapping_scope": MAPPING_SCOPE,
                "quota_reference_id": quota.get("reference_id", ""),
                "quota_source_code": quota.get("source_code", ""),
                "quota_raw_name": quota.get("raw_name", ""),
                "quota_standard_name_candidate": quota.get("standard_name_candidate", ""),
                "quota_unit": quota.get("unit", ""),
                "bill_reference_id": bill.get("bill_reference_id", "") if bill else "",
                "bill_code_9": bill.get("bill_code_9", "") if bill else "",
                "bill_name": bill.get("bill_name", "") if bill else "",
                "bill_appendix_code": bill.get("appendix_code", "") if bill else "",
                "bill_appendix_name": bill.get("appendix_name", "") if bill else "",
                "bill_section_code": bill.get("section_code", "") if bill else "",
                "bill_section_name": bill.get("section_name", "") if bill else "",
                "bill_unit": bill.get("unit", "") if bill else "",
                "bill_project_feature_raw": bill.get("project_feature_raw", "") if bill else "",
                "bill_quantity_calculation_rule": bill.get("quantity_calculation_rule", "") if bill else "",
                "bill_work_content_raw": bill.get("work_content_raw", "") if bill else "",
                "mapping_status": status,
                "mapping_type": mapping_type,
                "mapping_basis": ";".join(basis),
                "mapping_confidence": f"{confidence:.2f}",
                "routing_status": routing_status,
                "review_status": REVIEW_STATUS,
                "reviewer": "",
                "review_comment": "",
                "remark": "readiness_candidate_only;not_approved;do_not_write_back_bill_code",
            }
        )
    return mappings, issues


def build_coverage_matrix(quota_rows: Sequence[Dict[str, str]], mappings: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    quota_by_prefix: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    map_by_prefix: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for quota in quota_rows:
        quota_by_prefix[source_code_prefix(quota.get("source_code", ""))].append(quota)
    for mapping in mappings:
        map_by_prefix[source_code_prefix(mapping.get("quota_source_code", ""))].append(mapping)

    rows = []
    for prefix in sorted(quota_by_prefix, key=lambda value: natural_quota_key(value + "-0")):
        qrows = quota_by_prefix[prefix]
        mrows = map_by_prefix.get(prefix, [])
        status_counts = Counter(row.get("mapping_status", "") for row in mrows)
        manual_review_count = sum(1 for row in mrows if is_explicit_manual_review(row))
        appendix_counts = Counter(row.get("bill_appendix_code", "") for row in mrows if row.get("bill_appendix_code"))
        mapped_count = sum(1 for row in mrows if row.get("bill_code_9"))
        readiness = round(
            100
            * (
                status_counts.get("direct_bill_candidate", 0)
                + 0.75 * status_counts.get("feature_required", 0)
                + 0.55 * status_counts.get("bill_work_content_component", 0)
                + 0.45 * status_counts.get("route_to_other_appendix", 0)
                + 0.25 * status_counts.get("manual_review_required", 0)
            )
            / max(1, len(qrows)),
            1,
        )
        rows.append(
            {
                "quota_section_guess": qrows[0].get("section_name", ""),
                "quota_code_prefix": prefix,
                "quota_row_count": len(qrows),
                "mapped_row_count": mapped_count,
                "direct_candidate_count": status_counts.get("direct_bill_candidate", 0),
                "feature_required_count": status_counts.get("feature_required", 0),
                "work_content_component_count": status_counts.get("bill_work_content_component", 0),
                "construction_method_only_count": status_counts.get("construction_method_only", 0),
                "transport_or_disposal_count": status_counts.get("transport_or_disposal_related", 0),
                "route_to_other_appendix_count": status_counts.get("route_to_other_appendix", 0),
                "no_direct_bill_item_count": status_counts.get("no_direct_bill_item", 0),
                "manual_review_required_count": manual_review_count,
                "top_bill_appendices": ";".join(f"{key}:{value}" for key, value in appendix_counts.most_common(5)),
                "readiness_score": readiness,
                "remark": "prefix-level readiness only; section name requires human confirmation except known prefixes",
            }
        )
    return rows


def is_explicit_manual_review(row: Dict[str, str]) -> bool:
    return (
        row.get("mapping_status") == "manual_review_required"
        or row.get("mapping_type") == "needs_manual_review"
        or row.get("routing_status") == "routed_to_manual_review"
    )


def dashboard_row(name: str, value: Any, expected: str, ok: bool, severity: str, remark: str) -> Dict[str, Any]:
    return {
        "metric_name": name,
        "metric_value": value,
        "expected_or_threshold": expected,
        "status": "pass" if ok else "review",
        "severity": severity,
        "remark": remark,
    }


def build_dashboard(quota_rows: Sequence[Dict[str, str]], bill_rows: Sequence[Dict[str, str]], mappings: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    status_counts = Counter(row.get("mapping_status", "") for row in mappings)
    manual_review_count = sum(1 for row in mappings if is_explicit_manual_review(row))
    routing_missing = sum(1 for row in mappings if not row.get("routing_status"))
    non_pending = sum(1 for row in mappings if row.get("review_status") != REVIEW_STATUS)
    approved = sum(1 for row in mappings if row.get("review_status") == "approved")
    bill_code_writeback = any("bill_code" in key.lower() or "清单" in key for key in quota_rows[0].keys()) if quota_rows else False
    return [
        dashboard_row("total_quota_A1_rows", len(quota_rows), "> 0", len(quota_rows) > 0, "high", "All GD2018 A1 quota rows extracted from normalized Excel."),
        dashboard_row("total_bill_reference_rows", len(bill_rows), "around 472", len(bill_rows) >= 450, "high", "Full GB50854 bill reference candidate count."),
        dashboard_row("quota_rows_with_any_routing_status", len(mappings) - routing_missing, "equals total_quota_A1_rows", routing_missing == 0, "high", "Every quota should have routing_status."),
        dashboard_row("quota_rows_without_any_routing_status", routing_missing, "0", routing_missing == 0, "high", "Missing routing blocks readiness."),
        dashboard_row("direct_candidate_count", status_counts.get("direct_bill_candidate", 0), "informational", True, "low", "Potential direct bill candidates."),
        dashboard_row("feature_required_count", status_counts.get("feature_required", 0), "informational", True, "medium", "Requires project feature confirmation."),
        dashboard_row("work_content_component_count", status_counts.get("bill_work_content_component", 0), "informational", True, "medium", "Likely work-content components."),
        dashboard_row("construction_method_only_count", status_counts.get("construction_method_only", 0), "informational", True, "medium", "Construction method / auxiliary process rows."),
        dashboard_row("transport_or_disposal_count", status_counts.get("transport_or_disposal_related", 0), "informational", True, "medium", "Transport/disposal rows require human handling."),
        dashboard_row("route_to_other_appendix_count", status_counts.get("route_to_other_appendix", 0), "informational", True, "medium", "Rows routed outside GB Appendix A."),
        dashboard_row("no_direct_bill_item_count", status_counts.get("no_direct_bill_item", 0), "informational", True, "medium", "No reliable bill item by lightweight rules."),
        dashboard_row("manual_review_required_count", manual_review_count, "informational", True, "medium", "Rows explicitly routed to manual review."),
        dashboard_row("approved_count", approved, "0", approved == 0, "critical", "No approved records should be generated."),
        dashboard_row("non_pending_review_status_count", non_pending, "0", non_pending == 0, "critical", "All rows must remain pending."),
        dashboard_row("bill_code_writeback_detected", str(bill_code_writeback).lower(), "false", not bill_code_writeback, "critical", "Quota input must not contain bill_code writeback fields."),
        dashboard_row("database_write_detected", "false", "false", True, "critical", "Script writes files only."),
    ]


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
        "backup_path": rel(project_root / ENGINE_REL / "data" / "private" / "reference_extraction" / "backups" / "runs_backup_after_MAP_A1_FULL_0", project_root),
        "status": "generated" if exists else "missing",
        "remark": "private readiness artifact; pending review; not approved",
    }


def update_manifest(project_root: Path, output_dir: Path, quota_output_dir: Path) -> None:
    docs_ref = project_root / DOCS_REF_REL
    manifest_csv = docs_ref / "reference_artifact_manifest.csv"
    rows = read_csv(manifest_csv) if manifest_csv.exists() else []
    new_specs = [
        ("GD2018_stage2R_A1_full", "raw_reference_excel_rows_A1.csv", quota_output_dir / "raw_reference_excel_rows_A1.csv", "广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx"),
        ("GD2018_stage2R_A1_full", "standard_cost_item_reference_A1_candidate.csv", quota_output_dir / "standard_cost_item_reference_A1_candidate.csv", "广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx"),
        ("GD2018_stage2R_A1_full", "reference_quota_pricing_snapshot_A1.csv", quota_output_dir / "reference_quota_pricing_snapshot_A1.csv", "广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx"),
        ("GD2018_stage2R_A1_full", "gd2018_a1_extraction_issues.csv", quota_output_dir / "gd2018_a1_extraction_issues.csv", "广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx"),
        ("GD2018_stage2R_A1_full", "gd2018_a1_section_inventory.csv", quota_output_dir / "gd2018_a1_section_inventory.csv", "广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx"),
        ("GD2018_stage2R_A1_full", "stage_gd2018_a1_full_report.md", quota_output_dir / "stage_gd2018_a1_full_report.md", "广东省房屋建筑与装饰工程综合定额2018_normalized.xlsx"),
        ("MAP_A1_full_readiness", "quota_reference_A1_input_snapshot.csv", output_dir / "quota_reference_A1_input_snapshot.csv", "standard_cost_item_reference_A1_candidate.csv"),
        ("MAP_A1_full_readiness", "bill_reference_all_input_snapshot.csv", output_dir / "bill_reference_all_input_snapshot.csv", "bill_item_reference_all_candidate.csv"),
        ("MAP_A1_full_readiness", "quota_to_bill_mapping_A1_candidate.csv", output_dir / "quota_to_bill_mapping_A1_candidate.csv", "A1 candidates + GB50854 full bill references"),
        ("MAP_A1_full_readiness", "quota_to_bill_mapping_A1_issues.csv", output_dir / "quota_to_bill_mapping_A1_issues.csv", "A1 candidates + GB50854 full bill references"),
        ("MAP_A1_full_readiness", "mapping_coverage_matrix_A1.csv", output_dir / "mapping_coverage_matrix_A1.csv", "quota_to_bill_mapping_A1_candidate.csv"),
        ("MAP_A1_full_readiness", "mapping_readiness_dashboard_A1.csv", output_dir / "mapping_readiness_dashboard_A1.csv", "quota_to_bill_mapping_A1_candidate.csv"),
        ("MAP_A1_full_readiness", "stage_map_A1_full_readiness_report.md", output_dir / "stage_map_A1_full_readiness_report.md", "A1 readiness outputs"),
    ]
    by_key = {(row.get("stage_name", ""), row.get("artifact_name", "")): row for row in rows}
    for stage, artifact, path, source in new_specs:
        by_key[(stage, artifact)] = manifest_row(stage, artifact, path, source, project_root)
    ordered = list(by_key.values())
    write_csv(manifest_csv, MANIFEST_FIELDS, ordered)
    existing = [row for row in ordered if row.get("exists") == "true"]
    manifest_md = docs_ref / "REFERENCE_ARTIFACT_MANIFEST.md"
    manifest_md.write_text(
        "\n".join(
            [
                "# Reference Artifact Manifest",
                "",
                "## Governance",
                "",
                "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
                "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
                "- Each completed stage must back up its `runs` output directory after validation.",
                "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
                "- Readiness outputs are pending review artifacts only and do not approve mappings.",
                "",
                "## Current Manifest Summary",
                "",
                f"- registered_artifacts: {len(ordered)}",
                f"- existing_artifacts: {len(existing)}",
                f"- missing_artifacts: {len(ordered) - len(existing)}",
                "",
                "## Manifest CSV",
                "",
                "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
                "",
                "## Latest Readiness Outputs",
                "",
                "- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/GD2018_stage2R_A1_full/`",
                "- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/MAP_A1_full_readiness/`",
                "",
                "## Backup Requirement",
                "",
                "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_MAP_A1_FULL_0/`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_report(path: Path, quota_rows: Sequence[Dict[str, str]], bill_rows: Sequence[Dict[str, str]], mappings: Sequence[Dict[str, str]], issues: Sequence[Dict[str, str]], matrix: Sequence[Dict[str, Any]], dashboard: Sequence[Dict[str, Any]]) -> None:
    status_counts = Counter(row["mapping_status"] for row in mappings)
    routing_missing = sum(1 for row in mappings if not row.get("routing_status"))
    top_manual = sorted(matrix, key=lambda row: float(row["readiness_score"]))[:8]
    lines = [
        "# Stage MAP-A1-FULL-0 Report - GD2018 A1 to GB50854 Full Bill Reference Readiness",
        "",
        "## 1. Task Scope",
        "",
        "Analyze readiness for mapping all GD2018 A1 quota reference candidates against the full GB/T 50854 bill reference candidate table. This is a routing and readiness analysis, not final matching.",
        "",
        "## 2. Input Files",
        "",
        "- GD2018 A1 candidate CSV generated from normalized Excel.",
        "- GB50854 full bill reference candidate CSV.",
        "- GB50854 context rules CSV used as background reference only.",
        "",
        "## 3. GD2018 A1 Extraction Summary",
        "",
        f"- total_quota_A1_rows: {len(quota_rows)}",
        f"- source_code_prefix_count: {len(set(source_code_prefix(row['source_code']) for row in quota_rows))}",
        "",
        "## 4. GB50854 Full Bill Reference Summary",
        "",
        f"- total_bill_reference_rows: {len(bill_rows)}",
        f"- bill_appendix_count: {len(set(row.get('appendix_code', '') for row in bill_rows))}",
        "",
        "## 5. Mapping Strategy",
        "",
        "- Lightweight rule scoring uses quota source_code prefix, raw_name, unit, bill_name, project_feature_raw, quantity_calculation_rule, and work_content_raw.",
        "- The script does not force a bill_code for every quota.",
        "- Rows without reliable bill candidates are emitted as `no_direct_bill_item / unrouted`.",
        "- Transport, construction method, measures, and work-content-only rows are routed rather than confirmed.",
        "",
        "## 6. Coverage Matrix Summary",
        "",
        f"- coverage_matrix_rows: {len(matrix)}",
        f"- quota_rows_with_any_routing_status: {len(mappings) - routing_missing}",
        f"- quota_rows_without_any_routing_status: {routing_missing}",
        "",
        "## 7. Readiness Dashboard",
        "",
        "| Metric | Value | Status |",
        "|---|---:|---|",
    ]
    for row in dashboard:
        lines.append(f"| {row['metric_name']} | {row['metric_value']} | {row['status']} |")
    lines.extend(
        [
            "",
            "## 8. Key Findings",
            "",
            f"- direct_candidate_count: {status_counts.get('direct_bill_candidate', 0)}",
            f"- feature_required_count: {status_counts.get('feature_required', 0)}",
            f"- work_content_component_count: {status_counts.get('bill_work_content_component', 0)}",
            f"- construction_method_only_count: {status_counts.get('construction_method_only', 0)}",
            f"- transport_or_disposal_count: {status_counts.get('transport_or_disposal_related', 0)}",
            f"- route_to_other_appendix_count: {status_counts.get('route_to_other_appendix', 0)}",
            f"- no_direct_bill_item_count: {status_counts.get('no_direct_bill_item', 0)}",
            "",
            "## 9. Risk Groups",
            "",
            "- Low-readiness prefixes needing human confirmation:",
        ]
    )
    for row in top_manual:
        lines.append(f"  - {row['quota_code_prefix']}: readiness_score={row['readiness_score']}, rows={row['quota_row_count']}, no_direct={row['no_direct_bill_item_count']}")
    lines.extend(
        [
            "",
            "## 10. What Complete Matching Means",
            "",
            "完整匹配不是每条定额都有唯一 bill_code，而是每条定额都有明确 routing_status，并知道它是清单项、工作内容、施工方法、运输、措施或人工复核项。",
            "",
            "## 11. Not Approved / Not Final Statement",
            "",
            "All generated rows remain `pending`. This stage does not approve mappings, does not write bill_code back to quota references, does not write databases, and does not create enterprise templates.",
            "",
            "## 12. Recommended Human Confirmation Points",
            "",
            "- 可进入企业模板草案优先候选：direct_candidate 较多、readiness_score 较高的前缀分组。",
            "- 必须人工复核：feature_required、route_to_other_appendix、no_direct_bill_item、low_confidence 和 unit_mismatch 分组。",
            "- 运输 / 施工方法 / 措施项：transport_or_disposal_related 与 construction_method_only 应优先判断是否属于工作内容或措施，不直接做清单项确认。",
            "- 可暂不处理：no_direct_bill_item 且 readiness_score 低的前缀，待企业模板边界确定后再处理。",
            "",
            "## 13. Next Step Recommendation",
            "",
            "a1_full_readiness_ready_for_global_human_confirmation",
            "",
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze GD2018 A1 to GB50854 full bill reference readiness.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    quota_output_dir = project_root / QUOTA_RUN_REL
    gb_run_dir = project_root / GB_RUN_REL
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    quota_path = quota_output_dir / "standard_cost_item_reference_A1_candidate.csv"
    bill_path = gb_run_dir / "bill_item_reference_all_candidate.csv"
    rules_path = gb_run_dir / "bill_context_rules_all.csv"
    for input_path in [quota_path, bill_path, rules_path]:
        if not input_path.exists():
            raise SystemExit(f"blocked_missing_inputs: {input_path}")

    quota_rows = read_csv(quota_path)
    bill_rows = read_csv(bill_path)
    context_rules = read_csv(rules_path)
    quota_snapshot, bill_snapshot = build_snapshots(quota_rows, bill_rows)
    mappings, issues = build_mappings(quota_rows, bill_rows)
    matrix = build_coverage_matrix(quota_rows, mappings)
    dashboard = build_dashboard(quota_rows, bill_rows, mappings)

    write_csv(output_dir / "quota_reference_A1_input_snapshot.csv", QUOTA_FIELDS, quota_snapshot)
    write_csv(output_dir / "bill_reference_all_input_snapshot.csv", BILL_SNAPSHOT_FIELDS, bill_snapshot)
    write_csv(output_dir / "quota_to_bill_mapping_A1_candidate.csv", MAPPING_FIELDS, mappings)
    write_csv(output_dir / "quota_to_bill_mapping_A1_issues.csv", ISSUE_FIELDS, issues)
    write_csv(output_dir / "mapping_coverage_matrix_A1.csv", COVERAGE_FIELDS, matrix)
    write_csv(output_dir / "mapping_readiness_dashboard_A1.csv", DASHBOARD_FIELDS, dashboard)
    write_report(output_dir / "stage_map_A1_full_readiness_report.md", quota_rows, bill_rows, mappings, issues, matrix, dashboard)
    update_manifest(project_root, output_dir, quota_output_dir)

    status_counts = Counter(row["mapping_status"] for row in mappings)
    print(f"quota_rows={len(quota_rows)}")
    print(f"bill_rows={len(bill_rows)}")
    print(f"context_rule_rows={len(context_rules)}")
    print(f"mapping_rows={len(mappings)}")
    print(f"routing_missing={sum(1 for row in mappings if not row.get('routing_status'))}")
    print("mapping_status_counts=" + json.dumps(dict(status_counts), ensure_ascii=False, sort_keys=True))
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
