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
GD_BASE_REL = RUNS_REL / "SOURCE_BASELINE_LOCK_1" / "GD2018_normalized_full_quota_parse_review"
PRICE_REFRESH_REL = RUNS_REL / "PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1"
ALIGNMENT_REL = RUNS_REL / "ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1"
OUTPUT_DIR_REL = RUNS_REL / "ENTERPRISE_QUOTA_MANUAL_PRICING_REVIEW_V0_1"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

GD_QUOTA_REL = GD_BASE_REL / "gd2018_normalized_quota_items_full_review.csv"
GD_PRICING_REL = GD_BASE_REL / "gd2018_normalized_pricing_fields_full_review.csv"
INTERNAL_V2_REL = PRICE_REFRESH_REL / "internal_price_item_candidate_v2.csv"
UNIT_V2_REL = PRICE_REFRESH_REL / "internal_price_unit_normalized_v2.csv"
MARKET_NORMALIZED_REL = PRICE_REFRESH_REL / "market_price_normalized_items.csv"
ALIGNMENT_CANDIDATE_REL = ALIGNMENT_REL / "internal_price_to_gd_quota_candidate.csv"
COVERAGE_MATRIX_REL = ALIGNMENT_REL / "gd_quota_price_coverage_matrix_3712.csv"

NODE_EXE_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)
NODE_MODULES_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
)

STAGE_NAME = "ENTERPRISE_QUOTA_MANUAL_PRICING_REVIEW_V0_1"
REVIEW_STATUS = "pending"

MAIN_FIELDS = [
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
    "enterprise_candidate_count",
    "enterprise_candidate_ids",
    "enterprise_candidate_names",
    "enterprise_candidate_units",
    "enterprise_labor_fee_candidate",
    "enterprise_material_fee_candidate",
    "enterprise_machine_fee_candidate",
    "enterprise_management_fee_candidate",
    "enterprise_total_fee_candidate",
    "enterprise_unit_scale_note",
    "enterprise_candidate_confidence",
    "enterprise_candidate_status",
    "enterprise_price_lock_status",
    "diff_labor_fee",
    "diff_material_fee",
    "diff_machine_fee",
    "diff_management_fee",
    "diff_total_fee",
    "diff_total_rate",
    "price_variance_level",
    "risk_flags",
    "ai_recommended_price_source",
    "ai_recommended_labor_fee",
    "ai_recommended_material_fee",
    "ai_recommended_machine_fee",
    "ai_recommended_management_fee",
    "ai_recommended_total_fee",
    "ai_recommendation_basis",
    "ai_confidence_level",
    "ai_auto_apply_allowed",
    "cost_engineer_decision",
    "human_selected_price_source",
    "human_selected_labor_fee",
    "human_selected_material_fee",
    "human_selected_machine_fee",
    "human_selected_management_fee",
    "human_selected_total_fee",
    "human_lock_status",
    "cost_engineer_comment",
]

DETAIL_FIELDS = [
    "quota_source_code",
    "quota_name_candidate",
    "quota_unit",
    "internal_price_id",
    "internal_price_name",
    "internal_unit",
    "internal_labor_fee",
    "internal_material_fee",
    "internal_machine_fee",
    "internal_management_fee",
    "internal_total_fee",
    "scaled_labor_fee",
    "scaled_material_fee",
    "scaled_machine_fee",
    "scaled_management_fee",
    "scaled_total_fee",
    "unit_scale_factor",
    "unit_scale_note",
    "match_type",
    "match_confidence",
    "candidate_rank",
    "lock_status",
    "human_decision",
    "human_comment",
]

FLAG_FIELDS = [
    "flag_id",
    "quota_source_code",
    "quota_name_candidate",
    "issue_type",
    "severity",
    "province_total_fee",
    "enterprise_total_fee",
    "diff_total_fee",
    "diff_total_rate",
    "enterprise_candidate_ids",
    "remark",
    "review_status",
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
    "enterprise_quota_manual_pricing_review_v0_1.csv",
    "enterprise_price_candidate_detail_v0_1.csv",
    "price_variance_review_flags_v0_1.csv",
    "ai_price_recommendation_explanation_v0_1.csv",
    "manual_pricing_review_dashboard.csv",
    "Enterprise_Quota_Manual_Pricing_Review_V0_1.xlsx",
    "stage_enterprise_quota_manual_pricing_review_v0_1_report.md",
]

