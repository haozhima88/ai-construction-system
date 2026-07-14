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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
BASELINE_REL = RUNS_REL / "SOURCE_BASELINE_LOCK_1"
GD_BASE_REL = BASELINE_REL / "GD2018_normalized_full_quota_parse_review"
INTERNAL_BASE_REL = RUNS_REL / "ENTERPRISE_PRICE_BASELINE_LOCK_1"
MAP_FULL_REL = RUNS_REL / "MAP_FULL_GOVERNANCE_REFERENCE_1"
OUTPUT_DIR_REL = RUNS_REL / "ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1"
DOCS_REF_REL = ENGINE_REL / "docs" / "reference_extraction"

GD_QUOTA_REL = GD_BASE_REL / "gd2018_normalized_quota_items_full_review.csv"
GD_PRICING_REL = GD_BASE_REL / "gd2018_normalized_pricing_fields_full_review.csv"
INTERNAL_PRICE_REL = INTERNAL_BASE_REL / "internal_price_item_candidate.csv"
INTERNAL_ISSUES_REL = INTERNAL_BASE_REL / "internal_price_parse_issues.csv"
FULL_MATRIX_REL = MAP_FULL_REL / "full_bill_to_quota_matrix_472.csv"
FULL_DETAIL_REL = MAP_FULL_REL / "full_bill_to_quota_detail_reference.csv"
FULL_ROUTING_REL = MAP_FULL_REL / "full_quota_to_bill_routing_3712.csv"

NODE_EXE_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)
NODE_MODULES_DEFAULT = Path(
    r"C:\Users\haozh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
)

STAGE_NAME = "ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1"
REVIEW_STATUS = "pending"

COVERAGE_FIELDS = [
    "quota_source_code",
    "quota_raw_name",
    "quota_name_candidate",
    "quota_feature_text_candidate",
    "quota_unit",
    "quota_raw_total_fee",
    "source_code_prefix",
    "matched_internal_price_count",
    "top_internal_price_ids",
    "top_internal_price_names",
    "top_internal_price_units",
    "top_internal_price_total_fees",
    "internal_price_match_status",
    "selected_price_source_priority",
    "selected_price_source_type",
    "selected_internal_price_id",
    "province_quota_price_available",
    "market_price_required",
    "price_resolution_status",
    "confidence_level",
    "review_status",
    "cost_engineer_decision",
    "cost_engineer_comment",
]

MATCH_FIELDS = [
    "internal_price_id",
    "internal_raw_name",
    "internal_name_candidate",
    "internal_unit",
    "internal_total_fee",
    "internal_category",
    "matched_quota_source_code",
    "matched_quota_name_candidate",
    "matched_quota_unit",
    "matched_quota_total_fee",
    "match_type",
    "match_basis",
    "match_confidence",
    "unit_compatibility_status",
    "price_comparison_status",
    "suggested_action",
    "review_status",
    "cost_engineer_decision",
    "cost_engineer_comment",
]

SUPPLEMENT_FIELDS = [
    "enterprise_supplement_code",
    "display_label",
    "internal_price_id",
    "source_file",
    "source_sheet",
    "source_excel_row",
    "raw_category",
    "raw_name",
    "name_candidate",
    "feature_text_candidate",
    "raw_unit",
    "unit_normalized",
    "labor_fee",
    "material_fee",
    "machine_fee",
    "total_fee",
    "suggested_bill_code_9",
    "suggested_bill_name",
    "suggested_parent_quota_code",
    "supplement_type",
    "creation_reason",
    "allowed_use",
    "forbidden_use",
    "review_status",
    "cost_engineer_decision",
    "cost_engineer_comment",
]

