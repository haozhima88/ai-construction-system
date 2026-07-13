from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
SOURCE_BASELINE_REL = RUNS_REL / "SOURCE_BASELINE_LOCK_1"
GD_REVIEW_REL = SOURCE_BASELINE_REL / "GD2018_normalized_full_quota_parse_review"
ENTERPRISE_BASE_REL = RUNS_REL / "ENTERPRISE_PRICE_BASELINE_LOCK_1"
ALIGNMENT_REL = RUNS_REL / "ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1"
OUTPUT_DIR_REL = RUNS_REL / "ENTERPRISE_QUOTA_PRICE_COMPARISON_V0_1"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

GD_QUOTA_REL = GD_REVIEW_REL / "gd2018_normalized_quota_items_full_review.csv"
GD_PRICING_REL = GD_REVIEW_REL / "gd2018_normalized_pricing_fields_full_review.csv"
INTERNAL_PRICE_REL = ENTERPRISE_BASE_REL / "internal_price_item_candidate.csv"
ALIGNMENT_CANDIDATE_REL = ALIGNMENT_REL / "internal_price_to_gd_quota_candidate.csv"
COVERAGE_MATRIX_REL = ALIGNMENT_REL / "gd_quota_price_coverage_matrix_3712.csv"
SUPPLEMENT_REL = ALIGNMENT_REL / "enterprise_supplement_item_candidate.csv"

NODE_EXE_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)
NODE_MODULES_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
)

STAGE_NAME = "ENTERPRISE_QUOTA_PRICE_COMPARISON_V0_1"
REVIEW_STATUS = "pending"

COMPARISON_FIELDS = [
    "quota_source_code",
    "quota_raw_name",
    "quota_name_candidate",
    "quota_feature_text_candidate",
    "quota_unit",
    "source_code_prefix",
    "province_labor_fee",
    "province_material_fee",
    "province_machine_fee",
    "province_management_fee",
    "province_total_fee",
    "province_price_status",
    "enterprise_price_candidate_count",
    "enterprise_price_candidate_ids",
    "enterprise_price_candidate_names",
    "enterprise_labor_fee_candidate",
    "enterprise_material_fee_candidate",
    "enterprise_machine_fee_candidate",
    "enterprise_management_fee_candidate",
    "enterprise_total_fee_candidate",
    "enterprise_price_candidate_status",
    "enterprise_price_lock_status",
    "market_price_candidate_count",
    "market_labor_fee_candidate",
    "market_material_fee_candidate",
    "market_machine_fee_candidate",
    "market_management_fee_candidate",
    "market_total_fee_candidate",
    "market_price_source",
    "market_price_date",
    "market_price_status",
    "ai_recommended_labor_fee",
    "ai_recommended_material_fee",
    "ai_recommended_machine_fee",
    "ai_recommended_management_fee",
    "ai_recommended_total_fee",
    "ai_recommendation_basis",
    "ai_confidence_level",
    "ai_risk_flags",
    "ai_auto_apply_allowed",
    "human_selected_price_source",
    "human_selected_labor_fee",
    "human_selected_material_fee",
    "human_selected_machine_fee",
    "human_selected_management_fee",
    "human_selected_total_fee",
    "human_lock_status",
    "cost_engineer_comment",
]

CANDIDATE_POOL_FIELDS = [
    "quota_source_code",
    "quota_name_candidate",
    "internal_price_id",
    "internal_price_name",
    "internal_unit",
    "internal_labor_fee",
    "internal_material_fee",
    "internal_machine_fee",
    "internal_management_fee",
    "internal_total_fee",
    "match_type",
    "match_confidence",
    "unit_compatibility_status",
    "candidate_rank",
    "candidate_use_scope",
    "lock_status",
    "human_decision",
    "human_comment",
]

MARKET_FIELDS = [
    "market_price_candidate_id",
    "quota_source_code",
    "quota_name_candidate",
    "market_item_name",
    "unit",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "management_fee",
    "total_fee",
    "price_source",
    "source_region",
    "source_date",
    "source_file_or_url",
    "confidence_level",
    "review_status",
    "remark",
]

AI_FIELDS = [
    "quota_source_code",
    "quota_name_candidate",
    "recommended_price_source",
    "recommended_labor_fee",
    "recommended_material_fee",
    "recommended_machine_fee",
    "recommended_management_fee",
    "recommended_total_fee",
    "recommendation_basis",
    "confidence_level",
    "risk_flags",
    "auto_apply_allowed",
    "human_review_required",
]

SUPPLEMENT_PRICE_FIELDS = [
    "enterprise_supplement_code",
    "display_label",
    "raw_name",
    "name_candidate",
    "raw_unit",
    "unit_normalized",
    "enterprise_labor_fee",
    "enterprise_material_fee",
    "enterprise_machine_fee",
    "enterprise_management_fee",
    "enterprise_total_fee",
    "suggested_bill_code_9",
    "suggested_parent_quota_code",
    "supplement_type",
    "ai_recommendation_basis",
    "human_lock_status",
    "review_status",
    "cost_engineer_comment",
]

DASHBOARD_FIELDS = [
    "metric_name",
    "metric_value",
    "expected_or_threshold",
    "status",
    "severity",
    "remark",
]

SUMMARY_FIELDS = ["metric_name", "metric_value", "remark"]

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

OUTPUT_ARTIFACTS = [
    "enterprise_quota_price_comparison_v0_1.csv",
    "enterprise_price_candidate_pool_v0_1.csv",
    "market_price_candidate_placeholder_v0_1.csv",
    "ai_price_recommendation_v0_1.csv",
    "enterprise_supplement_price_comparison_v0_1.csv",
    "price_comparison_quality_dashboard.csv",
    "Enterprise_Quota_Price_Comparison_V0_1_Review.xlsx",
    "stage_enterprise_quota_price_comparison_v0_1_report.md",
]

STRONG_MATCH_TYPES = {"exact_name_unit_candidate", "strong_semantic_candidate"}
WEAK_MATCH_TYPES = {"category_semantic_candidate", "weak_candidate"}
NO_MATCH_TYPES = {"no_match"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate enterprise quota price comparison V0.1 review pack."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--node-exe", type=Path, default=NODE_EXE_DEFAULT)
    parser.add_argument("--node-modules", type=Path, default=NODE_MODULES_DEFAULT)
    return parser.parse_args()


def norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").strip()


def rel(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def csv_row_count(path: Path) -> str:
    if path.suffix.lower() != ".csv" or not path.exists():
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return str(sum(1 for _ in csv.DictReader(fh)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_decimal(value: Any) -> Optional[Decimal]:
    text = norm(value).replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def decimal_text(value: Optional[Decimal]) -> str:
    if value is None:
        return ""
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(quantized.normalize(), "f")


def scale_fee(value: Any, factor: Optional[Decimal]) -> str:
    amount = to_decimal(value)
    if amount is None or factor is None:
        return ""
    return decimal_text(amount * factor)


def parse_confidence(value: Any) -> Decimal:
    parsed = to_decimal(value)
    return parsed if parsed is not None else Decimal("0")


def normalized_unit_text(unit: Any) -> str:
    text = norm(unit)
    replacements = {
        "m³": "m3",
        "M³": "m3",
        "㎥": "m3",
        "立方米": "m3",
        "m²": "m2",
        "M²": "m2",
        "㎡": "m2",
        "平方米": "m2",
        "米": "m",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", "", text).lower()


def unit_multiplier_and_base(unit: Any) -> Tuple[Optional[Decimal], str]:
    text = normalized_unit_text(unit)
    if not text:
        return None, ""
    match = re.match(r"^(\d+(?:\.\d+)?)(.+)$", text)
    if match:
        return Decimal(match.group(1)), match.group(2)
    return Decimal("1"), text


def unit_scale_factor(internal_unit: Any, quota_unit: Any) -> Optional[Decimal]:
    internal_multiplier, internal_base = unit_multiplier_and_base(internal_unit)
    quota_multiplier, quota_base = unit_multiplier_and_base(quota_unit)
    if internal_multiplier is None or quota_multiplier is None:
        return None
    if not internal_base or internal_base != quota_base:
        return None
    if internal_multiplier == 0:
        return None
    return quota_multiplier / internal_multiplier


def fee_from(row: Dict[str, str], *names: str) -> str:
    for name in names:
        value = norm(row.get(name))
        if value:
            return value
    return ""


def province_price_status(pricing: Dict[str, str], quota: Dict[str, str]) -> str:
    values = [
        fee_from(pricing, "raw_labor_fee", "labor_fee", "province_labor_fee"),
        fee_from(pricing, "raw_material_fee", "material_fee", "province_material_fee"),
        fee_from(pricing, "raw_machine_fee", "machine_fee", "province_machine_fee"),
        fee_from(pricing, "raw_management_fee", "management_fee", "province_management_fee"),
        fee_from(pricing, "raw_total_fee", "total_fee", "province_total_fee"),
    ]
    if not any(values):
        values = [
            fee_from(quota, "raw_labor_fee"),
            fee_from(quota, "raw_material_fee"),
            fee_from(quota, "raw_machine_fee"),
            fee_from(quota, "raw_management_fee"),
            fee_from(quota, "raw_total_fee"),
        ]
    if all(values):
        return "component_complete"
    if values[-1]:
        return "total_available_component_partial"
    if any(values):
        return "partial"
    return "missing"


def candidate_sort_key(row: Dict[str, str]) -> Tuple[int, Decimal, str]:
    match_type = norm(row.get("match_type"))
    if match_type in STRONG_MATCH_TYPES:
        tier = 0
    elif match_type == "category_semantic_candidate":
        tier = 1
    elif match_type == "weak_candidate":
        tier = 2
    else:
        tier = 3
    return (tier, -parse_confidence(row.get("match_confidence")), norm(row.get("internal_price_id")))


def candidate_use_scope(row: Dict[str, str]) -> str:
    match_type = norm(row.get("match_type"))
    unit_status = norm(row.get("unit_compatibility_status"))
    if unit_status in {"mismatch", "missing_internal_unit"}:
        return "unit_issue_manual_review_only"
    if match_type in STRONG_MATCH_TYPES and unit_status == "compatible":
        return "candidate_price_reference"
    if match_type == "category_semantic_candidate" and unit_status == "compatible":
        return "category_candidate_manual_review"
    return "manual_review_only"


def is_reliable_enterprise_candidate(row: Dict[str, str], factor: Optional[Decimal]) -> bool:
    match_type = norm(row.get("match_type"))
    unit_status = norm(row.get("unit_compatibility_status"))
    return (
        match_type in STRONG_MATCH_TYPES
        and unit_status == "compatible"
        and factor is not None
        and parse_confidence(row.get("match_confidence")) >= Decimal("0.70")
    )


def join_unique(values: Iterable[Any]) -> str:
    seen = set()
    result = []
    for value in values:
        text = norm(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return ";".join(result)


def build_indexes(
    quotas: Sequence[Dict[str, str]],
    pricing: Sequence[Dict[str, str]],
    internals: Sequence[Dict[str, str]],
    alignments: Sequence[Dict[str, str]],
    coverage: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    quota_by_code = {norm(row.get("source_code")): row for row in quotas if norm(row.get("source_code"))}
    pricing_by_code = {norm(row.get("source_code")): row for row in pricing if norm(row.get("source_code"))}
    internal_by_id = {
        norm(row.get("internal_price_id")): row
        for row in internals
        if norm(row.get("internal_price_id"))
    }
    coverage_by_code = {
        norm(row.get("quota_source_code")): row
        for row in coverage
        if norm(row.get("quota_source_code"))
    }
    alignments_by_quota: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in alignments:
        code = norm(row.get("matched_quota_source_code"))
        match_type = norm(row.get("match_type"))
        if not code or match_type in NO_MATCH_TYPES:
            continue
        alignments_by_quota[code].append(row)
    for rows in alignments_by_quota.values():
        rows.sort(key=candidate_sort_key)
    return {
        "quota_by_code": quota_by_code,
        "pricing_by_code": pricing_by_code,
        "internal_by_id": internal_by_id,
        "coverage_by_code": coverage_by_code,
        "alignments_by_quota": alignments_by_quota,
    }


def build_candidate_pool(
    alignments_by_quota: Dict[str, List[Dict[str, str]]],
    internal_by_id: Dict[str, Dict[str, str]],
    quota_by_code: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for quota_code in sorted(alignments_by_quota):
        quota = quota_by_code.get(quota_code, {})
        for rank, match in enumerate(alignments_by_quota[quota_code], start=1):
            internal = internal_by_id.get(norm(match.get("internal_price_id")), {})
            rows.append(
                {
                    "quota_source_code": quota_code,
                    "quota_name_candidate": norm(
                        quota.get("quota_name_candidate")
                        or match.get("matched_quota_name_candidate")
                    ),
                    "internal_price_id": norm(match.get("internal_price_id")),
                    "internal_price_name": norm(
                        internal.get("name_candidate")
                        or match.get("internal_name_candidate")
                        or match.get("internal_raw_name")
                    ),
                    "internal_unit": norm(
                        internal.get("unit_normalized")
                        or match.get("internal_unit")
                        or internal.get("raw_unit")
                    ),
                    "internal_labor_fee": norm(internal.get("labor_fee")),
                    "internal_material_fee": norm(internal.get("material_fee")),
                    "internal_machine_fee": norm(internal.get("machine_fee")),
                    "internal_management_fee": "",
                    "internal_total_fee": norm(internal.get("total_fee") or match.get("internal_total_fee")),
                    "match_type": norm(match.get("match_type")),
                    "match_confidence": norm(match.get("match_confidence")),
                    "unit_compatibility_status": norm(match.get("unit_compatibility_status")),
                    "candidate_rank": rank,
                    "candidate_use_scope": candidate_use_scope(match),
                    "lock_status": "candidate_only",
                    "human_decision": "",
                    "human_comment": "",
                }
            )
    return rows


def selected_enterprise_candidate(
    quota: Dict[str, str],
    matches: Sequence[Dict[str, str]],
    internal_by_id: Dict[str, Dict[str, str]],
) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]], Optional[Decimal], str]:
    best_any: Optional[Tuple[Dict[str, str], Dict[str, str], Optional[Decimal]]] = None
    for match in matches:
        internal = internal_by_id.get(norm(match.get("internal_price_id")), {})
        internal_unit = internal.get("unit_normalized") or match.get("internal_unit") or internal.get("raw_unit")
        factor = unit_scale_factor(internal_unit, quota.get("unit"))
        if best_any is None:
            best_any = (match, internal, factor)
        if is_reliable_enterprise_candidate(match, factor):
            return match, internal, factor, "high_confidence_scaled_candidate_available"
    if best_any is None:
        return None, None, None, "no_candidate"
    match, internal, factor = best_any
    scale_suffix = "_unit_scaled" if factor is not None else "_unit_scale_pending"
    if norm(match.get("unit_compatibility_status")) in {"mismatch", "missing_internal_unit"}:
        return match, internal, factor, "candidate_available_unit_issue"
    if norm(match.get("match_type")) in WEAK_MATCH_TYPES:
        return match, internal, factor, "candidate_available_manual_review" + scale_suffix
    return match, internal, factor, "candidate_available" + scale_suffix


def enterprise_candidate_scaled_values(
    internal: Optional[Dict[str, str]], factor: Optional[Decimal]
) -> Dict[str, str]:
    if not internal or factor is None:
        return {
            "labor": "",
            "material": "",
            "machine": "",
            "management": "",
            "total": "",
        }
    return {
        "labor": scale_fee(internal.get("labor_fee"), factor),
        "material": scale_fee(internal.get("material_fee"), factor),
        "machine": scale_fee(internal.get("machine_fee"), factor),
        "management": "",
        "total": scale_fee(internal.get("total_fee"), factor),
    }


def price_variance_risk(enterprise_total: str, province_total: str) -> str:
    ent = to_decimal(enterprise_total)
    prov = to_decimal(province_total)
    if ent is None or prov is None or prov == 0:
        return ""
    ratio = ent / prov
    if ratio < Decimal("0.50") or ratio > Decimal("1.50"):
        return "enterprise_vs_province_large_variance"
    return ""


def build_market_rows(quotas: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows = []
    for idx, quota in enumerate(quotas, start=1):
        rows.append(
            {
                "market_price_candidate_id": f"MKT-PH-{idx:06d}",
                "quota_source_code": norm(quota.get("source_code")),
                "quota_name_candidate": norm(quota.get("quota_name_candidate")),
                "market_item_name": "",
                "unit": norm(quota.get("unit")),
                "labor_fee": "",
                "material_fee": "",
                "machine_fee": "",
                "management_fee": "",
                "total_fee": "",
                "price_source": "",
                "source_region": "",
                "source_date": "",
                "source_file_or_url": "",
                "confidence_level": "pending",
                "review_status": REVIEW_STATUS,
                "remark": "placeholder_only;market_price_not_loaded;no_web_fetch",
            }
        )
    return rows


def build_comparison_and_ai(
    quotas: Sequence[Dict[str, str]],
    pricing_by_code: Dict[str, Dict[str, str]],
    coverage_by_code: Dict[str, Dict[str, str]],
    alignments_by_quota: Dict[str, List[Dict[str, str]]],
    internal_by_id: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    comparison_rows: List[Dict[str, Any]] = []
    ai_rows: List[Dict[str, Any]] = []
    for quota in quotas:
        quota_code = norm(quota.get("source_code"))
        pricing = pricing_by_code.get(quota_code, {})
        coverage = coverage_by_code.get(quota_code, {})
        matches = alignments_by_quota.get(quota_code, [])
        selected_match, selected_internal, factor, candidate_status = selected_enterprise_candidate(
            quota, matches, internal_by_id
        )
        scaled = enterprise_candidate_scaled_values(selected_internal, factor)
        province_values = {
            "labor": fee_from(pricing, "raw_labor_fee") or norm(quota.get("raw_labor_fee")),
            "material": fee_from(pricing, "raw_material_fee") or norm(quota.get("raw_material_fee")),
            "machine": fee_from(pricing, "raw_machine_fee") or norm(quota.get("raw_machine_fee")),
            "management": fee_from(pricing, "raw_management_fee") or norm(quota.get("raw_management_fee")),
            "total": fee_from(pricing, "raw_total_fee") or norm(quota.get("raw_total_fee")),
        }
        candidate_ids = join_unique(match.get("internal_price_id") for match in matches)
        candidate_names = join_unique(
            internal_by_id.get(norm(match.get("internal_price_id")), {}).get("name_candidate")
            or match.get("internal_name_candidate")
            or match.get("internal_raw_name")
            for match in matches
        )

        risk_flags: List[str] = []
        if selected_match:
            unit_status = norm(selected_match.get("unit_compatibility_status"))
            if unit_status and unit_status != "compatible":
                risk_flags.append(unit_status)
            if factor is None and unit_status == "compatible":
                risk_flags.append("unit_scale_factor_unparsed")
            if selected_internal and not norm(selected_internal.get("total_fee")):
                risk_flags.append("internal_total_fee_missing")
            if selected_internal:
                risk_flags.append("internal_management_fee_missing")
            if norm(selected_match.get("match_type")) in WEAK_MATCH_TYPES:
                risk_flags.append("weak_or_category_candidate")
        else:
            risk_flags.append("no_enterprise_candidate")
        variance_flag = price_variance_risk(scaled["total"], province_values["total"])
        if variance_flag:
            risk_flags.append(variance_flag)
        if province_price_status(pricing, quota) != "component_complete":
            risk_flags.append("province_component_partial")

        reliable = bool(
            selected_match
            and selected_internal
            and is_reliable_enterprise_candidate(selected_match, factor)
        )
        if reliable:
            recommended_source = "enterprise_internal_price_candidate"
            recommended_values = scaled
            match_id = norm(selected_match.get("internal_price_id"))
            basis_parts = [
                f"high_confidence_internal_candidate:{match_id}",
                f"match_type:{norm(selected_match.get('match_type'))}",
                f"confidence:{norm(selected_match.get('match_confidence'))}",
            ]
            if factor is not None:
                basis_parts.append(f"unit_scaled_factor:{decimal_text(factor)}")
            confidence_level = "high" if parse_confidence(selected_match.get("match_confidence")) >= Decimal("0.90") else "medium"
        else:
            recommended_source = "province_quota_fallback"
            recommended_values = province_values
            basis_parts = [
                "enterprise_candidate_not_reliable_or_unit_pending",
                "market_price_not_loaded",
                "province_quota_preserved_as_review_fallback",
            ]
            if selected_match is not None and factor is not None:
                basis_parts.append(f"top_enterprise_candidate_unit_scaled_factor:{decimal_text(factor)}")
            confidence_level = "medium" if province_values["total"] else "low"

        risk_text = join_unique(risk_flags)
        ai_row = {
            "quota_source_code": quota_code,
            "quota_name_candidate": norm(quota.get("quota_name_candidate")),
            "recommended_price_source": recommended_source,
            "recommended_labor_fee": recommended_values["labor"],
            "recommended_material_fee": recommended_values["material"],
            "recommended_machine_fee": recommended_values["machine"],
            "recommended_management_fee": recommended_values["management"],
            "recommended_total_fee": recommended_values["total"],
            "recommendation_basis": ";".join(basis_parts),
            "confidence_level": confidence_level,
            "risk_flags": risk_text,
            "auto_apply_allowed": "false",
            "human_review_required": "true",
        }
        ai_rows.append(ai_row)

        comparison_rows.append(
            {
                "quota_source_code": quota_code,
                "quota_raw_name": norm(quota.get("raw_name")),
                "quota_name_candidate": norm(quota.get("quota_name_candidate")),
                "quota_feature_text_candidate": norm(quota.get("quota_feature_text_candidate")),
                "quota_unit": norm(quota.get("unit")),
                "source_code_prefix": norm(quota.get("code_prefix") or coverage.get("source_code_prefix")),
                "province_labor_fee": province_values["labor"],
                "province_material_fee": province_values["material"],
                "province_machine_fee": province_values["machine"],
                "province_management_fee": province_values["management"],
                "province_total_fee": province_values["total"],
                "province_price_status": province_price_status(pricing, quota),
                "enterprise_price_candidate_count": str(len(matches)),
                "enterprise_price_candidate_ids": candidate_ids,
                "enterprise_price_candidate_names": candidate_names,
                "enterprise_labor_fee_candidate": scaled["labor"],
                "enterprise_material_fee_candidate": scaled["material"],
                "enterprise_machine_fee_candidate": scaled["machine"],
                "enterprise_management_fee_candidate": scaled["management"],
                "enterprise_total_fee_candidate": scaled["total"],
                "enterprise_price_candidate_status": candidate_status,
                "enterprise_price_lock_status": "candidate_only",
                "market_price_candidate_count": "0",
                "market_labor_fee_candidate": "",
                "market_material_fee_candidate": "",
                "market_machine_fee_candidate": "",
                "market_management_fee_candidate": "",
                "market_total_fee_candidate": "",
                "market_price_source": "",
                "market_price_date": "",
                "market_price_status": "pending_market_price_not_loaded",
                "ai_recommended_labor_fee": ai_row["recommended_labor_fee"],
                "ai_recommended_material_fee": ai_row["recommended_material_fee"],
                "ai_recommended_machine_fee": ai_row["recommended_machine_fee"],
                "ai_recommended_management_fee": ai_row["recommended_management_fee"],
                "ai_recommended_total_fee": ai_row["recommended_total_fee"],
                "ai_recommendation_basis": ai_row["recommendation_basis"],
                "ai_confidence_level": ai_row["confidence_level"],
                "ai_risk_flags": ai_row["risk_flags"],
                "ai_auto_apply_allowed": "false",
                "human_selected_price_source": "",
                "human_selected_labor_fee": "",
                "human_selected_material_fee": "",
                "human_selected_machine_fee": "",
                "human_selected_management_fee": "",
                "human_selected_total_fee": "",
                "human_lock_status": REVIEW_STATUS,
                "cost_engineer_comment": "",
            }
        )
    return comparison_rows, ai_rows


def build_supplement_price_rows(supplements: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in supplements:
        rows.append(
            {
                "enterprise_supplement_code": norm(row.get("enterprise_supplement_code")),
                "display_label": norm(row.get("display_label")),
                "raw_name": norm(row.get("raw_name")),
                "name_candidate": norm(row.get("name_candidate")),
                "raw_unit": norm(row.get("raw_unit")),
                "unit_normalized": norm(row.get("unit_normalized")),
                "enterprise_labor_fee": norm(row.get("labor_fee")),
                "enterprise_material_fee": norm(row.get("material_fee")),
                "enterprise_machine_fee": norm(row.get("machine_fee")),
                "enterprise_management_fee": "",
                "enterprise_total_fee": norm(row.get("total_fee")),
                "suggested_bill_code_9": norm(row.get("suggested_bill_code_9")),
                "suggested_parent_quota_code": norm(row.get("suggested_parent_quota_code")),
                "supplement_type": norm(row.get("supplement_type")),
                "ai_recommendation_basis": "enterprise_supplement_candidate_only;not_official_gd_quota;pending_cost_engineer_review",
                "human_lock_status": REVIEW_STATUS,
                "review_status": REVIEW_STATUS,
                "cost_engineer_comment": "",
            }
        )
    return rows


def metric_row(
    name: str,
    value: Any,
    expected: str,
    status: str,
    severity: str,
    remark: str,
) -> Dict[str, Any]:
    return {
        "metric_name": name,
        "metric_value": value,
        "expected_or_threshold": expected,
        "status": status,
        "severity": severity,
        "remark": remark,
    }


def build_dashboard(
    comparison: Sequence[Dict[str, Any]],
    candidate_pool: Sequence[Dict[str, Any]],
    market: Sequence[Dict[str, Any]],
    ai: Sequence[Dict[str, Any]],
    supplements: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    total_rows = len(comparison)
    enterprise_available = sum(
        1 for row in comparison if int(norm(row.get("enterprise_price_candidate_count")) or "0") > 0
    )
    candidate_only_count = sum(
        1 for row in comparison if norm(row.get("enterprise_price_lock_status")) == "candidate_only"
    )
    ai_auto_count = sum(1 for row in ai if norm(row.get("auto_apply_allowed")).lower() == "true")
    human_locked_count = sum(1 for row in comparison if norm(row.get("human_lock_status")) != REVIEW_STATUS)
    approved_count = sum(
        1
        for row in list(market) + list(supplements)
        if norm(row.get("review_status")).lower() == "approved"
    )
    non_pending_review_status_count = sum(
        1
        for row in list(market) + list(supplements)
        if norm(row.get("review_status")) != REVIEW_STATUS
    )
    locked_internal_count = sum(
        1 for row in candidate_pool if norm(row.get("lock_status")).lower() in {"locked", "approved"}
    )
    market_available = sum(
        1
        for row in market
        if any(
            norm(row.get(field))
            for field in ["labor_fee", "material_fee", "machine_fee", "management_fee", "total_fee"]
        )
    )
    province_total_available = sum(1 for row in comparison if norm(row.get("province_total_fee")))
    province_all_components = sum(
        1
        for row in comparison
        if all(
            norm(row.get(field))
            for field in [
                "province_labor_fee",
                "province_material_fee",
                "province_machine_fee",
                "province_management_fee",
                "province_total_fee",
            ]
        )
    )
    rows = [
        metric_row("total_gd_quota_rows", total_rows, "3712", "pass" if total_rows == 3712 else "fail", "critical", "GD2018 normalized full quota baseline rows."),
        metric_row("province_price_complete_rows", province_total_available, "3712 province total fees retained", "pass" if province_total_available == 3712 else "warn", "high", "Province labor/material/machine/management/total columns are present; source component blanks are preserved."),
        metric_row("province_price_all_fee_components_non_empty_rows", province_all_components, "informational", "info", "low", "Rows with all five province fee component values non-empty."),
        metric_row("enterprise_candidate_available_rows", enterprise_available, "informational", "info", "medium", "GD quota rows with one or more internal price candidates."),
        metric_row("enterprise_candidate_missing_rows", total_rows - enterprise_available, "informational", "info", "medium", "GD quota rows without internal price candidate."),
        metric_row("market_candidate_available_rows", market_available, "0", "pass" if market_available == 0 else "fail", "critical", "Market prices are placeholders only; no web fetching performed."),
        metric_row("ai_recommendation_rows", len(ai), "3712", "pass" if len(ai) == 3712 else "fail", "critical", "One non-binding AI suggestion row per GD quota row."),
        metric_row("ai_auto_apply_allowed_count", ai_auto_count, "0", "pass" if ai_auto_count == 0 else "fail", "critical", "AI recommendations must never auto-apply."),
        metric_row("human_locked_count", human_locked_count, "0", "pass" if human_locked_count == 0 else "fail", "critical", "All human lock status values remain pending."),
        metric_row("candidate_only_enterprise_price_count", candidate_only_count, "3712", "pass" if candidate_only_count == 3712 else "fail", "critical", "Enterprise price state stays candidate_only."),
        metric_row("approved_count", approved_count, "0", "pass" if approved_count == 0 else "fail", "critical", "No artifact row may be approved in this stage."),
        metric_row("non_pending_review_status_count", non_pending_review_status_count, "0", "pass" if non_pending_review_status_count == 0 else "fail", "critical", "Review-bearing rows remain pending."),
        metric_row("locked_internal_price_count", locked_internal_count, "0", "pass" if locked_internal_count == 0 else "fail", "critical", "Internal price IDs are not locked."),
        metric_row("database_write_detected", 0, "0", "pass", "critical", "This script writes files only; no database connection is used."),
    ]
    return rows


def build_summary_rows(dashboard: Sequence[Dict[str, Any]], rec: str) -> List[Dict[str, Any]]:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    return [
        {"metric_name": "stage_name", "metric_value": STAGE_NAME, "remark": "Review workbook only."},
        {"metric_name": "recommendation", "metric_value": rec, "remark": "Not final enterprise quota."},
        {"metric_name": "total_gd_quota_rows", "metric_value": metrics.get("total_gd_quota_rows", 0), "remark": "Must equal 3712."},
        {"metric_name": "enterprise_candidate_available_rows", "metric_value": metrics.get("enterprise_candidate_available_rows", 0), "remark": "Candidate only; no internal price lock."},
        {"metric_name": "market_candidate_available_rows", "metric_value": metrics.get("market_candidate_available_rows", 0), "remark": "Must remain 0 in this stage."},
        {"metric_name": "ai_auto_apply_allowed_count", "metric_value": metrics.get("ai_auto_apply_allowed_count", 0), "remark": "Must remain 0."},
        {"metric_name": "approved_count", "metric_value": metrics.get("approved_count", 0), "remark": "Must remain 0."},
    ]


def write_report(
    path: Path,
    dashboard: Sequence[Dict[str, Any]],
    comparison: Sequence[Dict[str, Any]],
    candidate_pool: Sequence[Dict[str, Any]],
    market: Sequence[Dict[str, Any]],
    ai: Sequence[Dict[str, Any]],
    supplements: Sequence[Dict[str, Any]],
    rec: str,
) -> None:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    price_status_counts = Counter(row["province_price_status"] for row in comparison)
    enterprise_status_counts = Counter(row["enterprise_price_candidate_status"] for row in comparison)
    ai_source_counts = Counter(row["recommended_price_source"] for row in ai)
    lines = [
        "# Stage ENTERPRISE-QUOTA-PRICE-COMPARISON-V0.1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Generate a human-reviewable enterprise quota V0.1 price comparison draft from the locked GD2018 3712-row quota baseline, internal price candidates, previous alignment candidates, market placeholders, and non-binding AI recommendation fields.",
        "",
        "## 2. Why Previous Alignment Was Not Enough",
        "",
        "The previous alignment stage identified possible relationships between internal price rows and GD2018 quota rows. It did not produce a review workbook that preserves province fee components, shows one-to-many internal candidates, reserves market price fields, and keeps human lock fields blank/pending.",
        "",
        "## 3. Four Price Dimensions",
        "",
        "- Province quota price: preserved from the normalized GD2018 baseline.",
        "- Enterprise internal price candidate: linked as candidate_only and not locked.",
        "- Market price candidate: placeholder only; no web fetch and no fabricated value.",
        "- AI recommendation: explainable fallback or candidate suggestion with auto_apply_allowed=false.",
        "",
        "## 4. Province Price Completeness",
        "",
        f"- total_gd_quota_rows: {metrics.get('total_gd_quota_rows', 0)}",
        f"- province_price_complete_rows: {metrics.get('province_price_complete_rows', 0)}",
        f"- province_price_all_fee_components_non_empty_rows: {metrics.get('province_price_all_fee_components_non_empty_rows', 0)}",
        f"- province_price_status_counts: {json.dumps(dict(price_status_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 5. Enterprise Price Candidate Pool",
        "",
        f"- enterprise_candidate_available_rows: {metrics.get('enterprise_candidate_available_rows', 0)}",
        f"- enterprise_candidate_missing_rows: {metrics.get('enterprise_candidate_missing_rows', 0)}",
        f"- enterprise_price_candidate_pool_rows: {len(candidate_pool)}",
        f"- enterprise_price_candidate_status_counts: {json.dumps(dict(enterprise_status_counts), ensure_ascii=False, sort_keys=True)}",
        "- All internal price links remain candidate_only; internal_price_id is not locked.",
        "",
        "## 6. Market Price Placeholder",
        "",
        f"- market_placeholder_rows: {len(market)}",
        f"- market_candidate_available_rows: {metrics.get('market_candidate_available_rows', 0)}",
        "- Market fields are intentionally empty/pending because this stage does not fetch or infer market prices.",
        "",
        "## 7. AI Recommendation Logic",
        "",
        "- High-confidence exact/strong enterprise candidates with parseable compatible units are recommended as enterprise_internal_price_candidate.",
        "- Internal unit prices are automatically converted to the GD quota unit base when units are compatible, for example m2 to 100m2 or m3 to 100m3 uses a factor of 100.",
        "- Weak, category-only, incompatible, or unscaled candidates fall back to province_quota_fallback.",
        "- Province vs enterprise large variance, unit issues, missing internal management fee, and partial province components are recorded as risk flags.",
        f"- ai_recommendation_rows: {len(ai)}",
        f"- ai_recommended_price_source_counts: {json.dumps(dict(ai_source_counts), ensure_ascii=False, sort_keys=True)}",
        f"- ai_auto_apply_allowed_count: {metrics.get('ai_auto_apply_allowed_count', 0)}",
        "",
        "## 8. Supplement Item Price Comparison",
        "",
        f"- supplement_price_comparison_rows: {len(supplements)}",
        "- Supplement rows keep ENT-SUP identity and remain pending; they are not official GD quota rows and no fake A1 code is generated.",
        "",
        "## 9. Governance Controls",
        "",
        "- No database write.",
        "- No migration or schema change.",
        "- No internal_price_library generation.",
        "- No cost item write-back.",
        "- No web market price fetch.",
        "- No approved rows and no locked internal price IDs.",
        "",
        "## 10. Not Approved / Not Final Statement",
        "",
        "This package is a review draft only. It is not a formal enterprise quota, not an approved price library, and not a database import source without a later human approval stage.",
        "",
        "## 11. Next Step Recommendation",
        "",
        rec,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def create_xlsx(output_dir: Path, node_exe: Path, node_modules: Path) -> None:
    specs = [
        ["quota_price_comparison_3712", "enterprise_quota_price_comparison_v0_1.csv", len(COMPARISON_FIELDS)],
        ["enterprise_price_candidate_pool", "enterprise_price_candidate_pool_v0_1.csv", len(CANDIDATE_POOL_FIELDS)],
        ["market_price_placeholder", "market_price_candidate_placeholder_v0_1.csv", len(MARKET_FIELDS)],
        ["ai_price_recommendation", "ai_price_recommendation_v0_1.csv", len(AI_FIELDS)],
        ["supplement_price_comparison", "enterprise_supplement_price_comparison_v0_1.csv", len(SUPPLEMENT_PRICE_FIELDS)],
        ["quality_dashboard", "price_comparison_quality_dashboard.csv", len(DASHBOARD_FIELDS)],
        ["summary", "summary_for_xlsx.csv", len(SUMMARY_FIELDS)],
    ]
    builder = r'''
import fs from "fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = process.argv[2];
const specs = JSON.parse(process.argv[3]);
let workbook = null;
for (const spec of specs) {
  const [sheetName, fileName, colCount] = spec;
  const csvText = await fs.readFile(`${outputDir}/${fileName}`, "utf8");
  if (!workbook) {
    workbook = await Workbook.fromCSV(csvText, { sheetName });
  } else {
    await workbook.fromCSV(csvText, { sheetName });
  }
  const effectiveSheetName = sheetName.slice(0, 31);
  const sheet = workbook.worksheets.getItem(effectiveSheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format = { fill: "#1F4E79", font: { bold: true, color: "#FFFFFF" }, wrapText: true };
  header.format.borders = { preset: "bottom", style: "thin", color: "#9FBAD0" };
  const used = sheet.getUsedRange();
  used.format = { wrapText: true, verticalAlignment: "top" };
  used.format.font = { name: "Aptos", size: 10 };
  sheet.getRangeByIndexes(0, 0, 1, colCount).format.columnWidth =
    sheetName === "summary" || sheetName === "quality_dashboard" ? 26 : 18;
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
await workbook.render({ sheetName: "summary", autoCrop: "all", scale: 1, format: "png" });
await workbook.render({ sheetName: "quality_dashboard", autoCrop: "all", scale: 1, format: "png" });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/Enterprise_Quota_Price_Comparison_V0_1_Review.xlsx`);
console.log(`xlsx=${outputDir}/Enterprise_Quota_Price_Comparison_V0_1_Review.xlsx`);
'''
    with tempfile.TemporaryDirectory(prefix="enterprise_quota_price_xlsx_") as tmp:
        tmp_path = Path(tmp)
        link = tmp_path / "node_modules"
        try:
            os.symlink(node_modules, link, target_is_directory=True)
        except OSError:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(node_modules)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        builder_path = tmp_path / "build_enterprise_quota_price_review.mjs"
        builder_path.write_text(builder, encoding="utf-8")
        subprocess.run(
            [str(node_exe), str(builder_path), str(output_dir), json.dumps(specs)],
            cwd=tmp_path,
            check=True,
        )
    sidecar = output_dir / "Enterprise_Quota_Price_Comparison_V0_1_Review.xlsx.inspect.ndjson"
    if sidecar.exists():
        sidecar.unlink()


def artifact_manifest_row(
    project_root: Path,
    output_dir: Path,
    artifact_name: str,
    row_count_override: str = "",
) -> Dict[str, Any]:
    path = output_dir / artifact_name
    exists = path.exists()
    source_files = [
        rel(project_root / GD_QUOTA_REL, project_root),
        rel(project_root / GD_PRICING_REL, project_root),
        rel(project_root / INTERNAL_PRICE_REL, project_root),
        rel(project_root / ALIGNMENT_CANDIDATE_REL, project_root),
        rel(project_root / COVERAGE_MATRIX_REL, project_root),
        rel(project_root / SUPPLEMENT_REL, project_root),
    ]
    return {
        "stage_name": STAGE_NAME,
        "artifact_name": artifact_name,
        "expected_path": rel(path, project_root),
        "exists": str(exists).lower(),
        "file_size_bytes": path.stat().st_size if exists else 0,
        "row_count": row_count_override if row_count_override else csv_row_count(path),
        "sha256": sha256_file(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": ";".join(source_files),
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": "construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_ENTERPRISE_QUOTA_PRICE_COMPARISON_V0_1",
        "status": "generated_pending_review" if exists else "missing",
        "remark": "private artifact; not tracked by Git; no database write; no approved; no internal price lock",
    }


def update_manifest(
    project_root: Path,
    output_dir: Path,
    workbook_total_rows: int,
) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    existing = read_csv(manifest_path)
    kept = [row for row in existing if norm(row.get("stage_name")) != STAGE_NAME]
    new_rows = []
    for name in OUTPUT_ARTIFACTS:
        row_override = str(workbook_total_rows) if name.endswith(".xlsx") else ""
        new_rows.append(artifact_manifest_row(project_root, output_dir, name, row_override))
    write_csv(manifest_path, MANIFEST_FIELDS, kept + new_rows)
    write_manifest_md(project_root, kept + new_rows, new_rows)


def write_manifest_md(
    project_root: Path,
    all_rows: Sequence[Dict[str, Any]],
    latest: Sequence[Dict[str, Any]],
) -> None:
    registered = len(all_rows)
    existing_count = sum(1 for row in all_rows if norm(row.get("exists")).lower() == "true")
    lines = [
        "# Reference Artifact Manifest",
        "",
        "## Governance",
        "",
        "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
        "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
        "- Each completed stage must back up its `runs` output directory after validation.",
        "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
        "- Enterprise price comparison outputs are pending review artifacts only and do not approve prices.",
        "- Internal price IDs remain candidate references only until a later human lock stage.",
        "- Market price placeholders must not be treated as fetched or verified market prices.",
        "",
        "## Current Manifest Summary",
        "",
        f"- registered_artifacts: {registered}",
        f"- existing_artifacts: {existing_count}",
        f"- missing_artifacts: {registered - existing_count}",
        "",
        "## Manifest CSV",
        "",
        "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
        "",
        "## Latest Enterprise Quota Price Comparison V0.1 Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_ENTERPRISE_QUOTA_PRICE_COMPARISON_V0_1/`",
            "",
        ]
    )
    (project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def validate_input_files(project_root: Path) -> List[str]:
    required = [
        GD_QUOTA_REL,
        GD_PRICING_REL,
        INTERNAL_PRICE_REL,
        ALIGNMENT_CANDIDATE_REL,
        COVERAGE_MATRIX_REL,
        SUPPLEMENT_REL,
    ]
    return [rel(project_root / path, project_root) for path in required if not (project_root / path).exists()]


def recommendation_from_dashboard(dashboard: Sequence[Dict[str, Any]], xlsx_ok: bool) -> str:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    if not xlsx_ok:
        return "blocked_xlsx_generation_failed"
    hard_fail = [
        str(metrics.get("total_gd_quota_rows")) != "3712",
        str(metrics.get("ai_recommendation_rows")) != "3712",
        str(metrics.get("ai_auto_apply_allowed_count")) != "0",
        str(metrics.get("human_locked_count")) != "0",
        str(metrics.get("candidate_only_enterprise_price_count")) != "3712",
        str(metrics.get("approved_count")) != "0",
        str(metrics.get("locked_internal_price_count")) != "0",
        str(metrics.get("database_write_detected")) != "0",
    ]
    if any(hard_fail):
        return "price_comparison_partial_manual_intervention_required"
    return "price_comparison_ready_for_cost_engineer_review"


def write_blocked_report(project_root: Path, missing: Sequence[str]) -> None:
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage ENTERPRISE-QUOTA-PRICE-COMPARISON-V0.1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Generate enterprise quota price comparison review artifacts.",
        "",
        "## 2. Why Previous Alignment Was Not Enough",
        "",
        "Skipped because required inputs are missing.",
        "",
        "## 3. Four Price Dimensions",
        "",
        "Skipped.",
        "",
        "## 4. Province Price Completeness",
        "",
        "Skipped.",
        "",
        "## 5. Enterprise Price Candidate Pool",
        "",
        "Skipped.",
        "",
        "## 6. Market Price Placeholder",
        "",
        "Skipped.",
        "",
        "## 7. AI Recommendation Logic",
        "",
        "Skipped.",
        "",
        "## 8. Supplement Item Price Comparison",
        "",
        "Skipped.",
        "",
        "## 9. Governance Controls",
        "",
        "No database write performed.",
        "",
        "## 10. Not Approved / Not Final Statement",
        "",
        "No approved output generated.",
        "",
        "## 11. Next Step Recommendation",
        "",
        "blocked_missing_inputs",
        "",
        "Missing inputs:",
    ]
    lines.extend(f"- `{path}`" for path in missing)
    (output_dir / "stage_enterprise_quota_price_comparison_v0_1_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = validate_input_files(project_root)
    if missing:
        write_blocked_report(project_root, missing)
        print("recommendation=blocked_missing_inputs")
        for path in missing:
            print(f"missing_input={path}")
        return 2

    quotas = read_csv(project_root / GD_QUOTA_REL)
    pricing = read_csv(project_root / GD_PRICING_REL)
    internals = read_csv(project_root / INTERNAL_PRICE_REL)
    alignments = read_csv(project_root / ALIGNMENT_CANDIDATE_REL)
    coverage = read_csv(project_root / COVERAGE_MATRIX_REL)
    supplements_input = read_csv(project_root / SUPPLEMENT_REL)

    indexes = build_indexes(quotas, pricing, internals, alignments, coverage)
    candidate_pool = build_candidate_pool(
        indexes["alignments_by_quota"],
        indexes["internal_by_id"],
        indexes["quota_by_code"],
    )
    market_rows = build_market_rows(quotas)
    comparison, ai_rows = build_comparison_and_ai(
        quotas,
        indexes["pricing_by_code"],
        indexes["coverage_by_code"],
        indexes["alignments_by_quota"],
        indexes["internal_by_id"],
    )
    supplement_rows = build_supplement_price_rows(supplements_input)
    dashboard = build_dashboard(comparison, candidate_pool, market_rows, ai_rows, supplement_rows)

    write_csv(output_dir / "enterprise_quota_price_comparison_v0_1.csv", COMPARISON_FIELDS, comparison)
    write_csv(output_dir / "enterprise_price_candidate_pool_v0_1.csv", CANDIDATE_POOL_FIELDS, candidate_pool)
    write_csv(output_dir / "market_price_candidate_placeholder_v0_1.csv", MARKET_FIELDS, market_rows)
    write_csv(output_dir / "ai_price_recommendation_v0_1.csv", AI_FIELDS, ai_rows)
    write_csv(output_dir / "enterprise_supplement_price_comparison_v0_1.csv", SUPPLEMENT_PRICE_FIELDS, supplement_rows)
    write_csv(output_dir / "price_comparison_quality_dashboard.csv", DASHBOARD_FIELDS, dashboard)

    rec_before_xlsx = recommendation_from_dashboard(dashboard, xlsx_ok=True)
    summary_rows = build_summary_rows(dashboard, rec_before_xlsx)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary_rows)

    xlsx_ok = True
    try:
        create_xlsx(output_dir, args.node_exe, args.node_modules)
    except Exception as exc:  # noqa: BLE001
        xlsx_ok = False
        print(f"xlsx_generation_error={exc}")

    rec = recommendation_from_dashboard(dashboard, xlsx_ok=xlsx_ok)
    if rec != rec_before_xlsx:
        summary_rows = build_summary_rows(dashboard, rec)
        write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary_rows)

    write_report(
        output_dir / "stage_enterprise_quota_price_comparison_v0_1_report.md",
        dashboard,
        comparison,
        candidate_pool,
        market_rows,
        ai_rows,
        supplement_rows,
        rec,
    )

    workbook_total_rows = (
        len(comparison)
        + len(candidate_pool)
        + len(market_rows)
        + len(ai_rows)
        + len(supplement_rows)
        + len(dashboard)
        + len(summary_rows)
    )
    update_manifest(project_root, output_dir, workbook_total_rows)
    (output_dir / "summary_for_xlsx.csv").unlink(missing_ok=True)

    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    print(f"recommendation={rec}")
    print(f"quota_comparison_rows={len(comparison)}")
    print(f"province_price_complete_rows={metrics.get('province_price_complete_rows', 0)}")
    print(f"enterprise_candidate_available_rows={metrics.get('enterprise_candidate_available_rows', 0)}")
    print(f"market_candidate_available_rows={metrics.get('market_candidate_available_rows', 0)}")
    print(f"ai_recommendation_rows={len(ai_rows)}")
    print(f"auto_apply_allowed_count={metrics.get('ai_auto_apply_allowed_count', 0)}")
    print(f"locked_internal_price_count={metrics.get('locked_internal_price_count', 0)}")
    print(f"candidate_pool_rows={len(candidate_pool)}")
    print(f"supplement_price_rows={len(supplement_rows)}")
    print(f"xlsx_exists={(output_dir / 'Enterprise_Quota_Price_Comparison_V0_1_Review.xlsx').exists()}")
    print(f"output_dir={output_dir}")
    return 0 if xlsx_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