STRONG_MATCH_TYPES = {"exact_name_unit_candidate", "strong_semantic_candidate"}
CATEGORY_MATCH_TYPES = {"category_semantic_candidate"}
WEAK_MATCH_TYPES = {"weak_candidate"}
NO_MATCH_TYPES = {"no_match"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build enterprise quota manual pricing review V0.1 workbook.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--node-exe", type=Path, default=NODE_EXE_DEFAULT)
    parser.add_argument("--node-modules", type=Path, default=NODE_MODULES_DEFAULT)
    return parser.parse_args()


def norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").strip()


def compact(value: Any) -> str:
    return re.sub(r"\s+", "", norm(value))


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
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return Decimal(match.group(0))
        except InvalidOperation:
            return None


def decimal_text(value: Optional[Decimal], places: str = "0.01") -> str:
    if value is None:
        return ""
    quantized = value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    text = format(quantized.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def parse_confidence(value: Any) -> Decimal:
    parsed = to_decimal(value)
    return parsed if parsed is not None else Decimal("0")


def normalized_unit_text(unit: Any) -> str:
    value = compact(unit).lower()
    replacements = {
        "m³": "m3",
        "m^3": "m3",
        "㎥": "m3",
        "立方米": "m3",
        "m²": "m2",
        "m^2": "m2",
        "㎡": "m2",
        "平方米": "m2",
        "米": "m",
        "吨": "t",
        "千克": "kg",
        "公斤": "kg",
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    return value


def unit_multiplier_and_base(unit: Any) -> Tuple[Optional[Decimal], str]:
    value = normalized_unit_text(unit)
    if not value:
        return None, ""
    if value == "kg":
        return Decimal("1"), "kg"
    if value == "t":
        return Decimal("1"), "t"
    match = re.match(r"^(\d+(?:\.\d+)?)(.+)$", value)
    if match:
        return Decimal(match.group(1)), match.group(2)
    return Decimal("1"), value


def direct_unit_scale(internal_unit: str, quota_unit: str) -> Tuple[Optional[Decimal], str]:
    internal = normalized_unit_text(internal_unit)
    quota = normalized_unit_text(quota_unit)
    if not internal or not quota:
        return None, "unit_missing_or_blank"
    if internal == quota:
        return Decimal("1"), "same_unit"
    if internal == "kg" and quota == "t":
        return Decimal("1000"), "kg_to_t_price_multiply_1000_quantity_multiply_0.001"
    if internal == "t" and quota == "kg":
        return Decimal("0.001"), "t_to_kg_price_multiply_0.001_quantity_multiply_1000"
    internal_mult, internal_base = unit_multiplier_and_base(internal)
    quota_mult, quota_base = unit_multiplier_and_base(quota)
    if internal_mult is not None and quota_mult is not None and internal_base and internal_base == quota_base:
        return quota_mult / internal_mult, f"{internal}_to_{quota}_price_multiply_{decimal_text(quota_mult / internal_mult, '0.000001')}"
    return None, f"unit_unparsed_or_incompatible:{internal}->{quota}"


def price_values(row: Dict[str, str], prefix: str = "") -> Dict[str, str]:
    return {
        "labor": norm(row.get(f"{prefix}labor_fee")),
        "material": norm(row.get(f"{prefix}material_fee")),
        "machine": norm(row.get(f"{prefix}machine_fee")),
        "management": norm(row.get(f"{prefix}management_fee")),
        "total": norm(row.get(f"{prefix}total_fee")),
    }


def multiply(value: Any, factor: Optional[Decimal]) -> str:
    amount = to_decimal(value)
    if amount is None or factor is None:
        return ""
    return decimal_text(amount * factor)


def diff_text(left: Any, right: Any) -> str:
    a = to_decimal(left)
    b = to_decimal(right)
    if a is None or b is None:
        return ""
    return decimal_text(a - b)


def rate_text(diff: Any, base: Any) -> str:
    diff_dec = to_decimal(diff)
    base_dec = to_decimal(base)
    if diff_dec is None or base_dec is None or base_dec == 0:
        return ""
    return decimal_text(diff_dec / base_dec, "0.0001")


def province_status(values: Dict[str, str]) -> str:
    if all(values.values()):
        return "component_complete"
    if values["total"]:
        return "total_available_component_partial"
    if any(values.values()):
        return "partial"
    return "missing"


def old_ip_to_v2_id(old_id: str) -> str:
    match = re.match(r"^IP-(\d+)$", norm(old_id))
    if not match:
        return ""
    return f"IP2-{int(match.group(1)):06d}"


def join_unique(values: Iterable[Any]) -> str:
    seen = set()
    out = []
    for value in values:
        text = norm(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return ";".join(out)


def candidate_sort_key(row: Dict[str, Any]) -> Tuple[int, Decimal, str]:
    match_type = norm(row.get("match_type"))
    if match_type in STRONG_MATCH_TYPES:
        tier = 0
    elif match_type in CATEGORY_MATCH_TYPES:
        tier = 1
    elif match_type in WEAK_MATCH_TYPES:
        tier = 2
    else:
        tier = 3
    return (tier, -parse_confidence(row.get("match_confidence")), norm(row.get("internal_price_id")))


def build_indexes(
    quotas: Sequence[Dict[str, str]],
    pricing: Sequence[Dict[str, str]],
    internals_v2: Sequence[Dict[str, str]],
    alignments: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    pricing_by_code = {norm(row.get("source_code")): row for row in pricing if norm(row.get("source_code"))}
    internal_by_id = {norm(row.get("internal_price_id")): row for row in internals_v2 if norm(row.get("internal_price_id"))}
    internal_by_name_unit: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in internals_v2:
        key = (compact(row.get("raw_name")), normalized_unit_text(row.get("unit_normalized") or row.get("raw_unit")))
        if key[0] and key not in internal_by_name_unit:
            internal_by_name_unit[key] = row
    alignments_by_quota: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for align in alignments:
        quota_code = norm(align.get("matched_quota_source_code"))
        if not quota_code or norm(align.get("match_type")) in NO_MATCH_TYPES:
            continue
        v2_id = old_ip_to_v2_id(align.get("internal_price_id"))
        internal = internal_by_id.get(v2_id)
        if internal is None:
            key = (compact(align.get("internal_raw_name")), normalized_unit_text(align.get("internal_unit")))
            internal = internal_by_name_unit.get(key)
        if internal is None:
            enriched = dict(align)
            enriched["internal_v2_missing"] = "true"
        else:
            enriched = dict(align)
            enriched["internal_v2_missing"] = "false"
            enriched["internal_price_id_v2"] = internal["internal_price_id"]
        alignments_by_quota[quota_code].append(enriched)
    for rows in alignments_by_quota.values():
        rows.sort(key=candidate_sort_key)
    return {
        "pricing_by_code": pricing_by_code,
        "internal_by_id": internal_by_id,
        "internal_by_name_unit": internal_by_name_unit,
        "alignments_by_quota": alignments_by_quota,
    }


def resolve_internal(align: Dict[str, Any], indexes: Dict[str, Any]) -> Optional[Dict[str, str]]:
    internal_id = norm(align.get("internal_price_id_v2")) or old_ip_to_v2_id(align.get("internal_price_id"))
    internal = indexes["internal_by_id"].get(internal_id)
    if internal is not None:
        return internal
    key = (compact(align.get("internal_raw_name")), normalized_unit_text(align.get("internal_unit")))
    return indexes["internal_by_name_unit"].get(key)


def scaled_candidate_values(internal: Dict[str, str], quota_unit: str) -> Tuple[Dict[str, str], str, str]:
    factor, note = direct_unit_scale(internal.get("unit_normalized") or internal.get("raw_unit"), quota_unit)
    if factor is None:
        return {"labor": "", "material": "", "machine": "", "management": "", "total": ""}, "", note
    values = {
        "labor": multiply(internal.get("labor_fee"), factor),
        "material": multiply(internal.get("material_fee"), factor),
        "machine": multiply(internal.get("machine_fee"), factor),
        "management": multiply(internal.get("management_fee"), factor),
        "total": multiply(internal.get("total_fee"), factor),
    }
    return values, decimal_text(factor, "0.000001"), note


def build_candidate_detail(
    quotas: Sequence[Dict[str, str]],
    indexes: Dict[str, Any],
) -> List[Dict[str, Any]]:
    quota_by_code = {norm(row.get("source_code")): row for row in quotas}
    out: List[Dict[str, Any]] = []
    for quota_code in sorted(indexes["alignments_by_quota"].keys()):
        quota = quota_by_code.get(quota_code, {})
        quota_unit = norm(quota.get("unit"))
        rows = indexes["alignments_by_quota"][quota_code]
        for rank, align in enumerate(rows, start=1):
            internal = resolve_internal(align, indexes) or {}
            scaled, factor, note = scaled_candidate_values(internal, quota_unit) if internal else (
                {"labor": "", "material": "", "machine": "", "management": "", "total": ""},
                "",
                "internal_v2_candidate_missing",
            )
            out.append(
                {
                    "quota_source_code": quota_code,
                    "quota_name_candidate": norm(quota.get("quota_name_candidate") or align.get("matched_quota_name_candidate")),
                    "quota_unit": quota_unit,
                    "internal_price_id": norm(internal.get("internal_price_id") or align.get("internal_price_id")),
                    "internal_price_name": norm(internal.get("name_candidate") or align.get("internal_name_candidate") or align.get("internal_raw_name")),
                    "internal_unit": norm(internal.get("unit_normalized") or align.get("internal_unit") or internal.get("raw_unit")),
                    "internal_labor_fee": norm(internal.get("labor_fee")),
                    "internal_material_fee": norm(internal.get("material_fee")),
                    "internal_machine_fee": norm(internal.get("machine_fee")),
                    "internal_management_fee": norm(internal.get("management_fee")),
                    "internal_total_fee": norm(internal.get("total_fee") or align.get("internal_total_fee")),
                    "scaled_labor_fee": scaled["labor"],
                    "scaled_material_fee": scaled["material"],
                    "scaled_machine_fee": scaled["machine"],
                    "scaled_management_fee": scaled["management"],
                    "scaled_total_fee": scaled["total"],
                    "unit_scale_factor": factor,
                    "unit_scale_note": note,
                    "match_type": norm(align.get("match_type")),
                    "match_confidence": norm(align.get("match_confidence")),
                    "candidate_rank": rank,
                    "lock_status": "candidate_only",
                    "human_decision": "",
                    "human_comment": "",
                }
            )
    return out


def variance_level(diff_rate: str, has_candidate: bool, unit_note: str) -> str:
    if not has_candidate:
        return "no_enterprise_candidate"
    if unit_note.startswith("unit_unparsed") or unit_note == "internal_v2_candidate_missing":
        return "unit_review_required"
    rate = to_decimal(diff_rate)
    if rate is None:
        return "manual_review_required"
    abs_rate = abs(rate)
    if abs_rate >= Decimal("0.50"):
        return "high"
    if abs_rate >= Decimal("0.15"):
        return "medium"
    return "low"


def build_ai(
    quota_code: str,
    quota_name: str,
    top: Optional[Dict[str, Any]],
    province_values: Dict[str, str],
    diff_rate: str,
    risk_flags: str,
    price_level: str,
) -> Dict[str, Any]:
    if top is None:
        source = "province_quota_fallback"
        values = province_values
        basis = "no_enterprise_candidate;market_price_not_loaded;province_quota_preserved_for_manual_review"
        confidence = "medium" if province_values["total"] else "low"
    elif price_level == "low" and norm(top.get("match_type")) in STRONG_MATCH_TYPES and norm(top.get("unit_scale_factor")):
        source = "enterprise_internal_candidate"
        values = {
            "labor": norm(top.get("scaled_labor_fee")),
            "material": norm(top.get("scaled_material_fee")),
            "machine": norm(top.get("scaled_machine_fee")),
            "management": norm(top.get("scaled_management_fee")),
            "total": norm(top.get("scaled_total_fee")),
        }
        basis = f"strong_internal_candidate;match_type:{top.get('match_type')};confidence:{top.get('match_confidence')};{top.get('unit_scale_note')}"
        confidence = "high" if parse_confidence(top.get("match_confidence")) >= Decimal("0.90") else "medium"
    else:
        source = "manual_review_required"
        values = {"labor": "", "material": "", "machine": "", "management": "", "total": ""}
        basis = f"enterprise_candidate_exists_but_needs_review;variance_level:{price_level};market_price_not_loaded;top_candidate:{norm(top.get('internal_price_id'))}"
        confidence = "low" if price_level in {"high", "unit_review_required"} else "medium"
    return {
        "quota_source_code": quota_code,
        "quota_name_candidate": quota_name,
        "recommended_price_source": source,
        "recommended_labor_fee": values["labor"],
        "recommended_material_fee": values["material"],
        "recommended_machine_fee": values["machine"],
        "recommended_management_fee": values["management"],
        "recommended_total_fee": values["total"],
        "recommendation_basis": basis,
        "confidence_level": confidence,
        "risk_flags": risk_flags,
        "auto_apply_allowed": "false",
        "human_review_required": "true",
    }


def add_flag(
    flags: List[Dict[str, Any]],
    quota_code: str,
    quota_name: str,
    issue_type: str,
    severity: str,
    province_total: str,
    enterprise_total: str,
    diff_total: str,
    diff_rate: str,
    candidate_ids: str,
    remark: str,
) -> None:
    flags.append(
        {
            "flag_id": f"PRICE_FLAG_{len(flags) + 1:06d}",
            "quota_source_code": quota_code,
            "quota_name_candidate": quota_name,
            "issue_type": issue_type,
            "severity": severity,
            "province_total_fee": province_total,
            "enterprise_total_fee": enterprise_total,
            "diff_total_fee": diff_total,
            "diff_total_rate": diff_rate,
            "enterprise_candidate_ids": candidate_ids,
            "remark": remark,
            "review_status": REVIEW_STATUS,
        }
    )


def build_outputs(
    quotas: Sequence[Dict[str, str]],
    pricing_by_code: Dict[str, Dict[str, str]],
    detail_by_quota: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    main_rows: List[Dict[str, Any]] = []
    flags: List[Dict[str, Any]] = []
    ai_rows: List[Dict[str, Any]] = []
    for quota in quotas:
        quota_code = norm(quota.get("source_code"))
        quota_name = norm(quota.get("quota_name_candidate"))
        pricing = pricing_by_code.get(quota_code, {})
        province_values = {
            "labor": norm(pricing.get("raw_labor_fee") or quota.get("raw_labor_fee")),
            "material": norm(pricing.get("raw_material_fee") or quota.get("raw_material_fee")),
            "machine": norm(pricing.get("raw_machine_fee") or quota.get("raw_machine_fee")),
            "management": norm(pricing.get("raw_management_fee") or quota.get("raw_management_fee")),
            "total": norm(pricing.get("raw_total_fee") or quota.get("raw_total_fee")),
        }
        candidates = detail_by_quota.get(quota_code, [])
        top = candidates[0] if candidates else None
        candidate_ids = join_unique(row.get("internal_price_id") for row in candidates)
        candidate_names = join_unique(row.get("internal_price_name") for row in candidates)
        candidate_units = join_unique(row.get("internal_unit") for row in candidates)
        if top:
            enterprise_values = {
                "labor": norm(top.get("scaled_labor_fee")),
                "material": norm(top.get("scaled_material_fee")),
                "machine": norm(top.get("scaled_machine_fee")),
                "management": norm(top.get("scaled_management_fee")),
                "total": norm(top.get("scaled_total_fee")),
            }
            candidate_status = "candidate_available"
            if not norm(top.get("unit_scale_factor")):
                candidate_status = "candidate_available_unit_review_required"
        else:
            enterprise_values = {"labor": "", "material": "", "machine": "", "management": "", "total": ""}
            candidate_status = "missing"

        diff_labor = diff_text(enterprise_values["labor"], province_values["labor"])
        diff_material = diff_text(enterprise_values["material"], province_values["material"])
        diff_machine = diff_text(enterprise_values["machine"], province_values["machine"])
        diff_management = diff_text(enterprise_values["management"], province_values["management"])
        diff_total = diff_text(enterprise_values["total"], province_values["total"])
        diff_rate = rate_text(diff_total, province_values["total"])
        level = variance_level(diff_rate, bool(top), norm(top.get("unit_scale_note")) if top else "")
        risk_list: List[str] = []
        if not candidates:
            risk_list.append("enterprise_price_missing")
            add_flag(flags, quota_code, quota_name, "enterprise_price_missing", "medium", province_values["total"], "", "", "", "", "No enterprise internal price candidate.")
        if len(candidates) > 1:
            risk_list.append("enterprise_candidate_multiple")
            add_flag(flags, quota_code, quota_name, "enterprise_candidate_multiple", "medium", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, f"{len(candidates)} enterprise candidates hit this quota.")
        if top and not norm(top.get("unit_scale_factor")):
            risk_list.append("enterprise_candidate_unit_unparsed")
            add_flag(flags, quota_code, quota_name, "enterprise_candidate_unit_unparsed", "high", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, norm(top.get("unit_scale_note")))
        if province_status(province_values) != "component_complete":
            risk_list.append("province_component_partial")
            add_flag(flags, quota_code, quota_name, "province_component_partial", "low", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, "Province total exists but one or more components are blank.")
        if level == "high":
            risk_list.append("total_fee_variance_high")
            add_flag(flags, quota_code, quota_name, "total_fee_variance_high", "high", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, "Absolute total fee variance rate >= 50%.")
        for field, issue_name in [
            ("labor", "labor_fee_variance_high"),
            ("material", "material_fee_variance_high"),
            ("machine", "machine_fee_variance_high"),
            ("management", "management_fee_missing"),
        ]:
            if field == "management" and top and not enterprise_values["management"]:
                risk_list.append(issue_name)
                add_flag(flags, quota_code, quota_name, issue_name, "medium", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, "Enterprise internal source does not provide management fee.")
            elif field != "management":
                d = to_decimal(diff_text(enterprise_values[field], province_values[field]))
                base = to_decimal(province_values[field])
                if d is not None and base not in {None, Decimal("0")} and abs(d / base) >= Decimal("0.50"):
                    risk_list.append(issue_name)
                    add_flag(flags, quota_code, quota_name, issue_name, "medium", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, f"Absolute {field} fee variance rate >= 50%.")
        if risk_list and ("total_fee_variance_high" in risk_list or "enterprise_candidate_unit_unparsed" in risk_list):
            risk_list.append("manual_review_required")
            add_flag(flags, quota_code, quota_name, "manual_review_required", "high", province_values["total"], enterprise_values["total"], diff_total, diff_rate, candidate_ids, "Risk flags require cost engineer review.")

        risk_flags = join_unique(risk_list)
        ai_row = build_ai(quota_code, quota_name, top, province_values, diff_rate, risk_flags, level)
        ai_rows.append(ai_row)
        main_rows.append(
            {
                "quota_source_code": quota_code,
                "quota_raw_name": norm(quota.get("raw_name")),
                "quota_name_candidate": quota_name,
                "quota_feature_text_candidate": norm(quota.get("quota_feature_text_candidate")),
                "quota_unit": norm(quota.get("unit")),
                "source_code_prefix": norm(quota.get("code_prefix")),
                "province_labor_fee": province_values["labor"],
                "province_material_fee": province_values["material"],
                "province_machine_fee": province_values["machine"],
                "province_management_fee": province_values["management"],
                "province_total_fee": province_values["total"],
                "province_price_status": province_status(province_values),
                "enterprise_candidate_count": str(len(candidates)),
                "enterprise_candidate_ids": candidate_ids,
                "enterprise_candidate_names": candidate_names,
                "enterprise_candidate_units": candidate_units,
                "enterprise_labor_fee_candidate": enterprise_values["labor"],
                "enterprise_material_fee_candidate": enterprise_values["material"],
                "enterprise_machine_fee_candidate": enterprise_values["machine"],
                "enterprise_management_fee_candidate": enterprise_values["management"],
                "enterprise_total_fee_candidate": enterprise_values["total"],
                "enterprise_unit_scale_note": norm(top.get("unit_scale_note")) if top else "",
                "enterprise_candidate_confidence": norm(top.get("match_confidence")) if top else "",
                "enterprise_candidate_status": candidate_status,
                "enterprise_price_lock_status": "candidate_only",
                "diff_labor_fee": diff_labor,
                "diff_material_fee": diff_material,
                "diff_machine_fee": diff_machine,
                "diff_management_fee": diff_management,
                "diff_total_fee": diff_total,
                "diff_total_rate": diff_rate,
                "price_variance_level": level,
                "risk_flags": risk_flags,
                "ai_recommended_price_source": ai_row["recommended_price_source"],
                "ai_recommended_labor_fee": ai_row["recommended_labor_fee"],
                "ai_recommended_material_fee": ai_row["recommended_material_fee"],
                "ai_recommended_machine_fee": ai_row["recommended_machine_fee"],
                "ai_recommended_management_fee": ai_row["recommended_management_fee"],
                "ai_recommended_total_fee": ai_row["recommended_total_fee"],
                "ai_recommendation_basis": ai_row["recommendation_basis"],
                "ai_confidence_level": ai_row["confidence_level"],
                "ai_auto_apply_allowed": "false",
                "cost_engineer_decision": "",
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
    return main_rows, flags, ai_rows


def metric_row(name: str, value: Any, expected: str, status: str, severity: str, remark: str) -> Dict[str, Any]:
    return {
        "metric_name": name,
        "metric_value": value,
        "expected_or_threshold": expected,
        "status": status,
        "severity": severity,
        "remark": remark,
    }


def build_dashboard(main_rows: Sequence[Dict[str, Any]], detail_rows: Sequence[Dict[str, Any]], flags: Sequence[Dict[str, Any]], ai_rows: Sequence[Dict[str, Any]], market_rows: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    total = len(main_rows)
    province_price_rows = sum(1 for row in main_rows if norm(row.get("province_total_fee")))
    province_all = sum(1 for row in main_rows if norm(row.get("province_price_status")) == "component_complete")
    enterprise_available = sum(1 for row in main_rows if int(norm(row.get("enterprise_candidate_count")) or "0") > 0)
    multiple = sum(1 for row in main_rows if int(norm(row.get("enterprise_candidate_count")) or "0") > 1)
    high_variance = sum(1 for row in main_rows if norm(row.get("price_variance_level")) == "high")
    ai_counts = Counter(row.get("recommended_price_source") for row in ai_rows)
    market_status = "not_loaded" if len(market_rows) == 0 else "loaded_requires_market_alignment_stage"
    market_cols = sum(1 for field in MAIN_FIELDS if field.startswith("market_"))
    auto_apply = sum(1 for row in ai_rows if norm(row.get("auto_apply_allowed")) != "false")
    human_locked = sum(1 for row in main_rows if norm(row.get("human_lock_status")) != REVIEW_STATUS)
    approved = 0
    locked_internal = sum(1 for row in detail_rows if norm(row.get("lock_status")) != "candidate_only")
    return [
        metric_row("total_quota_rows", total, "3712", "pass" if total == 3712 else "fail", "critical", "One row per GD2018 quota."),
        metric_row("province_price_rows", province_price_rows, "3712", "pass" if province_price_rows == 3712 else "warn", "high", "Rows with province total fee."),
        metric_row("province_all_component_complete_rows", province_all, "informational", "info", "medium", "Rows with all province labor/material/machine/management/total fields non-empty."),
        metric_row("enterprise_candidate_available_rows", enterprise_available, "informational", "info", "medium", "Rows with at least one enterprise internal candidate."),
        metric_row("enterprise_candidate_missing_rows", total - enterprise_available, "informational", "info", "medium", "Rows without enterprise internal candidate."),
        metric_row("multiple_enterprise_candidate_rows", multiple, "informational", "info", "medium", "Rows with more than one candidate."),
        metric_row("high_variance_rows", high_variance, "manual review", "warn" if high_variance else "pass", "high", "Rows where absolute total variance rate >= 50%."),
        metric_row("ai_recommendation_rows", len(ai_rows), "3712", "pass" if len(ai_rows) == 3712 else "fail", "critical", "One AI explanation row per quota."),
        metric_row("ai_enterprise_recommendation_rows", ai_counts.get("enterprise_internal_candidate", 0), "informational", "info", "medium", "AI recommends enterprise candidate only for strong, convertible, reasonable variance rows."),
        metric_row("ai_province_fallback_rows", ai_counts.get("province_quota_fallback", 0), "informational", "info", "medium", "AI falls back to province price when enterprise candidate is missing."),
        metric_row("ai_manual_review_required_rows", ai_counts.get("manual_review_required", 0), "informational", "info", "high", "AI refuses automatic recommendation due to candidate/variance/unit risk."),
        metric_row("market_price_status", market_status, "not_loaded when market normalized rows are 0", "pass" if market_status == "not_loaded" else "warn", "high", "Market prices are not mixed into the main table in this stage."),
        metric_row("market_price_columns_in_main_table", market_cols, "0", "pass" if market_cols == 0 else "fail", "critical", "Main table must not include blank market labor/material/machine/management/total columns."),
        metric_row("auto_apply_allowed_count", auto_apply, "0", "pass" if auto_apply == 0 else "fail", "critical", "AI auto apply is prohibited."),
        metric_row("human_locked_count", human_locked, "0", "pass" if human_locked == 0 else "fail", "critical", "Human lock status remains pending."),
        metric_row("approved_count", approved, "0", "pass", "critical", "No approved state generated."),
        metric_row("locked_internal_price_id_count", locked_internal, "0", "pass" if locked_internal == 0 else "fail", "critical", "Internal price IDs are not locked."),
        metric_row("database_write_detected", 0, "0", "pass", "critical", "This stage writes files only."),
    ]


def build_summary(dashboard: Sequence[Dict[str, Any]], rec: str) -> List[Dict[str, Any]]:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    return [
        {"metric_name": "stage_name", "metric_value": STAGE_NAME, "remark": "Manual pricing review workbook only."},
        {"metric_name": "recommendation", "metric_value": rec, "remark": "Not approved; not formal enterprise quota."},
        {"metric_name": "total_quota_rows", "metric_value": metrics.get("total_quota_rows", 0), "remark": "Must equal 3712."},
        {"metric_name": "enterprise_candidate_available_rows", "metric_value": metrics.get("enterprise_candidate_available_rows", 0), "remark": "Candidate-only links."},
        {"metric_name": "high_variance_rows", "metric_value": metrics.get("high_variance_rows", 0), "remark": "Manual review focus."},
        {"metric_name": "market_price_status", "metric_value": metrics.get("market_price_status", ""), "remark": "No market columns in main table when not_loaded."},
        {"metric_name": "auto_apply_allowed_count", "metric_value": metrics.get("auto_apply_allowed_count", 0), "remark": "Must be 0."},
    ]


def recommendation_from_dashboard(dashboard: Sequence[Dict[str, Any]], xlsx_ok: bool) -> str:
    if not xlsx_ok:
        return "blocked_xlsx_generation_failed"
    metrics = {row["metric_name"]: str(row["metric_value"]) for row in dashboard}
    hard_fail = [
        metrics.get("total_quota_rows") != "3712",
        metrics.get("market_price_columns_in_main_table") != "0",
        metrics.get("auto_apply_allowed_count") != "0",
        metrics.get("human_locked_count") != "0",
        metrics.get("approved_count") != "0",
        metrics.get("locked_internal_price_id_count") != "0",
        metrics.get("database_write_detected") != "0",
    ]
    if any(hard_fail):
        return "manual_pricing_review_partial_manual_intervention_required"
    return "manual_pricing_review_ready_for_cost_engineer"


def create_xlsx(output_dir: Path, node_exe: Path, node_modules: Path) -> None:
    specs = [
        ["manual_pricing_review_3712", "enterprise_quota_manual_pricing_review_v0_1.csv", len(MAIN_FIELDS)],
        ["enterprise_price_candidate_detail", "enterprise_price_candidate_detail_v0_1.csv", len(DETAIL_FIELDS)],
        ["variance_review_flags", "price_variance_review_flags_v0_1.csv", len(FLAG_FIELDS)],
        ["ai_recommendation_explanation", "ai_price_recommendation_explanation_v0_1.csv", len(AI_FIELDS)],
        ["dashboard", "manual_pricing_review_dashboard.csv", len(DASHBOARD_FIELDS)],
        ["summary", "summary_for_xlsx.csv", len(SUMMARY_FIELDS)],
    ]
    builder = r'''
import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = process.argv[2];
const specs = JSON.parse(process.argv[3]);
let workbook = null;
const actualSheets = [];
for (const spec of specs) {
  const [sheetName, fileName, colCount] = spec;
  const csvText = await fs.readFile(`${outputDir}/${fileName}`, "utf8");
  if (!workbook) {
    workbook = await Workbook.fromCSV(csvText, { sheetName });
  } else {
    await workbook.fromCSV(csvText, { sheetName });
  }
  const effectiveSheetName = sheetName.slice(0, 31);
  actualSheets.push(effectiveSheetName);
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
    effectiveSheetName === "summary" || effectiveSheetName === "dashboard" ? 26 : 18;
}
for (const sheetName of actualSheets) {
  await workbook.render({ sheetName, range: "A1:H20", scale: 1, format: "png" });
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/Enterprise_Quota_Manual_Pricing_Review_V0_1.xlsx`);
console.log(`xlsx=${outputDir}/Enterprise_Quota_Manual_Pricing_Review_V0_1.xlsx`);
'''
    with tempfile.TemporaryDirectory(prefix="manual_pricing_review_xlsx_") as tmp:
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
        builder_path = tmp_path / "build_manual_pricing_review.mjs"
        builder_path.write_text(builder, encoding="utf-8")
        subprocess.run(
            [str(node_exe), str(builder_path), str(output_dir), json.dumps(specs)],
            cwd=tmp_path,
            check=True,
        )
    sidecar = output_dir / "Enterprise_Quota_Manual_Pricing_Review_V0_1.xlsx.inspect.ndjson"
    if sidecar.exists():
        sidecar.unlink()


def write_report(
    path: Path,
    dashboard: Sequence[Dict[str, Any]],
    flags: Sequence[Dict[str, Any]],
    rec: str,
) -> None:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    flag_counts = Counter(row.get("issue_type") for row in flags)
    lines = [
        "# Stage ENTERPRISE-QUOTA-MANUAL-PRICING-REVIEW-V0.1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Generate a 3712-row GD2018-based manual pricing review workbook with province price fields, enterprise internal candidate fields, variance analysis, AI explanation fields, and blank human decision columns.",
        "",
        "## 2. Why This Workbook Is Needed",
        "",
        "The price-source refresh stage is a source governance view. Cost engineers need a quota-row workbook that keeps GD2018 as the main table and shows candidate prices and differences directly on each quota row.",
        "",
        "## 3. Market Price Handling",
        "",
        f"- market_price_status: {metrics.get('market_price_status')}",
        f"- market_price_columns_in_main_table: {metrics.get('market_price_columns_in_main_table')}",
        "- Market price normalized rows are not mixed into this workbook. No market prices were fabricated.",
        "",
        "## 4. Province Price Fields",
        "",
        f"- province_price_rows: {metrics.get('province_price_rows')}",
        f"- province_all_component_complete_rows: {metrics.get('province_all_component_complete_rows')}",
        "- Province labor/material/machine/management/total values are preserved from GD2018 pricing fields.",
        "",
        "## 5. Enterprise Price Candidate Fields",
        "",
        f"- enterprise_candidate_available_rows: {metrics.get('enterprise_candidate_available_rows')}",
        f"- enterprise_candidate_missing_rows: {metrics.get('enterprise_candidate_missing_rows')}",
        f"- multiple_enterprise_candidate_rows: {metrics.get('multiple_enterprise_candidate_rows')}",
        "- All internal price IDs remain candidate_only and are not locked.",
        "",
        "## 6. Unit Conversion Logic",
        "",
        "- m2/m3/m to 100m2/100m3/100m uses price factor 100 when the GD quota unit requires it.",
        "- kg to t uses price factor 1000 and records the direction in unit_scale_note.",
        "- Unparsed or incompatible unit conversions are flagged for manual review.",
        "",
        "## 7. Difference Analysis",
        "",
        f"- high_variance_rows: {metrics.get('high_variance_rows')}",
        f"- variance_flag_counts: {json.dumps(dict(flag_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 8. AI Recommendation Logic",
        "",
        "- Strong, convertible enterprise candidates with reasonable total variance can be recommended as enterprise_internal_candidate.",
        "- Missing enterprise candidates fall back to province_quota_fallback.",
        "- Abnormal variance or unit risk is marked manual_review_required.",
        "- auto_apply_allowed is always false.",
        f"- ai_enterprise_recommendation_rows: {metrics.get('ai_enterprise_recommendation_rows')}",
        f"- ai_province_fallback_rows: {metrics.get('ai_province_fallback_rows')}",
        f"- ai_manual_review_required_rows: {metrics.get('ai_manual_review_required_rows')}",
        "",
        "## 9. Human Review Workflow",
        "",
        "Cost engineers should review high variance rows, multiple candidates, unit conversion warnings, and blank management fee cases before filling human_selected_* fields.",
        "",
        "## 10. Not Approved / Not Final Statement",
        "",
        "This workbook is not an approved enterprise quota, not an internal_price_library, and not a database import. No approved or locked status is generated.",
        "",
        "## 11. Next Step Recommendation",
        "",
        rec,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def artifact_row_count(path: Path, workbook_total_rows: int) -> str:
    if path.suffix.lower() == ".csv":
        return csv_row_count(path)
    if path.suffix.lower() == ".xlsx":
        return str(workbook_total_rows)
    return ""


def manifest_row(project_root: Path, output_dir: Path, artifact_name: str, workbook_total_rows: int) -> Dict[str, Any]:
    path = output_dir / artifact_name
    exists = path.exists()
    source_files = [
        rel(project_root / GD_QUOTA_REL, project_root),
        rel(project_root / GD_PRICING_REL, project_root),
        rel(project_root / INTERNAL_V2_REL, project_root),
        rel(project_root / UNIT_V2_REL, project_root),
        rel(project_root / MARKET_NORMALIZED_REL, project_root),
        rel(project_root / ALIGNMENT_CANDIDATE_REL, project_root),
        rel(project_root / COVERAGE_MATRIX_REL, project_root),
    ]
    return {
        "stage_name": STAGE_NAME,
        "artifact_name": artifact_name,
        "expected_path": rel(path, project_root),
        "exists": str(exists).lower(),
        "file_size_bytes": path.stat().st_size if exists else 0,
        "row_count": artifact_row_count(path, workbook_total_rows) if exists else "",
        "sha256": sha256_file(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": ";".join(source_files),
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": "construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_ENTERPRISE_QUOTA_MANUAL_PRICING_REVIEW_V0_1",
        "status": "generated_pending_review" if exists else "missing",
        "remark": "manual pricing review artifact; no approved; no database write; no locked internal price id",
    }


def update_manifest(project_root: Path, output_dir: Path, workbook_total_rows: int) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    existing = read_csv(manifest_path)
    kept = [row for row in existing if norm(row.get("stage_name")) != STAGE_NAME]
    latest = [manifest_row(project_root, output_dir, name, workbook_total_rows) for name in OUTPUT_ARTIFACTS]
    all_rows = kept + latest
    write_csv(manifest_path, MANIFEST_FIELDS, all_rows)
    write_manifest_md(project_root, all_rows, latest)


def write_manifest_md(project_root: Path, all_rows: Sequence[Dict[str, Any]], latest: Sequence[Dict[str, Any]]) -> None:
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
        "- Manual pricing review outputs are pending review artifacts only and do not approve prices.",
        "- Internal price IDs remain candidate_only until a later human lock stage.",
        "- Market prices must not be fabricated or represented by blank labor/material/machine/management/total columns.",
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
        "## Latest Enterprise Quota Manual Pricing Review V0.1 Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_ENTERPRISE_QUOTA_MANUAL_PRICING_REVIEW_V0_1/`",
            "",
        ]
    )
    (project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


def validate_inputs(project_root: Path) -> List[str]:
    required = [
        GD_QUOTA_REL,
        GD_PRICING_REL,
        INTERNAL_V2_REL,
        UNIT_V2_REL,
        MARKET_NORMALIZED_REL,
        ALIGNMENT_CANDIDATE_REL,
        COVERAGE_MATRIX_REL,
    ]
    return [rel(project_root / path, project_root) for path in required if not (project_root / path).exists()]


def write_blocked_report(output_dir: Path, rec: str, missing: Sequence[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage ENTERPRISE-QUOTA-MANUAL-PRICING-REVIEW-V0.1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Generate manual pricing review workbook.",
        "",
        "## 2. Why This Workbook Is Needed",
        "",
        "Skipped because required inputs are missing.",
        "",
        "## 3. Market Price Handling",
        "",
        "Skipped.",
        "",
        "## 4. Province Price Fields",
        "",
        "Skipped.",
        "",
        "## 5. Enterprise Price Candidate Fields",
        "",
        "Skipped.",
        "",
        "## 6. Unit Conversion Logic",
        "",
        "Skipped.",
        "",
        "## 7. Difference Analysis",
        "",
        "Skipped.",
        "",
        "## 8. AI Recommendation Logic",
        "",
        "Skipped.",
        "",
        "## 9. Human Review Workflow",
        "",
        "Skipped.",
        "",
        "## 10. Not Approved / Not Final Statement",
        "",
        "No approved output generated.",
        "",
        "## 11. Next Step Recommendation",
        "",
        rec,
        "",
        "Missing inputs:",
    ]
    lines.extend(f"- `{item}`" for item in missing)
    (output_dir / "stage_enterprise_quota_manual_pricing_review_v0_1_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)
    missing = validate_inputs(project_root)
    if missing:
        write_blocked_report(output_dir, "blocked_missing_inputs", missing)
        print("recommendation=blocked_missing_inputs")
        for item in missing:
            print(f"missing_input={item}")
        return 2

    quotas = read_csv(project_root / GD_QUOTA_REL)
    pricing = read_csv(project_root / GD_PRICING_REL)
    internals_v2 = read_csv(project_root / INTERNAL_V2_REL)
    market_rows = read_csv(project_root / MARKET_NORMALIZED_REL)
    alignments = read_csv(project_root / ALIGNMENT_CANDIDATE_REL)
    indexes = build_indexes(quotas, pricing, internals_v2, alignments)
    detail_rows = build_candidate_detail(quotas, indexes)
    detail_by_quota: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        detail_by_quota[norm(row.get("quota_source_code"))].append(row)
    for rows in detail_by_quota.values():
        rows.sort(key=lambda row: int(norm(row.get("candidate_rank")) or "999999"))
    main_rows, flags, ai_rows = build_outputs(quotas, indexes["pricing_by_code"], detail_by_quota)
    dashboard = build_dashboard(main_rows, detail_rows, flags, ai_rows, market_rows)
    rec_before_xlsx = recommendation_from_dashboard(dashboard, xlsx_ok=True)
    summary_rows = build_summary(dashboard, rec_before_xlsx)

    write_csv(output_dir / "enterprise_quota_manual_pricing_review_v0_1.csv", MAIN_FIELDS, main_rows)
    write_csv(output_dir / "enterprise_price_candidate_detail_v0_1.csv", DETAIL_FIELDS, detail_rows)
    write_csv(output_dir / "price_variance_review_flags_v0_1.csv", FLAG_FIELDS, flags)
    write_csv(output_dir / "ai_price_recommendation_explanation_v0_1.csv", AI_FIELDS, ai_rows)
    write_csv(output_dir / "manual_pricing_review_dashboard.csv", DASHBOARD_FIELDS, dashboard)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary_rows)

    xlsx_ok = True
    try:
        create_xlsx(output_dir, args.node_exe, args.node_modules)
    except Exception as exc:  # noqa: BLE001
        xlsx_ok = False
        print(f"xlsx_generation_error={exc}")
    rec = recommendation_from_dashboard(dashboard, xlsx_ok=xlsx_ok)
    if rec != rec_before_xlsx:
        summary_rows = build_summary(dashboard, rec)
        write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary_rows)
    write_report(output_dir / "stage_enterprise_quota_manual_pricing_review_v0_1_report.md", dashboard, flags, rec)

    workbook_total_rows = len(main_rows) + len(detail_rows) + len(flags) + len(ai_rows) + len(dashboard) + len(summary_rows)
    update_manifest(project_root, output_dir, workbook_total_rows)
    (output_dir / "summary_for_xlsx.csv").unlink(missing_ok=True)

    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    print(f"recommendation={rec}")
    print(f"manual_pricing_rows={len(main_rows)}")
    print(f"enterprise_candidate_available_rows={metrics.get('enterprise_candidate_available_rows', 0)}")
    print(f"province_all_component_complete_rows={metrics.get('province_all_component_complete_rows', 0)}")
    print(f"multiple_candidate_rows={metrics.get('multiple_enterprise_candidate_rows', 0)}")
    print(f"high_variance_rows={metrics.get('high_variance_rows', 0)}")
    print(f"market_price_status={metrics.get('market_price_status', '')}")
    print(f"market_columns_in_main_table={metrics.get('market_price_columns_in_main_table', 0)}")
    print(f"ai_enterprise_recommendation_rows={metrics.get('ai_enterprise_recommendation_rows', 0)}")
    print(f"ai_province_fallback_rows={metrics.get('ai_province_fallback_rows', 0)}")
    print(f"ai_manual_review_required_rows={metrics.get('ai_manual_review_required_rows', 0)}")
    print(f"auto_apply_allowed_count={metrics.get('auto_apply_allowed_count', 0)}")
    print(f"locked_internal_price_id_count={metrics.get('locked_internal_price_id_count', 0)}")
    print(f"approved_count={metrics.get('approved_count', 0)}")
    print(f"xlsx_exists={(output_dir / 'Enterprise_Quota_Manual_Pricing_Review_V0_1.xlsx').exists()}")
    print(f"output_dir={output_dir}")
    return 0 if xlsx_ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