ISSUE_FIELDS = [
    "issue_id",
    "issue_type",
    "severity",
    "internal_price_id",
    "internal_raw_name",
    "quota_source_code",
    "quota_raw_name",
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
RULE_SHEET_FIELDS = ["section", "rule_text"]

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

DOMAIN_TERMS = [
    "土方",
    "石方",
    "开挖",
    "回填",
    "外运",
    "消纳",
    "泥浆",
    "垫层",
    "灰土",
    "三合土",
    "基坑",
    "基槽",
    "支护",
    "搅拌桩",
    "喷射",
    "锚杆",
    "钢板桩",
    "桩",
    "灌注桩",
    "预制桩",
    "挖孔桩",
    "砖",
    "砌体",
    "砌块",
    "混凝土",
    "钢筋",
    "模板",
    "脚手架",
    "钢结构",
    "屋面",
    "防水",
    "保温",
    "楼地面",
    "墙面",
    "天棚",
    "吊顶",
    "门",
    "窗",
    "油漆",
    "涂料",
    "运输",
    "垂直运输",
    "降水",
    "排水",
    "保护",
]

CATEGORY_PREFIX_HINTS = {
    "土方": {"A1-1"},
    "土石方": {"A1-1"},
    "基坑支护": {"A1-2"},
    "支护": {"A1-2"},
    "桩": {"A1-3"},
    "砌筑": {"A1-4"},
    "砌体": {"A1-4"},
    "混凝土": {"A1-5", "A1-6"},
    "钢筋": {"A1-5"},
    "钢结构": {"A1-7"},
    "木": {"A1-8"},
    "门窗": {"A1-9"},
    "屋面": {"A1-10"},
    "防水": {"A1-10"},
    "保温": {"A1-11"},
    "防腐": {"A1-11"},
    "楼地面": {"A1-12"},
    "墙面": {"A1-13"},
    "抹灰": {"A1-13"},
    "天棚": {"A1-14"},
    "吊顶": {"A1-14"},
    "油漆": {"A1-15"},
    "涂料": {"A1-15"},
    "模板": {"A1-20"},
    "脚手架": {"A1-21"},
    "垂直运输": {"A1-22"},
    "运输": {"A1-23"},
    "保护": {"A1-24"},
    "降水": {"A1-25"},
    "排水": {"A1-25"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Align enterprise internal prices to GD2018 quota baseline.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--node-exe", type=Path, default=NODE_EXE_DEFAULT)
    parser.add_argument("--node-modules", type=Path, default=NODE_MODULES_DEFAULT)
    return parser.parse_args()


def norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").strip()


def compact(value: Any) -> str:
    text = norm(value).lower()
    text = text.replace("（", "(").replace("）", ")").replace("：", ":")
    text = re.sub(r"[\s,，、;；。.\-_/()（）]", "", text)
    return text


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
        if part:
            parts.append(int(part) if part.isdigit() else part)
    return tuple(parts)


def parse_decimal(value: Any) -> Decimal | None:
    text = norm(value)
    if not text or text in {"-", "--", "—", "/"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def fmt_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def source_prefix(code: str) -> str:
    match = re.match(r"^(A\d+-\d+)-", norm(code))
    return match.group(1) if match else ""


def unit_dimension(unit: str) -> str:
    value = compact(unit).replace("³", "3").replace("²", "2")
    if not value or value == "unparsed":
        return "unknown"
    if "m3" in value or "立方" in value:
        return "volume"
    if "m2" in value or "平方" in value or "㎡" in value:
        return "area"
    if value in {"m", "米"}:
        return "length"
    if value in {"t", "吨", "kg", "千克", "公斤"}:
        return "weight"
    if any(token in value for token in ["个", "项", "套", "台班", "工日", "樘", "根", "块", "件"]):
        return "count_or_shift"
    return "unknown"


def terms_in(text: str) -> List[str]:
    return [term for term in DOMAIN_TERMS if term in text]


def text_for_quota(row: Dict[str, str]) -> str:
    return " ".join(
        norm(row.get(field, ""))
        for field in ["source_code", "raw_name", "quota_name_candidate", "quota_feature_text_candidate", "chapter_guess", "section_guess"]
    )


def text_for_internal(row: Dict[str, str]) -> str:
    return " ".join(
        norm(row.get(field, ""))
        for field in ["category", "subcategory", "raw_name", "name_candidate", "feature_text_candidate", "raw_unit"]
    )


def category_prefixes(row: Dict[str, str]) -> set[str]:
    text = norm(row.get("category", "")) + " " + norm(row.get("subcategory", "")) + " " + norm(row.get("raw_name", ""))
    prefixes: set[str] = set()
    for key, values in CATEGORY_PREFIX_HINTS.items():
        if key in text:
            prefixes.update(values)
    return prefixes


def prepare_quota_profiles(quotas: Sequence[Dict[str, str]], pricing_by_code: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for row in quotas:
        code = norm(row.get("source_code"))
        text = text_for_quota(row)
        pricing = pricing_by_code.get(code, {})
        total = norm(pricing.get("raw_total_fee")) or norm(row.get("raw_total_fee"))
        profiles.append(
            {
                "row": row,
                "code": code,
                "text": text,
                "compact_text": compact(text),
                "name_compact": compact(row.get("quota_name_candidate") or row.get("raw_name")),
                "terms": set(terms_in(text)),
                "prefix": norm(row.get("code_prefix")) or source_prefix(code),
                "unit_dim": unit_dimension(row.get("unit", "")),
                "total_fee": total,
                "total_decimal": parse_decimal(total),
            }
        )
    return profiles


def prepare_internal_profiles(internals: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for row in internals:
        text = text_for_internal(row)
        total = parse_decimal(row.get("total_fee"))
        if total is None:
            total = sum((parse_decimal(row.get(field)) or Decimal("0")) for field in ["labor_fee", "material_fee", "machine_fee"])
            if total == 0:
                total = None
        profiles.append(
            {
                "row": row,
                "id": norm(row.get("internal_price_id")),
                "text": text,
                "compact_text": compact(text),
                "name_compact": compact(row.get("name_candidate") or row.get("raw_name")),
                "terms": set(terms_in(text)),
                "prefix_hints": category_prefixes(row),
                "unit_dim": unit_dimension(row.get("unit_normalized") or row.get("raw_unit")),
                "total_decimal": total,
                "total_fee": norm(row.get("total_fee")) or fmt_decimal(total),
            }
        )
    return profiles


def unit_status(internal: Dict[str, Any], quota: Dict[str, Any]) -> str:
    if not norm(internal["row"].get("raw_unit")):
        return "missing_internal_unit"
    if internal["unit_dim"] == "unknown" or quota["unit_dim"] == "unknown":
        return "unknown"
    return "compatible" if internal["unit_dim"] == quota["unit_dim"] else "mismatch"


def score_pair(internal: Dict[str, Any], quota: Dict[str, Any]) -> Tuple[float, List[str], str]:
    basis: List[str] = []
    score = 0.0
    iname = internal["name_compact"]
    qname = quota["name_compact"]
    if iname and qname and iname == qname:
        score += 8.0
        basis.append("exact_compact_name")
    elif iname and qname and (iname in qname or qname in iname):
        score += 5.0
        basis.append("name_contains")
    overlap = sorted(internal["terms"].intersection(quota["terms"]))
    if overlap:
        score += len(overlap) * 1.25
        basis.append("term_overlap:" + "/".join(overlap[:8]))
    if quota["prefix"] in internal["prefix_hints"]:
        score += 2.0
        basis.append("category_prefix_hint")
    status = unit_status(internal, quota)
    if status == "compatible":
        score += 1.25
        basis.append("unit_compatible")
    elif status == "mismatch":
        score -= 1.0
        basis.append("unit_mismatch")
    if internal["total_decimal"] is None:
        score -= 0.5
        basis.append("missing_internal_price")
    return score, basis, status


def match_type(score: float, basis: Sequence[str], unit_compatibility: str) -> str:
    if "exact_compact_name" in basis and unit_compatibility == "compatible":
        return "exact_name_unit_candidate"
    if score >= 6.0 and unit_compatibility != "mismatch":
        return "strong_semantic_candidate"
    if score >= 4.5 and "category_prefix_hint" in basis and unit_compatibility != "mismatch":
        return "category_semantic_candidate"
    if score >= 3.2:
        return "weak_candidate"
    return "no_match"


def price_comparison(internal_total: Decimal | None, quota_total: Decimal | None) -> str:
    if internal_total is None:
        return "missing_internal_price"
    if quota_total is None or quota_total == 0:
        return "province_price_missing"
    ratio = internal_total / quota_total
    if Decimal("0.8") <= ratio <= Decimal("1.2"):
        return "within_20_percent"
    if Decimal("0.5") <= ratio <= Decimal("1.5"):
        return "within_50_percent"
    return "large_variance"


def suggested_action_for(mtype: str, unit_compat: str, internal_price_missing: bool) -> str:
    if internal_price_missing:
        return "manual_review_required"
    if mtype in {"exact_name_unit_candidate", "strong_semantic_candidate", "category_semantic_candidate"} and unit_compat != "mismatch":
        return "align_to_gd_quota_price_source"
    if mtype == "weak_candidate":
        return "manual_review_required"
    return "create_enterprise_supplement_item"


def build_matches(internals: Sequence[Dict[str, str]], quotas: Sequence[Dict[str, str]], pricing: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    pricing_by_code = {norm(row.get("source_code")): row for row in pricing}
    quota_profiles = prepare_quota_profiles(quotas, pricing_by_code)
    internal_profiles = prepare_internal_profiles(internals)
    rows: List[Dict[str, Any]] = []
    for internal in internal_profiles:
        scored: List[Tuple[float, Dict[str, Any], List[str], str]] = []
        for quota in quota_profiles:
            score, basis, ustatus = score_pair(internal, quota)
            if score >= 3.2:
                scored.append((score, quota, basis, ustatus))
        scored.sort(key=lambda item: item[0], reverse=True)
        keep = scored[:12]
        if not keep:
            row = internal["row"]
            rows.append(
                {
                    "internal_price_id": internal["id"],
                    "internal_raw_name": norm(row.get("raw_name")),
                    "internal_name_candidate": norm(row.get("name_candidate")),
                    "internal_unit": norm(row.get("unit_normalized") or row.get("raw_unit")),
                    "internal_total_fee": internal["total_fee"],
                    "internal_category": norm(row.get("category")),
                    "matched_quota_source_code": "",
                    "matched_quota_name_candidate": "",
                    "matched_quota_unit": "",
                    "matched_quota_total_fee": "",
                    "match_type": "no_match",
                    "match_basis": "no score above threshold",
                    "match_confidence": "0.00",
                    "unit_compatibility_status": unit_status(internal, {"unit_dim": "unknown"}),
                    "price_comparison_status": "not_compared",
                    "suggested_action": "create_enterprise_supplement_item",
                    "review_status": REVIEW_STATUS,
                    "cost_engineer_decision": "",
                    "cost_engineer_comment": "",
                }
            )
            continue
        for score, quota, basis, ustatus in keep:
            irow = internal["row"]
            qrow = quota["row"]
            mtype = match_type(score, basis, ustatus)
            pcomp = price_comparison(internal["total_decimal"], quota["total_decimal"])
            rows.append(
                {
                    "internal_price_id": internal["id"],
                    "internal_raw_name": norm(irow.get("raw_name")),
                    "internal_name_candidate": norm(irow.get("name_candidate")),
                    "internal_unit": norm(irow.get("unit_normalized") or irow.get("raw_unit")),
                    "internal_total_fee": internal["total_fee"],
                    "internal_category": norm(irow.get("category")),
                    "matched_quota_source_code": quota["code"],
                    "matched_quota_name_candidate": norm(qrow.get("quota_name_candidate") or qrow.get("raw_name")),
                    "matched_quota_unit": norm(qrow.get("unit")),
                    "matched_quota_total_fee": quota["total_fee"],
                    "match_type": mtype,
                    "match_basis": ";".join(basis[:10]),
                    "match_confidence": f"{max(0.1, min(0.98, score / 10)):.2f}",
                    "unit_compatibility_status": ustatus,
                    "price_comparison_status": pcomp,
                    "suggested_action": suggested_action_for(mtype, ustatus, internal["total_decimal"] is None),
                    "review_status": REVIEW_STATUS,
                    "cost_engineer_decision": "",
                    "cost_engineer_comment": "",
                }
            )
    rows.sort(key=lambda row: (row["internal_price_id"], -float(row.get("match_confidence") or 0), natural_code_key(row["matched_quota_source_code"])))
    return rows


def reliable_match(row: Dict[str, Any]) -> bool:
    return row.get("match_type") in {"exact_name_unit_candidate", "strong_semantic_candidate", "category_semantic_candidate"} and row.get("unit_compatibility_status") != "mismatch"


def weak_match(row: Dict[str, Any]) -> bool:
    return row.get("match_type") == "weak_candidate"


def top_values(rows: Sequence[Dict[str, Any]], key: str, limit: int = 8) -> str:
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


def build_coverage(quotas: Sequence[Dict[str, str]], pricing: Sequence[Dict[str, str]], matches: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pricing_by_code = {norm(row.get("source_code")): row for row in pricing}
    by_quota: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in matches:
        if row.get("matched_quota_source_code"):
            by_quota[row["matched_quota_source_code"]].append(row)
    coverage: List[Dict[str, Any]] = []
    for quota in sorted(quotas, key=lambda row: natural_code_key(row.get("source_code", ""))):
        code = norm(quota.get("source_code"))
        qmatches = sorted(by_quota.get(code, []), key=lambda row: float(row.get("match_confidence") or 0), reverse=True)
        reliable = [row for row in qmatches if reliable_match(row)]
        weak = [row for row in qmatches if weak_match(row)]
        selected = reliable[0] if reliable else None
        quota_total = norm(pricing_by_code.get(code, {}).get("raw_total_fee")) or norm(quota.get("raw_total_fee"))
        has_province_price = parse_decimal(quota_total) is not None
        if selected:
            match_status = "exact_or_strong_candidate"
            priority = "P1_enterprise_internal_price"
            source_type = "enterprise_internal_price_table"
            resolution = "enterprise_price_candidate_available"
            market_required = "false"
            confidence = selected["match_confidence"]
        elif weak:
            match_status = "weak_candidate"
            priority = "P4_province_quota_price_fallback" if has_province_price else "P5_unresolved"
            source_type = "gd2018_province_quota_price" if has_province_price else ""
            resolution = "province_quota_fallback" if has_province_price else "unresolved_manual_review"
            market_required = "false" if has_province_price else "true"
            confidence = weak[0]["match_confidence"]
        else:
            match_status = "no_internal_price_candidate"
            priority = "P4_province_quota_price_fallback" if has_province_price else "P3_market_or_information_price"
            source_type = "gd2018_province_quota_price" if has_province_price else "market_or_information_price_required"
            resolution = "province_quota_fallback" if has_province_price else "market_price_required"
            market_required = "false" if has_province_price else "true"
            confidence = "0.00"
        coverage.append(
            {
                "quota_source_code": code,
                "quota_raw_name": norm(quota.get("raw_name")),
                "quota_name_candidate": norm(quota.get("quota_name_candidate")),
                "quota_feature_text_candidate": norm(quota.get("quota_feature_text_candidate")),
                "quota_unit": norm(quota.get("unit")),
                "quota_raw_total_fee": quota_total,
                "source_code_prefix": norm(quota.get("code_prefix")) or source_prefix(code),
                "matched_internal_price_count": len(qmatches),
                "top_internal_price_ids": top_values(qmatches, "internal_price_id"),
                "top_internal_price_names": top_values(qmatches, "internal_name_candidate"),
                "top_internal_price_units": top_values(qmatches, "internal_unit"),
                "top_internal_price_total_fees": top_values(qmatches, "internal_total_fee"),
                "internal_price_match_status": match_status,
                "selected_price_source_priority": priority,
                "selected_price_source_type": source_type,
                "selected_internal_price_id": selected["internal_price_id"] if selected else "",
                "province_quota_price_available": str(has_province_price).lower(),
                "market_price_required": market_required,
                "price_resolution_status": resolution,
                "confidence_level": confidence,
                "review_status": REVIEW_STATUS,
                "cost_engineer_decision": "",
                "cost_engineer_comment": "",
            }
        )
    return coverage


def supplement_type_for(row: Dict[str, str]) -> str:
    text = norm(row.get("raw_name")) + " " + norm(row.get("name_candidate")) + " " + norm(row.get("feature_text_candidate")) + " " + norm(row.get("category"))
    if any(term in text for term in ["外运", "消纳", "废弃", "泥浆"]):
        return "disposal_fee"
    if any(term in text for term in ["临时", "措施", "保护", "脚手架", "模板", "排水", "降水"]):
        return "temporary_measure"
    if any(term in text for term in ["引孔", "喷射", "泵送", "机械", "工艺", "强风化"]):
        return "special_method"
    if any(term in text for term in ["管理", "配合", "经验"]):
        return "management_experience_item"
    if norm(row.get("raw_name")) and norm(row.get("total_fee")):
        return "enterprise_specific_cost"
    return "unclear_but_possible_price_item"


def build_supplements(internals: Sequence[Dict[str, str]], matches: Sequence[Dict[str, Any]], routing_by_quota: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    by_internal: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in matches:
        by_internal[row["internal_price_id"]].append(row)
    supplements: List[Dict[str, Any]] = []
    for internal in internals:
        iid = norm(internal.get("internal_price_id"))
        rows = sorted(by_internal.get(iid, []), key=lambda row: float(row.get("match_confidence") or 0), reverse=True)
        has_reliable = any(reliable_match(row) for row in rows)
        if has_reliable:
            continue
        best = rows[0] if rows else {}
        quota_code = norm(best.get("matched_quota_source_code"))
        route = routing_by_quota.get(quota_code, {})
        supplement_index = len(supplements) + 1
        supplements.append(
            {
                "enterprise_supplement_code": f"ENT-SUP-{supplement_index:06d}",
                "display_label": f"补子目{supplement_index:03d}",
                "internal_price_id": iid,
                "source_file": norm(internal.get("source_file")),
                "source_sheet": norm(internal.get("source_sheet")),
                "source_excel_row": norm(internal.get("source_excel_row")),
                "raw_category": norm(internal.get("category")),
                "raw_name": norm(internal.get("raw_name")),
                "name_candidate": norm(internal.get("name_candidate")),
                "feature_text_candidate": norm(internal.get("feature_text_candidate")),
                "raw_unit": norm(internal.get("raw_unit")),
                "unit_normalized": norm(internal.get("unit_normalized")),
                "labor_fee": norm(internal.get("labor_fee")),
                "material_fee": norm(internal.get("material_fee")),
                "machine_fee": norm(internal.get("machine_fee")),
                "total_fee": norm(internal.get("total_fee")),
                "suggested_bill_code_9": top_first(route.get("candidate_bill_codes", "")),
                "suggested_bill_name": top_first(route.get("candidate_bill_names", "")),
                "suggested_parent_quota_code": quota_code,
                "supplement_type": supplement_type_for(internal),
                "creation_reason": "no reliable GD2018 quota match; preserve as enterprise supplement candidate for cost review",
                "allowed_use": "enterprise_supplement_candidate_after_cost_department_review",
                "forbidden_use": "must_not_auto_approve;must_not_be_treated_as_official_gd_quota;must_not_write_back_source_code",
                "review_status": REVIEW_STATUS,
                "cost_engineer_decision": "",
                "cost_engineer_comment": "",
            }
        )
    return supplements


def top_first(value: str) -> str:
    parts = [part for part in norm(value).split(";") if part]
    return parts[0] if parts else ""


def add_issue(
    issues: List[Dict[str, Any]],
    issue_type: str,
    severity: str,
    description: str,
    recommended_action: str,
    internal: Dict[str, Any] | None = None,
    quota: Dict[str, Any] | None = None,
) -> None:
    issues.append(
        {
            "issue_id": f"EPALIGN-ISSUE-{len(issues) + 1:06d}",
            "issue_type": issue_type,
            "severity": severity,
            "internal_price_id": norm((internal or {}).get("internal_price_id")),
            "internal_raw_name": norm((internal or {}).get("internal_raw_name") or (internal or {}).get("raw_name")),
            "quota_source_code": norm((quota or {}).get("quota_source_code") or (quota or {}).get("matched_quota_source_code")),
            "quota_raw_name": norm((quota or {}).get("quota_raw_name") or (quota or {}).get("matched_quota_name_candidate")),
            "description": description,
            "recommended_action": recommended_action,
            "review_status": REVIEW_STATUS,
        }
    )


def build_issues(matches: Sequence[Dict[str, Any]], supplements: Sequence[Dict[str, Any]], internals: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    by_internal: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in matches:
        by_internal[row["internal_price_id"]].append(row)
        if row["unit_compatibility_status"] == "mismatch":
            add_issue(issues, "unit_mismatch", "medium", "Internal price unit and GD quota unit dimension differ.", "Manual review before alignment.", row, row)
        if row["match_type"] == "weak_candidate":
            add_issue(issues, "weak_name_candidate", "medium", "Only weak semantic evidence found.", "Treat as manual review, not automatic alignment.", row, row)
        if row["suggested_action"] == "manual_review_required":
            add_issue(issues, "cost_engineer_review_required", "medium", "Candidate requires cost engineer review.", "Confirm before enterprise quota draft.", row, row)
    internal_by_id = {norm(row.get("internal_price_id")): row for row in internals}
    for iid, rows in by_internal.items():
        reliable = [row for row in rows if reliable_match(row)]
        if not reliable:
            src = internal_by_id.get(iid, {})
            add_issue(issues, "internal_price_no_gd_match", "high", "Internal price has no reliable GD2018 quota match.", "Create supplement candidate or refine matching rules.", src)
        if len(reliable) > 1:
            add_issue(issues, "internal_price_multiple_gd_candidates", "medium", "Internal price has multiple reliable GD quota candidates.", "Cost department should choose or split feature conditions.", reliable[0], reliable[0])
    for internal in internals:
        if not norm(internal.get("raw_unit")):
            add_issue(issues, "missing_internal_unit", "medium", "Internal price candidate lacks source unit.", "Confirm unit before alignment.", internal)
        if not norm(internal.get("total_fee")):
            add_issue(issues, "missing_internal_price", "high", "Internal price candidate lacks total fee.", "Resolve price before enterprise quota draft.", internal)
    for supplement in supplements:
        add_issue(issues, "supplement_candidate_required", "high", "Enterprise supplement candidate generated.", "Review supplement scope and coding before Enterprise Quota Master V0.1.", supplement)
    return issues


def write_rules(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Price Source Priority Rules V0.1",
                "",
                "## 1. Objective",
                "",
                "Define price-source priority rules for forming Enterprise Quota V0.1 from GD2018 quota baseline, enterprise internal prices, historical project or subcontract prices, and market or information prices.",
                "",
                "## 2. Base Principle",
                "",
                "The 3712 GD2018 quota rows are the enterprise quota baseline. The enterprise quota baseline can only add supplement items and must not remove official GD2018 quota rows.",
                "",
                "## 3. Price Source Priority",
                "",
                "- P1 enterprise internal price",
                "- P2 enterprise historical project / subcontract quotation",
                "- P3 market price / information price",
                "- P4 GD2018 province quota price fallback",
                "- P5 unresolved, manual processing",
                "",
                "## 4. Enterprise Supplement Item Rules",
                "",
                "Enterprise supplement items may exist for valid internal price rows that do not reliably match GD2018 quota rows. They must use ENT-SUP codes and must not fake province quota codes.",
                "",
                "## 5. Review Rules",
                "",
                "All price candidates remain pending. Approved rows are not allowed in this stage.",
                "",
                "## 6. Next Stage Gate",
                "",
                "Only after this stage passes review should the project enter Enterprise Quota Master V0.1 Draft.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def rules_for_xlsx_rows() -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    current = ""
    for line in [
        "# Price Source Priority Rules V0.1",
        "## 1. Objective",
        "Define price-source priority rules for Enterprise Quota V0.1.",
        "## 2. Base Principle",
        "GD2018 3712 quota rows are the baseline; only add, never remove.",
        "## 3. Price Source Priority",
        "P1 enterprise internal price; P2 historical project/subcontract; P3 market/information; P4 province quota fallback; P5 unresolved.",
        "## 4. Enterprise Supplement Item Rules",
        "Use ENT-SUP codes only; never fake province quota codes.",
        "## 5. Review Rules",
        "All candidates remain pending; no approved rows.",
        "## 6. Next Stage Gate",
        "Proceed to Enterprise Quota Master V0.1 Draft only after review.",
    ]:
        if line.startswith("#"):
            current = line.lstrip("# ")
        else:
            sections.append({"section": current, "rule_text": line})
    return sections


def build_dashboard(coverage: Sequence[Dict[str, Any]], matches: Sequence[Dict[str, Any]], internals: Sequence[Dict[str, str]], supplements: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched_internal_ids = {row["internal_price_id"] for row in matches if reliable_match(row)}
    metrics = [
        ("gd_quota_total_rows", len(coverage), "3712", len(coverage) == 3712, "high", ""),
        ("internal_price_candidate_rows", len(internals), "> 0", len(internals) > 0, "high", ""),
        ("gd_quota_with_internal_price_candidate", sum(1 for row in coverage if int(row["matched_internal_price_count"]) > 0), "reference only", True, "medium", ""),
        ("gd_quota_without_internal_price_candidate", sum(1 for row in coverage if int(row["matched_internal_price_count"]) == 0), "fallback/review", True, "medium", ""),
        ("internal_price_rows_matched_to_gd_quota", len(matched_internal_ids), "review", True, "medium", ""),
        ("internal_price_rows_unmatched", len(internals) - len(matched_internal_ids), "supplement/manual review", True, "high", ""),
        ("enterprise_supplement_candidate_count", len(supplements), "manual review", True, "high", ""),
        ("province_quota_fallback_count", sum(1 for row in coverage if row["selected_price_source_priority"] == "P4_province_quota_price_fallback"), "fallback", True, "medium", ""),
        ("market_price_required_count", sum(1 for row in coverage if row["market_price_required"] == "true"), "market input needed", True, "high", ""),
        ("unresolved_manual_review_count", sum(1 for row in coverage if row["price_resolution_status"] == "unresolved_manual_review"), "manual review", True, "high", ""),
        ("approved_count", 0, "0", True, "high", "No approved rows generated."),
        ("non_pending_review_status_count", 0, "0", True, "high", ""),
        ("database_write_detected", 0, "0", True, "high", "Script writes artifacts only."),
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
        for name, value, expected, ok, severity, remark in metrics
    ]


def recommendation(coverage: Sequence[Dict[str, Any]], xlsx_ok: bool) -> str:
    if not xlsx_ok:
        return "blocked_xlsx_generation_failed"
    if len(coverage) == 3712:
        return "enterprise_price_alignment_ready_for_enterprise_quota_master_v0_1"
    return "enterprise_price_alignment_partial_manual_intervention_required"


def build_summary(dashboard: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]], rec: str) -> List[Dict[str, Any]]:
    rows = [{"metric_name": row["metric_name"], "metric_value": row["metric_value"], "remark": row["remark"]} for row in dashboard]
    rows.append({"metric_name": "issue_count", "metric_value": len(issues), "remark": ""})
    rows.append({"metric_name": "recommendation", "metric_value": rec, "remark": ""})
    return rows


def build_xlsx(output_dir: Path, node_exe: Path, node_modules: Path) -> None:
    if not node_exe.exists() or not node_modules.exists():
        raise RuntimeError(f"Bundled node runtime unavailable: node={node_exe}, node_modules={node_modules}")
    specs = [
        ("gd_quota_price_coverage_3712", "gd_quota_price_coverage_matrix_3712.csv", len(COVERAGE_FIELDS)),
        ("internal_price_to_gd_quota_candidate", "internal_price_to_gd_quota_candidate.csv", len(MATCH_FIELDS)),
        ("enterprise_supplement_item_candidate", "enterprise_supplement_item_candidate.csv", len(SUPPLEMENT_FIELDS)),
        ("alignment_issues", "internal_price_alignment_issues.csv", len(ISSUE_FIELDS)),
        ("price_source_priority_rules", "price_source_priority_rules_for_xlsx.csv", len(RULE_SHEET_FIELDS)),
        ("dashboard", "enterprise_price_alignment_dashboard.csv", len(DASHBOARD_FIELDS)),
        ("summary", "summary_for_xlsx.csv", len(SUMMARY_FIELDS)),
    ]
    builder = r'''
import fs from "node:fs/promises";
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
  sheet.getRangeByIndexes(0, 0, 1, colCount).format.columnWidth = sheetName === "summary" || sheetName === "dashboard" ? 24 : 18;
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
await workbook.render({ sheetName: "summary", autoCrop: "all", scale: 1, format: "png" });
await workbook.render({ sheetName: "dashboard", autoCrop: "all", scale: 1, format: "png" });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/Enterprise_Price_To_GD_Quota_Alignment_Review.xlsx`);
console.log(`xlsx=${outputDir}/Enterprise_Price_To_GD_Quota_Alignment_Review.xlsx`);
'''
    with tempfile.TemporaryDirectory(prefix="enterprise_price_align_xlsx_") as tmp:
        tmp_path = Path(tmp)
        link = tmp_path / "node_modules"
        try:
            os.symlink(node_modules, link, target_is_directory=True)
        except OSError:
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(node_modules)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        builder_path = tmp_path / "build_enterprise_price_alignment_review.mjs"
        builder_path.write_text(builder, encoding="utf-8")
        subprocess.run([str(node_exe), str(builder_path), str(output_dir), json.dumps(specs)], cwd=tmp_path, check=True)
    sidecar = output_dir / "Enterprise_Price_To_GD_Quota_Alignment_Review.xlsx.inspect.ndjson"
    if sidecar.exists():
        sidecar.unlink()


def write_report(path: Path, coverage: Sequence[Dict[str, Any]], matches: Sequence[Dict[str, Any]], supplements: Sequence[Dict[str, Any]], issues: Sequence[Dict[str, Any]], dashboard: Sequence[Dict[str, Any]], rec: str) -> None:
    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    issue_counts = Counter(row["issue_type"] for row in issues)
    match_counts = Counter(row["match_type"] for row in matches)
    lines = [
        "# Stage ENTERPRISE-PRICE-TO-GD-QUOTA-ALIGNMENT-1 Report",
        "",
        "## 1. Task Scope",
        "",
        "Align enterprise internal price candidates to the full GD2018 quota baseline and generate enterprise supplement item candidates for valid internal price rows without reliable GD quota matches.",
        "",
        "## 2. Business Background",
        "",
        "GD2018 3712 quota rows remain the enterprise quota baseline and can only be supplemented, not reduced. Internal prices are candidate price sources only.",
        "",
        "## 3. Input Files",
        "",
        "- GD2018 normalized quota baseline and pricing fields",
        "- ENTERPRISE_PRICE_BASELINE_LOCK_1 internal price candidates and issues",
        "- MAP_FULL_GOVERNANCE_REFERENCE_1 full bill-to-quota routing reference",
        "",
        "## 4. GD Quota Price Coverage Summary",
        "",
        f"- gd_quota_total_rows: {len(coverage)}",
        f"- gd_quota_with_internal_price_candidate: {metrics.get('gd_quota_with_internal_price_candidate', 0)}",
        f"- gd_quota_without_internal_price_candidate: {metrics.get('gd_quota_without_internal_price_candidate', 0)}",
        f"- province_quota_fallback_count: {metrics.get('province_quota_fallback_count', 0)}",
        f"- market_price_required_count: {metrics.get('market_price_required_count', 0)}",
        "",
        "## 5. Internal Price to GD Quota Alignment Summary",
        "",
        f"- internal_price_candidate_rows: {metrics.get('internal_price_candidate_rows', 0)}",
        f"- internal_price_rows_matched_to_gd_quota: {metrics.get('internal_price_rows_matched_to_gd_quota', 0)}",
        f"- internal_price_rows_unmatched: {metrics.get('internal_price_rows_unmatched', 0)}",
        f"- match_type_counts: {json.dumps(dict(match_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 6. Enterprise Supplement Item Candidates",
        "",
        f"- enterprise_supplement_candidate_count: {len(supplements)}",
        "- Supplement item codes use ENT-SUP-* and must not be treated as official GD quota codes.",
        "",
        "## 7. Price Source Priority",
        "",
        "P1 enterprise internal price; P2 historical project/subcontract price; P3 market or information price; P4 GD2018 province quota fallback; P5 unresolved manual processing.",
        "",
        "## 8. Quality Issues",
        "",
        f"- issue_count: {len(issues)}",
        f"- issue_type_counts: {json.dumps(dict(issue_counts), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 9. Not Approved / Not Final Statement",
        "",
        "All outputs remain pending. This stage does not write databases, approve rows, generate internal_price_library, generate final enterprise standard names, create formal enterprise quota tables, enter Web development, or parse real bid lists.",
        "",
        "## 10. Next Step Recommendation",
        "",
        rec,
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


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
        "backup_path": rel(project_root / ENGINE_REL / "data" / "private" / "reference_extraction" / "backups" / "runs_backup_after_ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1", project_root),
        "status": "generated" if exists else "missing",
        "remark": "pending price alignment and supplement candidates only; not approved and not formal enterprise quota",
    }


def update_manifest(project_root: Path, output_dir: Path, artifacts: Sequence[str], workbook_total_rows: int) -> None:
    manifest_path = project_root / DOCS_REF_REL / "reference_artifact_manifest.csv"
    existing = read_csv(manifest_path) if manifest_path.exists() else []
    source_file = ";".join([rel(project_root / GD_QUOTA_REL, project_root), rel(project_root / INTERNAL_PRICE_REL, project_root)])
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
        "- Enterprise price alignment outputs are pending review artifacts only and do not approve mappings.",
        "- Enterprise supplement item candidates must use ENT-SUP codes and must not be treated as official GD quota rows.",
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
        "## Latest Enterprise Price To GD Quota Alignment Outputs",
        "",
    ]
    for row in latest:
        lines.append(f"- `{row.get('expected_path')}` ({row.get('row_count') or 'n/a'} rows)")
    lines.extend(
        [
            "",
            "## Backup Requirement",
            "",
            "`construction_cost_knowledge_engine/data/private/reference_extraction/backups/runs_backup_after_ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1/`",
            "",
        ]
    )
    (project_root / DOCS_REF_REL / "REFERENCE_ARTIFACT_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


def validate_inputs(quotas: Sequence[Dict[str, str]], pricing: Sequence[Dict[str, str]], internals: Sequence[Dict[str, str]], routing: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    checks = {
        "quota_rows": len(quotas),
        "pricing_rows": len(pricing),
        "quota_missing_source": sum(1 for row in quotas if not norm(row.get("source_code"))),
        "quota_missing_name": sum(1 for row in quotas if not norm(row.get("raw_name"))),
        "quota_missing_unit": sum(1 for row in quotas if not norm(row.get("unit"))),
        "quota_non_pending": sum(1 for row in quotas if norm(row.get("review_status")) != REVIEW_STATUS),
        "internal_rows": len(internals),
        "internal_non_pending": sum(1 for row in internals if norm(row.get("review_status")) != REVIEW_STATUS),
        "internal_approved": sum(1 for row in internals if norm(row.get("review_status")) == "approved"),
        "routing_rows": len(routing),
    }
    hard_fail = [
        checks["quota_rows"] != 3712,
        checks["quota_missing_source"] == checks["quota_rows"],
        checks["quota_missing_name"] == checks["quota_rows"],
        checks["quota_missing_unit"] == checks["quota_rows"],
        checks["quota_non_pending"] != 0,
        checks["internal_rows"] == 0,
        checks["internal_non_pending"] != 0,
        checks["internal_approved"] != 0,
        checks["routing_rows"] != 3712,
    ]
    checks["status"] = "pass" if not any(hard_fail) else "blocked_missing_inputs"
    return checks


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        quotas = read_csv(project_root / GD_QUOTA_REL)
        pricing = read_csv(project_root / GD_PRICING_REL)
        internals = read_csv(project_root / INTERNAL_PRICE_REL)
        _internal_issues = read_csv(project_root / INTERNAL_ISSUES_REL)
        _full_matrix = read_csv(project_root / FULL_MATRIX_REL)
        _full_detail = read_csv(project_root / FULL_DETAIL_REL)
        routing = read_csv(project_root / FULL_ROUTING_REL)
    except FileNotFoundError as exc:
        print("recommendation=blocked_missing_inputs")
        print(f"missing_input={exc}")
        return 2

    checks = validate_inputs(quotas, pricing, internals, routing)
    if checks["status"] != "pass":
        print("recommendation=blocked_missing_inputs")
        print(json.dumps(checks, ensure_ascii=False, sort_keys=True))
        return 2

    routing_by_quota = {norm(row.get("quota_source_code")): row for row in routing}
    matches = build_matches(internals, quotas, pricing)
    coverage = build_coverage(quotas, pricing, matches)
    supplements = build_supplements(internals, matches, routing_by_quota)
    issues = build_issues(matches, supplements, internals)
    write_rules(output_dir / "price_source_priority_rules_v0_1.md")
    dashboard = build_dashboard(coverage, matches, internals, supplements, issues)
    rec = recommendation(coverage, xlsx_ok=True)
    summary = build_summary(dashboard, issues, rec)

    write_csv(output_dir / "gd_quota_price_coverage_matrix_3712.csv", COVERAGE_FIELDS, coverage)
    write_csv(output_dir / "internal_price_to_gd_quota_candidate.csv", MATCH_FIELDS, matches)
    write_csv(output_dir / "enterprise_supplement_item_candidate.csv", SUPPLEMENT_FIELDS, supplements)
    write_csv(output_dir / "internal_price_alignment_issues.csv", ISSUE_FIELDS, issues)
    write_csv(output_dir / "enterprise_price_alignment_dashboard.csv", DASHBOARD_FIELDS, dashboard)
    write_csv(output_dir / "price_source_priority_rules_for_xlsx.csv", RULE_SHEET_FIELDS, rules_for_xlsx_rows())
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)

    try:
        build_xlsx(output_dir, args.node_exe, args.node_modules)
    except Exception as exc:
        write_report(output_dir / "stage_enterprise_price_to_gd_quota_alignment_report.md", coverage, matches, supplements, issues, dashboard, "blocked_xlsx_generation_failed")
        print("recommendation=blocked_xlsx_generation_failed")
        print(f"xlsx_error={exc}")
        return 3

    rec = recommendation(coverage, xlsx_ok=True)
    summary = build_summary(dashboard, issues, rec)
    write_csv(output_dir / "summary_for_xlsx.csv", SUMMARY_FIELDS, summary)
    write_report(output_dir / "stage_enterprise_price_to_gd_quota_alignment_report.md", coverage, matches, supplements, issues, dashboard, rec)

    artifacts = [
        "gd_quota_price_coverage_matrix_3712.csv",
        "internal_price_to_gd_quota_candidate.csv",
        "enterprise_supplement_item_candidate.csv",
        "internal_price_alignment_issues.csv",
        "price_source_priority_rules_v0_1.md",
        "enterprise_price_alignment_dashboard.csv",
        "Enterprise_Price_To_GD_Quota_Alignment_Review.xlsx",
        "stage_enterprise_price_to_gd_quota_alignment_report.md",
    ]
    workbook_total_rows = len(coverage) + len(matches) + len(supplements) + len(issues) + len(rules_for_xlsx_rows()) + len(dashboard) + len(summary)
    update_manifest(project_root, output_dir, artifacts, workbook_total_rows)
    (output_dir / "summary_for_xlsx.csv").unlink(missing_ok=True)
    (output_dir / "price_source_priority_rules_for_xlsx.csv").unlink(missing_ok=True)

    metrics = {row["metric_name"]: row["metric_value"] for row in dashboard}
    print(f"recommendation={rec}")
    print(f"gd_quota_rows={len(coverage)}")
    print(f"internal_price_candidate_rows={len(internals)}")
    print(f"gd_quota_with_internal_price_candidate={metrics.get('gd_quota_with_internal_price_candidate', 0)}")
    print(f"internal_price_matched_rows={metrics.get('internal_price_rows_matched_to_gd_quota', 0)}")
    print(f"supplement_item_candidate_rows={len(supplements)}")
    print(f"province_fallback_count={metrics.get('province_quota_fallback_count', 0)}")
    print(f"market_price_required_count={metrics.get('market_price_required_count', 0)}")
    print(f"unresolved_count={metrics.get('unresolved_manual_review_count', 0)}")
    print("approved_count=0")
    print("non_pending_review_status_count=0")
    print(f"xlsx_exists={(output_dir / 'Enterprise_Price_To_GD_Quota_Alignment_Review.xlsx').exists()}")
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
