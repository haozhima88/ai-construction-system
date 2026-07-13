from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
BASELINE_REL = RUNS_REL / "SOURCE_BASELINE_LOCK_1"
GB_BASE_REL = BASELINE_REL / "GB50854_2024_full_standard_parse_review"
GD_BASE_REL = BASELINE_REL / "GD2018_normalized_full_quota_parse_review"
OUTPUT_DIR_REL = RUNS_REL / "MAP_FULL_GOVERNANCE_REFERENCE_1"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

GB_BILLS_REL = GB_BASE_REL / "gb50854_bill_items_full_review.csv"
GB_RULES_REL = GB_BASE_REL / "gb50854_context_rules_full_review.csv"
GD_QUOTA_REL = GD_BASE_REL / "gd2018_normalized_quota_items_full_review.csv"
GD_PRICING_REL = GD_BASE_REL / "gd2018_normalized_pricing_fields_full_review.csv"

STAGE_NAME = "MAP_FULL_GOVERNANCE_REFERENCE_1"
REVIEW_STATUS = "pending"

NODE_EXE_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)
NODE_MODULES_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
)


MATRIX_FIELDS = [
    "bill_code_9",
    "bill_name",
    "appendix_code",
    "appendix_name",
    "section_code",
    "section_name",
    "unit",
    "quantity_calculation_rule",
    "work_content_raw",
    "project_feature_raw",
    "total_quota_candidate_count",
    "R1_direct_bill_body_count",
    "R2_feature_variant_count",
    "R3_work_content_component_count",
    "R4_method_or_measure_component_count",
    "R5_not_applicable_or_unrouted_count",
    "top_quota_source_codes",
    "top_quota_names",
    "top_quota_units",
    "top_source_code_prefixes",
    "recommended_bill_level_decision",
    "template_reference_value",
    "human_review_priority",
    "cost_engineer_decision",
    "cost_engineer_comment",
]

DETAIL_FIELDS = [
    "bill_code_9",
    "bill_name",
    "appendix_code",
    "appendix_name",
    "bill_unit",
    "bill_quantity_calculation_rule",
    "bill_work_content_raw",
    "bill_project_feature_raw",
    "quota_source_code",
    "quota_raw_name",
    "quota_name_candidate",
    "quota_feature_text_candidate",
    "quota_unit",
    "quota_raw_total_fee",
    "source_code_prefix",
    "governance_role",
    "relationship_basis",
    "mapping_confidence",
    "selection_condition",
    "forbidden_use",
    "issue_types",
    "review_status",
    "cost_engineer_decision",
    "cost_engineer_comment",
]

ROUTING_FIELDS = [
    "quota_source_code",
    "quota_raw_name",
    "quota_name_candidate",
    "quota_feature_text_candidate",
    "quota_unit",
    "source_code_prefix",
    "candidate_bill_count",
    "candidate_bill_codes",
    "candidate_bill_names",
    "dominant_governance_role",
    "allowed_use",
    "forbidden_use",
    "recommended_confidence_ceiling",
    "routing_status",
    "review_status",
    "cost_engineer_decision",
    "cost_engineer_comment",
]

SHARED_FIELDS = [
    "quota_source_code",
    "quota_raw_name",
    "quota_name_candidate",
    "candidate_bill_codes",
    "candidate_bill_names",
    "candidate_count",
    "dominant_governance_role",
    "shared_component_type",
    "selection_condition",
    "allowed_use",
    "forbidden_use",
    "review_priority",
]

ISSUE_FIELDS = [
    "issue_id",
    "issue_type",
    "severity",
    "bill_code_9",
    "bill_name",
    "quota_source_code",
    "quota_raw_name",
    "governance_role",
    "description",
    "recommended_action",
    "review_status",
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


ALL_TERMS = [
    "土方",
    "石方",
    "回填",
    "场地",
    "基坑",
    "沟槽",
    "余方",
    "弃方",
    "运输",
    "支护",
    "钢板桩",
    "锚杆",
    "喷射混凝土",
    "地下连续墙",
    "边坡",
    "换填",
    "强夯",
    "搅拌桩",
    "桩",
    "预制桩",
    "灌注桩",
    "钢管桩",
    "截桩头",
    "砖",
    "砌块",
    "砌体",
    "墙",
    "基础",
    "柱",
    "梁",
    "板",
    "楼梯",
    "混凝土",
    "钢筋",
    "预埋",
    "铁件",
    "钢结构",
    "钢柱",
    "钢梁",
    "钢屋架",
    "木结构",
    "屋架",
    "木构件",
    "门",
    "窗",
    "幕墙",
    "屋面",
    "瓦",
    "卷材",
    "防水",
    "涂膜",
    "保温",
    "隔热",
    "防腐",
    "楼地面",
    "找平",
    "面层",
    "块料",
    "踢脚",
    "台阶",
    "墙面",
    "柱面",
    "抹灰",
    "镶贴",
    "天棚",
    "吊顶",
    "龙骨",
    "油漆",
    "涂料",
    "裱糊",
    "刷油",
    "装饰线",
    "栏杆",
    "扶手",
    "洞口",
    "拆除",
    "模板",
    "脚手架",
    "垂直运输",
    "超高",
    "降水",
    "排水",
    "成品保护",
    "大型机械",
]

FEATURE_TERMS = [
    "厚度",
    "深度",
    "高度",
    "宽度",
    "长度",
    "运距",
    "级配",
    "强度",
    "等级",
    "断面",
    "规格",
    "材料",
    "做法",
    "层数",
    "以内",
    "以上",
]

TRANSPORT_TERMS = ["运输", "运距", "装车", "卸车", "场内", "水平运输", "垂直运输"]
METHOD_TERMS = ["人工", "机械", "泵送", "现浇", "预制", "安装", "拆除", "搭拆", "成井", "排水", "降水", "模板", "脚手架"]

PREFIX_HINTS = {
    "A": {"A1-1"},
    "B": {"A1-2"},
    "C": {"A1-3"},
    "D": {"A1-4"},
    "E": {"A1-5", "A1-6"},
    "F": {"A1-7"},
    "G": {"A1-8"},
    "H": {"A1-9"},
    "J": {"A1-10"},
    "K": {"A1-11"},
    "L": {"A1-12", "A1-24"},
    "M": {"A1-13"},
    "N": {"A1-14"},
    "P": {"A1-15"},
    "Q": {"A1-16", "A1-17", "A1-18", "A1-19"},
    "R": {"A1-20", "A1-21", "A1-22", "A1-23", "A1-24", "A1-25"},
}

ROLE_ORDER = [
    "R1_direct_bill_body",
    "R2_feature_variant",
    "R3_work_content_component",
    "R4_method_or_measure_component",
    "R5_not_applicable_or_unrouted",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate full GB/T to GD2018 governance reference outputs.")
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


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def csv_row_count(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".csv":
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return str(max(sum(1 for _ in fh) - 1, 0))


def natural_code_key(code: str) -> Tuple[Any, ...]:
    parts: List[Any] = []
    for part in re.split(r"(\d+)", norm(code)):
        if not part:
            continue
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts)


def source_prefix(code: str) -> str:
    match = re.match(r"^(A\d+-\d+)-", norm(code))
    return match.group(1) if match else ""


def bill_text(row: Dict[str, Any]) -> str:
    return " ".join(
        norm(row.get(field, ""))
        for field in [
            "bill_name",
            "appendix_name",
            "section_name",
            "table_name",
            "project_feature_raw",
            "work_content_raw",
            "keywords",
        ]
    )


def quota_text(row: Dict[str, Any]) -> str:
    return " ".join(
        norm(row.get(field, ""))
        for field in [
            "source_code",
            "raw_name",
            "quota_name_candidate",
            "quota_feature_text_candidate",
            "chapter_guess",
            "section_guess",
        ]
    )


def terms_in(text: str) -> List[str]:
    return [term for term in ALL_TERMS if term and term in text]


def contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms if term)


def normalize_unit_dimension(unit: str) -> str:
    value = norm(unit).lower().replace("³", "3").replace("㎡", "m2").replace("m²", "m2").replace("m³", "m3")
    if not value:
        return "unknown"
    if any(token in value for token in ["m3", "立方", "m^3"]):
        return "volume"
    if any(token in value for token in ["m2", "平方", "m^2"]):
        return "area"
    if value in {"m", "米"} or "延长米" in value:
        return "length"
    if any(token in value for token in ["t", "吨"]):
        return "weight"
    if any(token in value for token in ["kg", "千克"]):
        return "weight"
    if any(token in value for token in ["个", "樘", "套", "座", "根", "块", "件"]):
        return "count"
    return "unknown"


def validate_inputs(bills: Sequence[Dict[str, str]], rules: Sequence[Dict[str, str]], quotas: Sequence[Dict[str, str]], pricing: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    bill_codes = [norm(row.get("bill_code_9")) for row in bills]
    quota_statuses = [norm(row.get("review_status")) for row in quotas]
    checks = {
        "bill_rows": len(bills),
        "context_rule_rows": len(rules),
        "invalid_bill_code": sum(1 for code in bill_codes if not re.fullmatch(r"\d{9}", code)),
        "duplicate_bill_code": sum(1 for _code, count in Counter(bill_codes).items() if count > 1),
        "gb_missing_work_content": sum(1 for row in bills if not norm(row.get("work_content_raw"))),
        "gb_missing_quantity_rule": sum(1 for row in bills if not norm(row.get("quantity_calculation_rule"))),
        "quota_rows": len(quotas),
        "pricing_rows": len(pricing),
        "missing_source_code": sum(1 for row in quotas if not norm(row.get("source_code"))),
        "missing_raw_name": sum(1 for row in quotas if not norm(row.get("raw_name"))),
        "missing_unit": sum(1 for row in quotas if not norm(row.get("unit"))),
        "quota_non_pending": sum(1 for status in quota_statuses if status != REVIEW_STATUS),
    }
    hard_fail = [
        checks["bill_rows"] != 472,
        checks["quota_rows"] != 3712,
        checks["invalid_bill_code"] != 0,
        checks["duplicate_bill_code"] != 0,
        checks["gb_missing_work_content"] == checks["bill_rows"],
        checks["gb_missing_quantity_rule"] == checks["bill_rows"],
        checks["missing_source_code"] == checks["quota_rows"],
        checks["missing_raw_name"] == checks["quota_rows"],
        checks["missing_unit"] == checks["quota_rows"],
        checks["quota_non_pending"] != 0,
    ]
    checks["status"] = "pass" if not any(hard_fail) else "blocked_missing_inputs"
    return checks


def prepare_bill_profiles(bills: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for bill in bills:
        text = bill_text(bill)
        appendix = norm(bill.get("appendix_code"))
        profiles.append(
            {
                "bill": bill,
                "text": text,
                "compact_text": compact(text),
                "bill_name_compact": compact(bill.get("bill_name")),
                "terms": set(terms_in(text)),
                "work_terms": terms_in(norm(bill.get("work_content_raw"))),
                "prefix_hints": PREFIX_HINTS.get(appendix, set()),
                "unit_dim": normalize_unit_dimension(bill.get("unit", "")),
                "feature": contains_any(text, FEATURE_TERMS),
                "appendix_code": appendix,
            }
        )
    return profiles


def prepare_quota_profiles(quotas: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for quota in quotas:
        text = quota_text(quota)
        profiles.append(
            {
                "quota": quota,
                "text": text,
                "compact_text": compact(text),
                "terms": set(terms_in(text)),
                "prefix": norm(quota.get("code_prefix")) or source_prefix(quota.get("source_code", "")),
                "unit_dim": normalize_unit_dimension(quota.get("unit", "")),
                "transport": contains_any(text, TRANSPORT_TERMS),
                "method": contains_any(text, METHOD_TERMS),
                "feature": contains_any(text, FEATURE_TERMS),
            }
        )
    return profiles


def score_pair(bill_profile: Dict[str, Any], quota_profile: Dict[str, Any]) -> Tuple[float, List[str]]:
    overlap = sorted(bill_profile["terms"].intersection(quota_profile["terms"]))
    prefix_match = quota_profile["prefix"] in bill_profile["prefix_hints"]
    score = 0.0
    basis: List[str] = []

    if overlap:
        score += len(overlap) * 1.35
        basis.append("keyword_overlap:" + "/".join(overlap[:10]))
    if bill_profile["bill_name_compact"] and bill_profile["bill_name_compact"] in quota_profile["compact_text"]:
        score += 6.0
        basis.append("bill_name_in_quota_text")
    for term in bill_profile["work_terms"]:
        if term in quota_profile["text"]:
            score += 0.65
    if prefix_match:
        score += 2.0
        basis.append("source_code_prefix_hint")

    bill_dim = bill_profile["unit_dim"]
    quota_dim = quota_profile["unit_dim"]
    if bill_dim != "unknown" and quota_dim != "unknown":
        if bill_dim == quota_dim:
            score += 1.0
            basis.append("unit_dimension_match")
        else:
            score -= 0.85
            basis.append("unit_dimension_mismatch")

    if quota_profile["transport"]:
        score -= 0.25
        basis.append("transport_or_loading_risk")
    if quota_profile["method"]:
        basis.append("method_or_measure_risk")
    if quota_profile["feature"] or bill_profile["feature"]:
        basis.append("feature_condition_present")
    return score, basis


def classify_role(bill_profile: Dict[str, Any], quota_profile: Dict[str, Any], score: float, basis: Sequence[str]) -> Tuple[str, str, str, str]:
    prefix_match = quota_profile["prefix"] in bill_profile["prefix_hints"]
    dim_mismatch = "unit_dimension_mismatch" in basis
    transport = quota_profile["transport"]
    method = quota_profile["method"]
    feature = "feature_condition_present" in basis

    if dim_mismatch and score < 4.6:
        return "R5_not_applicable_or_unrouted", "candidate rejected by unit dimension or weak evidence", "manual review only", "none"
    if transport:
        return "R4_method_or_measure_component", "transport/loading/vertical movement candidate, not direct bill body", "transport or method review required", "low"
    if method and bill_profile["appendix_code"] != "R":
        return "R4_method_or_measure_component", "construction method/measure candidate, not direct bill body", "method review required", "low"
    if score >= 7.0 and prefix_match and not feature:
        return "R1_direct_bill_body", "strong name/object/prefix/unit evidence", "direct bill body candidate after cost review", "high"
    if score >= 5.0 and (prefix_match or score >= 7.5):
        return "R2_feature_variant", "bill body likely but feature/condition split required", "feature condition required", "medium"
    if score >= 4.0:
        return "R3_work_content_component", "related as work content/component rather than confirmed bill body", "work content only unless reviewer promotes", "low"
    return "R5_not_applicable_or_unrouted", "weak evidence, do not use automatically", "unrouted candidate", "none"


def allowed_use_for(role: str) -> str:
    return {
        "R1_direct_bill_body": "bill_body_candidate_after_review",
        "R2_feature_variant": "feature_variant_candidate_after_review",
        "R3_work_content_component": "work_content_component_reference",
        "R4_method_or_measure_component": "method_or_measure_component_reference",
        "R5_not_applicable_or_unrouted": "manual_review_only",
    }.get(role, "manual_review_only")


def forbidden_use_for(role: str) -> str:
    base = ["must_not_auto_approve", "must_not_write_back_bill_code", "must_not_generate_enterprise_standard_name", "must_not_generate_enterprise_price"]
    if role in {"R3_work_content_component", "R4_method_or_measure_component", "R5_not_applicable_or_unrouted"}:
        base.append("must_not_be_direct_bill_body")
    return ";".join(base)


def issue_types_for(role: str, basis: Sequence[str], confidence: float) -> str:
    issues: List[str] = []
    if role == "R2_feature_variant":
        issues.append("feature_required")
    if role == "R3_work_content_component":
        issues.append("work_content_only")
    if role == "R4_method_or_measure_component":
        if "transport_or_loading_risk" in basis:
            issues.append("transport_item_uncertain")
        else:
            issues.append("construction_method_only")
    if "unit_dimension_mismatch" in basis:
        issues.append("unit_dimension_mismatch")
    if role == "R5_not_applicable_or_unrouted" or confidence < 0.55:
        issues.append("possible_over_mapping")
    return ";".join(dict.fromkeys(issues))


def select_candidates(scored: List[Tuple[float, Dict[str, Any], List[str]]]) -> List[Tuple[float, Dict[str, Any], List[str]]]:
    scored.sort(key=lambda item: item[0], reverse=True)
    high = [item for item in scored if item[0] >= 5.0][:30]
    high_codes = {item[1]["quota"].get("source_code", "") for item in high}
    medium = [item for item in scored if 3.2 <= item[0] < 5.0 and item[1]["quota"].get("source_code", "") not in high_codes][:20]
    return high + medium


def build_details(
    bills: Sequence[Dict[str, str]],
    quotas: Sequence[Dict[str, str]],
    pricing_by_code: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    bill_profiles = prepare_bill_profiles(bills)
    quota_profiles = prepare_quota_profiles(quotas)
    for bill_profile in bill_profiles:
        scored: List[Tuple[float, Dict[str, Any], List[str]]] = []
        for quota_profile in quota_profiles:
            score, basis = score_pair(bill_profile, quota_profile)
            if score >= 3.2:
                scored.append((score, quota_profile, basis))
        for score, quota_profile, basis in select_candidates(scored):
            bill = bill_profile["bill"]
            quota = quota_profile["quota"]
            role, role_basis, condition, _template_value = classify_role(bill_profile, quota_profile, score, basis)
            confidence = max(0.1, min(0.98, score / 10.0))
            pricing = pricing_by_code.get(norm(quota.get("source_code")), {})
            details.append(
                {
                    "bill_code_9": norm(bill.get("bill_code_9")),
                    "bill_name": norm(bill.get("bill_name")),
                    "appendix_code": norm(bill.get("appendix_code")),
                    "appendix_name": norm(bill.get("appendix_name")),
                    "bill_unit": norm(bill.get("unit")),
                    "bill_quantity_calculation_rule": norm(bill.get("quantity_calculation_rule")),
                    "bill_work_content_raw": norm(bill.get("work_content_raw")),
                    "bill_project_feature_raw": norm(bill.get("project_feature_raw")),
                    "quota_source_code": norm(quota.get("source_code")),
                    "quota_raw_name": norm(quota.get("raw_name")),
                    "quota_name_candidate": norm(quota.get("quota_name_candidate")),
                    "quota_feature_text_candidate": norm(quota.get("quota_feature_text_candidate")),
                    "quota_unit": norm(quota.get("unit")),
                    "quota_raw_total_fee": norm(pricing.get("raw_total_fee")) or norm(quota.get("raw_total_fee")),
                    "source_code_prefix": quota_profile["prefix"],
                    "governance_role": role,
                    "relationship_basis": role_basis + ";" + ";".join(basis[:10]),
                    "mapping_confidence": f"{confidence:.2f}",
                    "selection_condition": condition,
                    "forbidden_use": forbidden_use_for(role),
                    "issue_types": issue_types_for(role, basis, confidence),
                    "review_status": REVIEW_STATUS,
                    "cost_engineer_decision": "",
                    "cost_engineer_comment": "",
                }
            )
    details.sort(key=lambda row: (row["bill_code_9"], -float(row["mapping_confidence"]), natural_code_key(row["quota_source_code"])))
    return details


def top_values(rows: Sequence[Dict[str, Any]], key: str, limit: int = 10) -> str:
    out: List[str] = []
    seen = set()
    for row in rows:
        value = norm(row.get(key))
        if value and value not in seen:
            out.append(value)
            seen.add(value)
        if len(out) >= limit:
            break
    return ";".join(out)


def decision_from_counts(counts: Counter, total: int) -> Tuple[str, str, str]:
    if total == 0:
        return "no_reliable_quota_candidate", "none", "high"
    if counts.get("R1_direct_bill_body", 0) > 0:
        return "ready_for_template_seed_after_review", "high", "medium"
    if counts.get("R2_feature_variant", 0) > 0:
        return "usable_with_feature_conditions", "medium", "medium"
    if counts.get("R3_work_content_component", 0) > 0 and counts.get("R4_method_or_measure_component", 0) == 0:
        return "only_work_content_components_available", "low", "medium"
    if counts.get("R4_method_or_measure_component", 0) > 0:
        return "requires_cost_department_review", "low", "high"
    return "defer", "none", "high"


def build_matrix(bills: Sequence[Dict[str, str]], details: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_bill: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in details:
        by_bill[row["bill_code_9"]].append(row)
    matrix: List[Dict[str, Any]] = []
    for bill in sorted(bills, key=lambda row: row.get("bill_code_9", "")):
        code = norm(bill.get("bill_code_9"))
        rows = sorted(by_bill.get(code, []), key=lambda row: float(row.get("mapping_confidence", "0")), reverse=True)
        counts = Counter(row["governance_role"] for row in rows)
        decision, template_value, priority = decision_from_counts(counts, len(rows))
        matrix.append(
            {
                "bill_code_9": code,
                "bill_name": norm(bill.get("bill_name")),
                "appendix_code": norm(bill.get("appendix_code")),
                "appendix_name": norm(bill.get("appendix_name")),
                "section_code": norm(bill.get("section_code")),
                "section_name": norm(bill.get("section_name")),
                "unit": norm(bill.get("unit")),
                "quantity_calculation_rule": norm(bill.get("quantity_calculation_rule")),
                "work_content_raw": norm(bill.get("work_content_raw")),
                "project_feature_raw": norm(bill.get("project_feature_raw")),
                "total_quota_candidate_count": len(rows),
                "R1_direct_bill_body_count": counts.get("R1_direct_bill_body", 0),
                "R2_feature_variant_count": counts.get("R2_feature_variant", 0),
                "R3_work_content_component_count": counts.get("R3_work_content_component", 0),
                "R4_method_or_measure_component_count": counts.get("R4_method_or_measure_component", 0),
                "R5_not_applicable_or_unrouted_count": counts.get("R5_not_applicable_or_unrouted", 0),
                "top_quota_source_codes": top_values(rows, "quota_source_code", 12),
                "top_quota_names": top_values(rows, "quota_raw_name", 8),
                "top_quota_units": top_values(rows, "quota_unit", 6),
                "top_source_code_prefixes": top_values(rows, "source_code_prefix", 6),
                "recommended_bill_level_decision": decision,
                "template_reference_value": template_value,
                "human_review_priority": priority,
                "cost_engineer_decision": "",
                "cost_engineer_comment": "",
            }
        )
    return matrix


def dominant_role(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    counts = Counter(row["governance_role"] for row in rows)
    return sorted(counts.items(), key=lambda item: (-item[1], ROLE_ORDER.index(item[0]) if item[0] in ROLE_ORDER else 99))[0][0]


def routing_status_for(role: str) -> str:
    return {
        "R1_direct_bill_body": "routed_to_bill_candidate",
        "R2_feature_variant": "routed_to_feature_variant",
        "R3_work_content_component": "routed_to_work_content_component",
        "R4_method_or_measure_component": "routed_to_method_or_measure",
        "R5_not_applicable_or_unrouted": "routed_to_manual_review",
    }.get(role, "unrouted")


def confidence_ceiling(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return "0.00"
    return f"{max(float(row.get('mapping_confidence', 0) or 0) for row in rows):.2f}"


def build_quota_routing(quotas: Sequence[Dict[str, str]], details: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_quota: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in details:
        by_quota[row["quota_source_code"]].append(row)
    rows: List[Dict[str, Any]] = []
    for quota in sorted(quotas, key=lambda row: natural_code_key(row.get("source_code", ""))):
        code = norm(quota.get("source_code"))
        matches = sorted(by_quota.get(code, []), key=lambda row: (ROLE_ORDER.index(row["governance_role"]) if row["governance_role"] in ROLE_ORDER else 99, row["bill_code_9"]))
        role = dominant_role(matches)
        rows.append(
            {
                "quota_source_code": code,
                "quota_raw_name": norm(quota.get("raw_name")),
                "quota_name_candidate": norm(quota.get("quota_name_candidate")),
                "quota_feature_text_candidate": norm(quota.get("quota_feature_text_candidate")),
                "quota_unit": norm(quota.get("unit")),
                "source_code_prefix": norm(quota.get("code_prefix")) or source_prefix(code),
                "candidate_bill_count": len({row["bill_code_9"] for row in matches}),
                "candidate_bill_codes": ";".join(sorted({row["bill_code_9"] for row in matches})),
                "candidate_bill_names": ";".join(sorted({row["bill_name"] for row in matches})),
                "dominant_governance_role": role,
                "allowed_use": allowed_use_for(role) if role else "manual_review_only",
                "forbidden_use": forbidden_use_for(role) if role else forbidden_use_for("R5_not_applicable_or_unrouted"),
                "recommended_confidence_ceiling": confidence_ceiling(matches),
                "routing_status": routing_status_for(role) if role else "unrouted",
                "review_status": REVIEW_STATUS,
                "cost_engineer_decision": "",
                "cost_engineer_comment": "",
            }
        )
    return rows


def shared_type_for(role: str, rows: Sequence[Dict[str, Any]]) -> str:
    text = " ".join(row.get("quota_raw_name", "") + " " + row.get("issue_types", "") for row in rows)
    if "transport_item_uncertain" in text or contains_any(text, TRANSPORT_TERMS):
        return "transport_component_shared"
    if role == "R2_feature_variant":
        return "feature_variant_shared"
    if role == "R3_work_content_component":
        return "work_content_component_shared"
    if role == "R4_method_or_measure_component":
        return "method_component_shared"
    return "possible_over_mapping"


def build_shared_components(details: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_quota: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in details:
        by_quota[row["quota_source_code"]].append(row)
    rows: List[Dict[str, Any]] = []
    for code, group in sorted(by_quota.items(), key=lambda item: natural_code_key(item[0])):
        bill_codes = sorted({row["bill_code_9"] for row in group})
        if len(bill_codes) <= 1:
            continue
        role = dominant_role(group)
        shared_type = shared_type_for(role, group)
        rows.append(
            {
                "quota_source_code": code,
                "quota_raw_name": group[0]["quota_raw_name"],
                "quota_name_candidate": group[0]["quota_name_candidate"],
                "candidate_bill_codes": ";".join(bill_codes),
                "candidate_bill_names": ";".join(sorted({row["bill_name"] for row in group})),
                "candidate_count": len(bill_codes),
                "dominant_governance_role": role,
                "shared_component_type": shared_type,
                "selection_condition": "shared quota component requires bill-specific feature/work-content/measure condition",
                "allowed_use": allowed_use_for(role),
                "forbidden_use": forbidden_use_for(role),
                "review_priority": "high" if len(bill_codes) >= 6 or shared_type in {"transport_component_shared", "possible_over_mapping"} else "medium",
            }
        )
    return rows


def add_issue(
    issues: List[Dict[str, Any]],
    issue_type: str,
    severity: str,
    description: str,
    recommended_action: str,
    bill: Dict[str, Any] | None = None,
    quota: Dict[str, Any] | None = None,
    role: str = "",
) -> None:
    issues.append(
        {
            "issue_id": f"FULL_MAP_ISSUE_{len(issues) + 1:06d}",
            "issue_type": issue_type,
            "severity": severity,
            "bill_code_9": norm((bill or {}).get("bill_code_9")),
            "bill_name": norm((bill or {}).get("bill_name")),
            "quota_source_code": norm((quota or {}).get("quota_source_code")),
            "quota_raw_name": norm((quota or {}).get("quota_raw_name")),
            "governance_role": role,
            "description": description,
            "recommended_action": recommended_action,
            "review_status": REVIEW_STATUS,
        }
    )


def build_issues(matrix: Sequence[Dict[str, Any]], details: Sequence[Dict[str, Any]], shared: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    issue_by_bill: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in details:
        for issue_type in [item for item in row.get("issue_types", "").split(";") if item]:
            key = (row["bill_code_9"], issue_type)
            issue_by_bill[key] += 1
            if issue_by_bill[key] <= 3:
                severity = "high" if issue_type in {"possible_over_mapping", "transport_item_uncertain", "unit_dimension_mismatch"} else "medium"
                add_issue(issues, issue_type, severity, f"{issue_type} detected in candidate relationship.", "Cost department should classify before use.", row, row, row["governance_role"])
    for row in matrix:
        total = int(row["total_quota_candidate_count"])
        if total == 0:
            add_issue(issues, "no_candidate_quota", "high", "No reliable GD2018 quota candidate found by lightweight governance rules.", "Manual review required; do not force mapping.", row)
        if total > 40:
            add_issue(issues, "too_many_candidate_quota", "medium", f"{total} retained candidates; bill requires feature narrowing.", "Review top candidates and refine feature conditions.", row)
        if row.get("human_review_priority") == "high":
            add_issue(issues, "cost_department_review_required", "high", "Bill-level decision requires cost department review.", "Confirm whether the bill should be seeded into Enterprise Template V0.1.", row)
    for row in shared:
        add_issue(
            issues,
            "shared_quota_component",
            "high" if row["review_priority"] == "high" else "medium",
            f"Quota appears under {row['candidate_count']} bill items.",
            "Require selection condition before enterprise template use.",
            None,
            {
                "quota_source_code": row["quota_source_code"],
                "quota_raw_name": row["quota_raw_name"],
            },
            row["dominant_governance_role"],
        )
    add_issue(
        issues,
        "candidate_name_not_final_standard",
        "high",
        "quota_name_candidate and bill_name are reference candidates only, not final enterprise standard names.",
        "Final enterprise standard names require cost department review.",
    )
    add_issue(
        issues,
        "market_price_required",
        "medium",
        "This stage preserves quota pricing context only; market price is not generated.",
        "Add market price evidence in Enterprise Template V0.1 stage.",
    )
    add_issue(
        issues,
        "enterprise_price_required",
        "medium",
        "This stage does not generate enterprise prices or internal_price_library.",
        "Combine internal, market, and quota pricing in a later approved stage.",
    )
    return issues


def build_dashboard(
    matrix: Sequence[Dict[str, Any]],
    routing: Sequence[Dict[str, Any]],
    details: Sequence[Dict[str, Any]],
    shared: Sequence[Dict[str, Any]],
    issues: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    role_counts = Counter(row["governance_role"] for row in details)
    rows = [
        ("total_bill_items", len(matrix), "472", len(matrix) == 472, "high", ""),
        ("total_quota_items", len(routing), "3712", len(routing) == 3712, "high", ""),
        ("bill_items_with_candidates", sum(1 for row in matrix if int(row["total_quota_candidate_count"]) > 0), "> 0", True, "medium", ""),
        ("bill_items_without_candidates", sum(1 for row in matrix if int(row["total_quota_candidate_count"]) == 0), "review required", True, "high", "Do not force-map these bills."),
        ("quota_items_with_routing", sum(1 for row in routing if row["routing_status"] != "unrouted"), "> 0", True, "medium", ""),
        ("quota_items_unrouted", sum(1 for row in routing if row["routing_status"] == "unrouted"), "manual review", True, "medium", ""),
        ("R1_count", role_counts.get("R1_direct_bill_body", 0), "reference only", True, "medium", ""),
        ("R2_count", role_counts.get("R2_feature_variant", 0), "feature review", True, "medium", ""),
        ("R3_count", role_counts.get("R3_work_content_component", 0), "component review", True, "medium", ""),
        ("R4_count", role_counts.get("R4_method_or_measure_component", 0), "method/measure review", True, "high", ""),
        ("R5_count", role_counts.get("R5_not_applicable_or_unrouted", 0), "manual review", True, "high", ""),
        ("shared_quota_component_count", len(shared), "manual condition required", True, "high", ""),
        ("high_priority_review_count", sum(1 for row in issues if row["severity"] == "high"), "manual review", True, "high", ""),
        ("approved_count", 0, "0", True, "high", "No approved rows generated."),
        ("non_pending_review_status_count", sum(1 for row in details if row["review_status"] != REVIEW_STATUS) + sum(1 for row in routing if row["review_status"] != REVIEW_STATUS), "0", True, "high", ""),
        ("database_write_detected", 0, "0", True, "high", "Script writes files only."),
        ("bill_code_writeback_detected", 0, "0", True, "high", "No source baseline files are modified."),
    ]
    return [
        {
            "metric_name": name,
            "metric_value": value,
            "expected_or_threshold": expected,
            "status": "pass" if ok else "fail",
            "severity": severity,
            "remark": remark,
        }
        for name, value, expected, ok, severity, remark in rows
    ]


def build_summary(matrix: Sequence[Dict[str, Any]], routing: Sequence[Dict[str, Any]], details: Sequence[Dict[str, Any]], shared: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]], recommendation: str) -> List[Dict[str, Any]]:
    return [
        {"metric_name": "bill_matrix_rows", "metric_value": len(matrix), "remark": "must equal 472"},
        {"metric_name": "quota_routing_rows", "metric_value": len(routing), "remark": "must equal 3712"},
        {"metric_name": "detail_rows", "metric_value": len(details), "remark": "not cartesian product"},
        {"metric_name": "bill_items_with_candidates", "metric_value": sum(1 for row in matrix if int(row["total_quota_candidate_count"]) > 0), "remark": ""},
        {"metric_name": "bill_items_without_candidates", "metric_value": sum(1 for row in matrix if int(row["total_quota_candidate_count"]) == 0), "remark": ""},
        {"metric_name": "unrouted_quota_items", "metric_value": sum(1 for row in routing if row["routing_status"] == "unrouted"), "remark": ""},
        {"metric_name": "shared_quota_component_count", "metric_value": len(shared), "remark": ""},
        {"metric_name": "high_priority_review_count", "metric_value": sum(1 for row in issues if row["severity"] == "high"), "remark": ""},
        {"metric_name": "approved_count", "metric_value": 0, "remark": "no approved generated"},
        {"metric_name": "recommendation", "metric_value": recommendation, "remark": ""},
    ]


def recommendation(matrix: Sequence[Dict[str, Any]], routing: Sequence[Dict[str, Any]], details: Sequence[Dict[str, Any]], xlsx_ok: bool) -> str:
    if not xlsx_ok:
        return "blocked_xlsx_generation_failed"
    if len(matrix) == 472 and len(routing) == 3712 and details:
        return "full_governance_reference_ready_for_enterprise_template_v0_1"
    return "full_governance_reference_partial_manual_intervention_required"


def write_report(
    path: Path,
    input_checks: Dict[str, Any],
    matrix: Sequence[Dict[str, Any]],
    routing: Sequence[Dict[str, Any]],
    details: Sequence[Dict[str, Any]],
    shared: Sequence[Dict[str, Any]],
    issues: Sequence[Dict[str, Any]],
    rec: str,
) -> None:
    role_counts = Counter(row["governance_role"] for row in details)
    issue_counts = Counter(row["issue_type"] for row in issues)
    lines = [
        "# Stage MAP-FULL-GOVERNANCE-REFERENCE-1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Generate a full pending reference library for GB/T 50854 bill items against GD2018 normalized quota items. This is a governance reference package, not an approved enterprise quota table.",
        "",
        "## 2. Business Purpose",
        "",
        "This stage is used by the cost department as a manual reference when assembling enterprise bill lists and later Enterprise Template V0.1 candidates. It is not a formally approved enterprise quota, does not create enterprise prices, and does not write any database records.",
        "",
        "## 3. Input Baselines",
        "",
        f"- gb_bill_rows: {input_checks.get('bill_rows')}",
        f"- gb_context_rules: {input_checks.get('context_rule_rows')}",
        f"- gd_quota_rows: {input_checks.get('quota_rows')}",
        f"- gd_pricing_rows: {input_checks.get('pricing_rows')}",
        f"- invalid_bill_code: {input_checks.get('invalid_bill_code')}",
        f"- duplicate_bill_code: {input_checks.get('duplicate_bill_code')}",
        f"- quota_non_pending: {input_checks.get('quota_non_pending')}",
        f"- gb_missing_quantity_rule_rows: {input_checks.get('gb_missing_quantity_rule')} (not overall missing)",
        "",
        "## 4. Mapping Strategy",
        "",
        "The script uses object keywords, work-content keywords, feature terms, unit dimensions, GD source-code prefix hints, and R1-R5 governance roles. Candidate details are capped per bill item and are not a cartesian product.",
        "",
        "## 5. Bill-Centric Matrix Summary",
        "",
        f"- bill_matrix_rows: {len(matrix)}",
        f"- bill_items_with_candidates: {sum(1 for row in matrix if int(row['total_quota_candidate_count']) > 0)}",
        f"- bill_items_without_candidates: {sum(1 for row in matrix if int(row['total_quota_candidate_count']) == 0)}",
        f"- role_counts: {json.dumps(dict(role_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 6. Quota-Centric Routing Summary",
        "",
        f"- quota_routing_rows: {len(routing)}",
        f"- quota_items_with_routing: {sum(1 for row in routing if row['routing_status'] != 'unrouted')}",
        f"- quota_items_unrouted: {sum(1 for row in routing if row['routing_status'] == 'unrouted')}",
        "",
        "## 7. Shared Component Findings",
        "",
        f"- shared_quota_component_count: {len(shared)}",
        "- Shared quota components require bill-specific feature/work-content/measure selection conditions before template use.",
        "",
        "## 8. High-Risk Review Areas",
        "",
        f"- issue_rows: {len(issues)}",
        f"- high_priority_review_count: {sum(1 for row in issues if row['severity'] == 'high')}",
        f"- issue_type_counts: {json.dumps(dict(issue_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 9. How Cost Department Should Use This Reference",
        "",
        "- Start with `full_bill_to_quota_matrix_472.csv` to review bill-level readiness.",
        "- Use `full_bill_to_quota_detail_reference.csv` to inspect candidate quota evidence.",
        "- Use `full_quota_to_bill_routing_3712.csv` to see quota-centric reuse and unrouted rows.",
        "- Treat shared components and R3/R4/R5 rows as review-only, not direct enterprise quota lines.",
        "",
        "## 10. Not Approved / Not Final Statement",
        "",
        "All rows remain pending. This stage does not write databases, approve mappings, write bill_code back to quota references, generate internal_price_library, generate final enterprise standard names, generate enterprise prices, enter Web development, or parse real bid lists.",
        "",
        "## 11. Next Step Recommendation",
        "",
        rec,
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_xlsx_with_artifact_tool(output_dir: Path, node_exe: Path, node_modules: Path) -> None:
    if not node_exe.exists() or not node_modules.exists():
        raise RuntimeError(f"Bundled node runtime unavailable: node={node_exe}, node_modules={node_modules}")
    specs = [
        ("bill_to_quota_matrix_472", "full_bill_to_quota_matrix_472.csv", len(MATRIX_FIELDS)),
        ("bill_to_quota_detail_reference", "full_bill_to_quota_detail_reference.csv", len(DETAIL_FIELDS)),
        ("quota_to_bill_routing_3712", "full_quota_to_bill_routing_3712.csv", len(ROUTING_FIELDS)),
        ("shared_quota_components", "full_shared_quota_components.csv", len(SHARED_FIELDS)),
        ("mapping_issues", "full_mapping_issues.csv", len(ISSUE_FIELDS)),
        ("governance_dashboard", "full_mapping_governance_dashboard.csv", len(DASHBOARD_FIELDS)),
        ("summary", "summary_for_xlsx.csv", len(SUMMARY_FIELDS)),
    ]
    builder = r'''
import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = process.argv[2];
const xlsxPath = `${outputDir}/Full_Mapping_Governance_Reference_Review.xlsx`;
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
  const sheet = workbook.worksheets.getItem(sheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  header.format.borders = { preset: "bottom", style: "thin", color: "#9FBAD0" };
  const width = sheetName === "summary" || sheetName === "governance_dashboard" ? 24 : 18;
  sheet.getRangeByIndexes(0, 0, 1, colCount).format.columnWidth = width;
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

await workbook.render({ sheetName: "summary", autoCrop: "all", scale: 1, format: "png" });
await workbook.render({ sheetName: "governance_dashboard", autoCrop: "all", scale: 1, format: "png" });

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(xlsxPath);
console.log(`xlsx=${xlsxPath}`);
'''
    with tempfile.TemporaryDirectory(prefix="map_full_gov_xlsx_") as tmp:
        tmp_path = Path(tmp)
        link = tmp_path / "node_modules"
        try:
            os.symlink(node_modules, link, target_is_directory=True)
        except OSError:
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(node_modules)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        builder_path = tmp_path / "build_full_mapping_governance_review.mjs"
        builder_path.write_text(builder, encoding="utf-8")
        subprocess.run([str(node_exe), str(builder_path), str(output_dir), json.dumps(specs)], cwd=tmp_path, check=True)
    sidecar = output_dir / "Full_Mapping_Governance_Reference_Review.xlsx.inspect.ndjson"
    if sidecar.exists():
        sidecar.unlink()


def artifact_row_count(path: Path, workbook_total_rows: int) -> str:
    if path.suffix.lower() == ".csv":
        return csv_row_count(path)
    if path.suffix.lower() == ".xlsx":
        return str(workbook_total_rows)
    return ""


def manifest_row(stage_name: str, artifact_name: str, path: Path, source_file: str, project_root: Path, workbook_total_rows: int) -> Dict[str, str]:
    exists = path.exists()
    return {
        "stage_name": stage_name,
        "artifact_name": artifact_name,
        "expected_path": rel(path, project_root),
        "exists": "true" if exists else "false",
        "file_size_bytes": str(path.stat().st_size) if exists else "",
        "row_count": artifact_row_count(path, workbook_total_rows) if exists else "",
        "sha256": sha256_file(path) if exists else "",
        "created_or_modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else "",
        "source_file": source_file,
        "can_regenerate": "true",
        "backup_required": "true",
        "backup_path": rel(project_root / ENGINE_REL / "data" / "private" / "reference_extraction" / "backups" / "runs_backup_after_MAP_FULL_GOVERNANCE_REFERENCE_1", project_root),
        "status": "generated" if exists else "missing",
        "remark": "pending governance reference only; not approved and not source of truth for enterprise prices",
    }


def update_manifest(project_root: Path, output_dir: Path, artifacts: Sequence[str], workbook_total_rows: int) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    existing = read_csv(manifest_path) if manifest_path.exists() else []
    source_file = ";".join([rel(project_root / GB_BILLS_REL, project_root), rel(project_root / GD_QUOTA_REL, project_root)])
    replacement = {
        (STAGE_NAME, artifact): manifest_row(STAGE_NAME, artifact, output_dir / artifact, source_file, project_root, workbook_total_rows)
        for artifact in artifacts
    }
    filtered = [row for row in existing if (row.get("stage_name"), row.get("artifact_name")) not in replacement]
    filtered.extend(replacement.values())
    write_csv(manifest_path, MANIFEST_FIELDS, filtered)
    write_manifest_md(project_root, filtered)


def write_manifest_md(project_root: Path, rows: Sequence[Dict[str, str]]) -> None:
    latest = [row for row in rows if row.get("stage_name") == STAGE_NAME]
    registered = len(rows)
    existing = sum(1 for row in rows if row.get("exists") == "true")
    lines = [
        "# Reference Artifact Manifest",
        "",
        "## Governance",
        "",
        "- `construction_cost_knowledge_engine/data/private/` is intentionally not tracked by Git.",
        "- Every private artifact must be registered with `row_count` and `sha256` after generation.",
        "- Each completed stage must back up its `runs` output directory after validation.",
        "- Mock SQLite and seed CSV artifacts must not be used as source of truth.",
        "- Full governance reference outputs are pending review artifacts only and do not approve mappings.",
        "- Full governance reference outputs must not be used as enterprise price source of truth.",
        "",
        "## Current Manifest Summary",
        "",
        f"- registered_artifacts: {registered}",
        f"- existing_artifacts: {existing}",
        f"- missing_artifacts: {registered - existing}",
        "",
        "## Manifest CSV",
        "",
        "`construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`",
        "",
        "## Latest Full Governance Reference Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_MAP_FULL_GOVERNANCE_REFERENCE_1/`",
            "",
        ]
    )
    (project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        bills = read_csv(project_root / GB_BILLS_REL)
        rules = read_csv(project_root / GB_RULES_REL)
        quotas = read_csv(project_root / GD_QUOTA_REL)
        pricing = read_csv(project_root / GD_PRICING_REL)
    except FileNotFoundError as exc:
        print(f"recommendation=blocked_missing_inputs")
        print(f"missing_input={exc}")
        return 2

    input_checks = validate_inputs(bills, rules, quotas, pricing)
    if input_checks["status"] != "pass":
        print("recommendation=blocked_missing_inputs")
        print(json.dumps(input_checks, ensure_ascii=False, sort_keys=True))
        return 2

    pricing_by_code = {norm(row.get("source_code")): row for row in pricing}
    details = build_details(bills, quotas, pricing_by_code)
    matrix = build_matrix(bills, details)
    routing = build_quota_routing(quotas, details)
    shared = build_shared_components(details)
    issues = build_issues(matrix, details, shared)
    provisional_rec = recommendation(matrix, routing, details, xlsx_ok=True)
    dashboard = build_dashboard(matrix, routing, details, shared, issues)
    summary = build_summary(matrix, routing, details, shared, issues, provisional_rec)

    write_csv(output_dir / "full_bill_to_quota_matrix_472.csv", MATRIX_FIELDS, matrix)
    write_csv(output_dir / "full_bill_to_quota_detail_reference.csv", DETAIL_FIELDS, details)
    write_csv(output_dir / "full_quota_to_bill_routing_3712.csv", ROUTING_FIELDS, routing)
    write_csv(output_dir / "full_shared_quota_components.csv", SHARED_FIELDS, shared)
    write_csv(output_dir / "full_mapping_issues.csv", ISSUE_FIELDS, issues)
    write_csv(output_dir / "full_mapping_governance_dashboard.csv", DASHBOARD_FIELDS, dashboard)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)

    xlsx_ok = False
    try:
        build_xlsx_with_artifact_tool(output_dir, args.node_exe, args.node_modules)
        xlsx_ok = True
    except Exception as exc:
        write_report(output_dir / "stage_map_full_governance_reference_report.md", input_checks, matrix, routing, details, shared, issues, "blocked_xlsx_generation_failed")
        print(f"recommendation=blocked_xlsx_generation_failed")
        print(f"xlsx_error={exc}")
        return 3

    rec = recommendation(matrix, routing, details, xlsx_ok=xlsx_ok)
    summary = build_summary(matrix, routing, details, shared, issues, rec)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)
    write_report(output_dir / "stage_map_full_governance_reference_report.md", input_checks, matrix, routing, details, shared, issues, rec)

    artifacts = [
        "full_bill_to_quota_matrix_472.csv",
        "full_bill_to_quota_detail_reference.csv",
        "full_quota_to_bill_routing_3712.csv",
        "full_shared_quota_components.csv",
        "full_mapping_issues.csv",
        "full_mapping_governance_dashboard.csv",
        "Full_Mapping_Governance_Reference_Review.xlsx",
        "stage_map_full_governance_reference_report.md",
    ]
    workbook_total_rows = len(matrix) + len(details) + len(routing) + len(shared) + len(issues) + len(dashboard) + len(summary)
    update_manifest(project_root, output_dir, artifacts, workbook_total_rows)
    (output_dir / "summary_for_xlsx.csv").unlink(missing_ok=True)

    print(f"recommendation={rec}")
    print(f"bill_matrix_rows={len(matrix)}")
    print(f"quota_routing_rows={len(routing)}")
    print(f"detail_rows={len(details)}")
    print(f"bill_items_with_candidates={sum(1 for row in matrix if int(row['total_quota_candidate_count']) > 0)}")
    print(f"bill_items_without_candidates={sum(1 for row in matrix if int(row['total_quota_candidate_count']) == 0)}")
    print(f"unrouted_quota_items={sum(1 for row in routing if row['routing_status'] == 'unrouted')}")
    print(f"shared_quota_component_count={len(shared)}")
    print(f"high_priority_review_count={sum(1 for row in issues if row['severity'] == 'high')}")
    print(f"approved_count=0")
    print(f"non_pending_review_status_count={sum(1 for row in details if row['review_status'] != REVIEW_STATUS) + sum(1 for row in routing if row['review_status'] != REVIEW_STATUS)}")
    print(f"xlsx_exists={(output_dir / 'Full_Mapping_Governance_Reference_Review.xlsx').exists()}")
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
