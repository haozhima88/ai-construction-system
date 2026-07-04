#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage MAP-A111-0 quota-to-bill mapping trial.

Generates pending rule/semantic mapping candidates between GD2018 A.1.1 quota
reference candidates and GB/T 50854-2024 Appendix A bill references.

This script does not write databases, migrations, cost_items,
knowledge_review_records, internal_price_library, quota_to_bill_mapping, or
approved records. It does not modify any input file and does not write bill
codes back into quota reference candidates.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")

BILL_REFERENCE_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "GB50854_2024_stageB_docx_full" / "bill_item_reference_all_candidate.csv"
QUOTA_REFERENCE_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "GD2018_stage2R_A111_full" / "standard_cost_item_reference_A111_candidate.csv"
PRICING_REFERENCE_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "GD2018_stage2R_A111_full" / "reference_quota_pricing_snapshot_A111.csv"
OUTPUT_DIR_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "MAP_A111_quota_to_bill_trial"

SOURCE_TYPE = "rule_semantic_candidate"
MAPPING_SCOPE = "A.1.1 土石方工程"
REVIEW_STATUS = "pending"

EXPECTED_BILL_CODES = [
    "010101001",
    "010101002",
    "010101003",
    "010102001",
    "010102002",
    "010102003",
    "010102004",
    "010102005",
    "010102006",
    "010102007",
    "010103001",
    "010103002",
]

SUPPLEMENTAL_CODES = {
    "A1-1-56-1",
    "A1-1-56-2",
    "A1-1-56-3",
    "A1-1-56-4",
    "A1-1-118-1",
    "A1-1-118-2",
}

SNAPSHOT_QUOTA_FIELDS = [
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

SNAPSHOT_BILL_FIELDS = [
    "bill_reference_id",
    "bill_code_9",
    "bill_name",
    "unit",
    "appendix_code",
    "section_code",
    "section_name",
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
    "bill_unit",
    "bill_project_feature_raw",
    "bill_quantity_calculation_rule",
    "bill_work_content_raw",
    "mapping_type",
    "mapping_basis",
    "mapping_confidence",
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


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def natural_quota_key(code: str) -> Tuple[int, int]:
    match = re.fullmatch(r"A1-1-(\d+)(?:-(\d+))?", compact(code))
    if not match:
        return (10000, 10000)
    return (int(match.group(1)), int(match.group(2) or 0))


def quota_base_number(code: str) -> int:
    return natural_quota_key(code)[0]


def is_supplemental(code: str) -> bool:
    return compact(code) in SUPPLEMENTAL_CODES or bool(re.fullmatch(r"A1-1-\d+-\d+", compact(code)))


def normalized_unit_dimension(unit: str) -> str:
    unit = compact(unit).lower().replace("³", "3").replace("㎡", "m2").replace("²", "2")
    if "m2" in unit or "平方" in unit:
        return "area"
    if "m3" in unit or "立方" in unit:
        return "volume"
    if unit:
        return "other"
    return ""


def add_issue(
    issues: List[Dict[str, str]],
    quota: Dict[str, str],
    issue_type: str,
    detail: str,
    severity: str,
    action: str,
) -> None:
    issues.append(
        {
            "issue_id": f"ISSUE_MAP_A111_{len(issues) + 1:04d}",
            "quota_source_code": quota.get("source_code", ""),
            "quota_raw_name": quota.get("raw_name", ""),
            "issue_type": issue_type,
            "issue_detail": detail,
            "severity": severity,
            "suggested_action": action,
        }
    )


def issue_once(
    issues: List[Dict[str, str]],
    seen: set,
    quota: Dict[str, str],
    issue_type: str,
    detail: str,
    severity: str,
    action: str,
) -> None:
    key = (quota.get("source_code", ""), issue_type, detail)
    if key in seen:
        return
    seen.add(key)
    add_issue(issues, quota, issue_type, detail, severity, action)


def bill_by_code(bills: Sequence[Dict[str, str]], code: str) -> Optional[Dict[str, str]]:
    for row in bills:
        if row.get("bill_code_9") == code:
            return row
    return None


def is_transport_like(name: str) -> bool:
    return any(token in name for token in ["运", "运输", "自卸汽车", "人力车", "铲运", "转堆", "垂直运输"])


def is_construction_method_only(name: str) -> bool:
    return any(token in name for token in ["原土打夯", "装车", "装土方", "装石方", "推土机", "铲运机", "转堆", "垂直运输", "挡土板", "压路机碾压"])


def choose_rule_mappings(quota: Dict[str, str]) -> List[Dict[str, Any]]:
    """Return bill-code candidates and rule metadata for one quota row."""
    name = compact(quota.get("raw_name") or quota.get("standard_name_candidate"))
    code = compact(quota.get("source_code"))
    base = quota_base_number(code)
    results: List[Dict[str, Any]] = []

    def add(bill_code: str, mapping_type: str, confidence: float, basis: str, remark: str = "") -> None:
        results.append(
            {
                "bill_code_9": bill_code,
                "mapping_type": mapping_type,
                "mapping_confidence": confidence,
                "mapping_basis": basis,
                "remark": remark,
            }
        )

    def add_no_direct(confidence: float, basis: str, remark: str = "") -> None:
        results.append(
            {
                "bill_code_9": "",
                "mapping_type": "no_direct_bill_item",
                "mapping_confidence": confidence,
                "mapping_basis": basis,
                "remark": remark,
            }
        )

    if "挡土板" in name:
        add_no_direct(0.50, "挡土板更接近措施/支护辅助项目，GB/T 50854 附录A土石方清单项无直接对应。", "no_direct_bill_item")
        return results

    if "平整场地" in name:
        add("010103001", "direct_candidate", 0.96, "定额名称与清单项目“平整场地”直接一致。")
        return results

    if "原土打夯" in name:
        add("010103001", "needs_manual_review", 0.62, "原土打夯可能是平整场地相关工作内容，但名称不像独立清单项目。", "construction_method_only")
        return results

    if "冻土" in name:
        add("010102003", "direct_candidate", 0.93, "定额名称含冻土，与清单项目“挖冻土”工程对象一致。")
        return results

    if "淤泥" in name or "流砂" in name:
        if is_transport_like(name) or "装车" in name or name.startswith("人工装车"):
            add("010103002", "feature_required", 0.58, "定额为淤泥/流砂运输或装车工序，可能服务于余方弃置但不是直接清单项。", "transport_item_uncertain")
        else:
            add("010102004", "direct_candidate", 0.91, "定额名称含挖淤泥/流砂，与清单项目“挖淤泥流砂”高度一致。")
        return results

    if "回填" in name:
        if "槽" in name or "坑" in name:
            add("010102007", "direct_candidate", 0.88, "定额名称含回填且部位为槽/坑，优先对应基础土石方回填方。")
        elif "填土方" in name or "填石方" in name or "碾压" in name:
            add("010102007", "needs_manual_review", 0.55, "压路机碾压填土/填石更像回填施工方法，需要判断是否形成清单回填方。", "construction_method_only")
        else:
            add("010102007", "one_quota_to_multi_bill", 0.78, "定额名称为回填类，但未说明是否为基础回填或单独土石方回填。")
            add("010101003", "one_quota_to_multi_bill", 0.72, "定额名称为回填类，可能与单独土石方回填相关，需要部位特征判断。")
        return results

    if is_transport_like(name) or "装土方" in name or "装石方" in name or "装车" in name:
        if "石方" in name:
            add("010103002", "feature_required", 0.56, "石方运输/装载可能属于余方弃置工作内容，但定额更像施工工序。", "transport_item_uncertain")
        else:
            add("010103002", "feature_required", 0.58, "土方运输/装载可能属于余方弃置工作内容，但定额更像施工工序。", "transport_item_uncertain")
        return results

    if "压路机碾压" in name:
        add("010102007", "needs_manual_review", 0.55, "压路机碾压土(石)方更像回填压实施工方法，需要判断是否形成清单回填方。", "construction_method_only")
        return results

    if "沟槽、基坑土方" in name or "槽、坑土方" in name:
        add("010102001", "one_quota_to_multi_bill", 0.78, "定额合并沟槽、基坑土方，需要按项目特征拆分到基坑或沟槽清单。")
        add("010102002", "one_quota_to_multi_bill", 0.78, "定额合并沟槽、基坑土方，需要按项目特征拆分到基坑或沟槽清单。")
        return results

    if "基坑土方" in name:
        add("010102001", "direct_candidate", 0.94, "定额名称含基坑土方，与清单项目“挖基坑土方”高度一致。")
        return results

    if "沟槽土方" in name:
        add("010102002", "direct_candidate", 0.94, "定额名称含沟槽土方，与清单项目“挖沟槽土方”高度一致。")
        return results

    if "一般土方" in name:
        if "挖装" in name:
            add("010101001", "multi_quota_to_one_bill", 0.84, "挖装一般土方对应挖单独土方的工作内容组合，仍需项目特征确认。")
        elif "人工挖" in name or "挖掘机挖" in name:
            add("010101001", "direct_candidate", 0.92, "定额名称含一般土方且无基坑/沟槽特征，优先对应挖单独土方。")
        else:
            add("010101001", "feature_required", 0.76, "一般土方相关但施工方法/范围需人工确认。")
        return results

    if "槽、坑石方" in name or "槽、坑" in name and "石方" in name:
        add("010102005", "one_quota_to_multi_bill", 0.78, "定额合并槽、坑石方，需要按项目特征拆分到基坑石方或沟槽石方。")
        add("010102006", "one_quota_to_multi_bill", 0.78, "定额合并槽、坑石方，需要按项目特征拆分到基坑石方或沟槽石方。")
        return results

    if "基坑石方" in name:
        add("010102005", "direct_candidate", 0.93, "定额名称含基坑石方，与清单项目“挖基坑石方”高度一致。")
        return results

    if "沟槽石方" in name:
        add("010102006", "direct_candidate", 0.93, "定额名称含沟槽石方，与清单项目“挖沟槽石方”高度一致。")
        return results

    if "一般石方" in name:
        add("010101002", "direct_candidate", 0.90, "定额名称含一般石方且无槽/坑特征，优先对应挖单独石方。")
        return results

    if "破碎岩石" in name or "石方" in name or "岩石" in name:
        add("010101002", "feature_required", 0.76, "定额为石方/岩石破碎类，未明确基坑/沟槽部位，需项目特征判断。")
        return results

    if "土方" in name:
        add("010101001", "feature_required", 0.70, "定额名称仅泛化为土方或施工方法，需判断是否构成挖单独土方。")
        return results

    add_no_direct(0.50, "轻量规则未找到可解释的 GB/T 附录A 清单候选。", "no_candidate_bill_item")
    return results


def build_snapshots(quota_rows: Sequence[Dict[str, str]], bill_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    quota_snapshot = [{field: row.get(field, "") for field in SNAPSHOT_QUOTA_FIELDS} for row in quota_rows]
    bill_snapshot = [{field: row.get(field, "") for field in SNAPSHOT_BILL_FIELDS} for row in bill_rows]
    return quota_snapshot, bill_snapshot


def build_mapping_and_issues(
    quota_rows: Sequence[Dict[str, str]],
    bill_rows: Sequence[Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    bill_map = {row["bill_code_9"]: row for row in bill_rows}
    issues: List[Dict[str, str]] = []
    seen_issues: set = set()
    mappings: List[Dict[str, Any]] = []

    for quota in quota_rows:
        code = quota.get("source_code", "")
        name = quota.get("raw_name", "")
        unit = quota.get("unit", "")
        rules = choose_rule_mappings(quota)
        if is_supplemental(code):
            issue_once(
                issues,
                seen_issues,
                quota,
                "supplemental_quota_code",
                "Supplemental quota code must remain pending and be manually verified.",
                "medium",
                "Verify supplemental code source before mapping review approval.",
            )
        if not rules:
            issue_once(issues, seen_issues, quota, "no_candidate_bill_item", "No mapping rule produced a candidate bill item.", "high", "Manual classification required.")
            continue

        if len([rule for rule in rules if rule["bill_code_9"]]) > 1:
            issue_once(
                issues,
                seen_issues,
                quota,
                "multiple_candidate_bill_items",
                "One quota row has multiple candidate bill items.",
                "medium",
                "Manual reviewer must select or split mapping by project feature.",
            )

        for idx, rule in enumerate(rules, start=1):
            bill_code = rule["bill_code_9"]
            bill = bill_map.get(bill_code) if bill_code else None
            if bill_code and not bill:
                issue_once(issues, seen_issues, quota, "bill_reference_missing", f"Bill reference {bill_code} is missing from Appendix A input.", "high", "Fix bill reference input before review.")
                continue

            bill_unit = bill.get("unit", "") if bill else ""
            quota_dim = normalized_unit_dimension(unit)
            bill_dim = normalized_unit_dimension(bill_unit)
            if bill and quota_dim and bill_dim and quota_dim != bill_dim:
                issue_once(
                    issues,
                    seen_issues,
                    quota,
                    "unit_mismatch",
                    f"Quota unit {unit} and bill unit {bill_unit} have different dimensions.",
                    "medium",
                    "Manual reviewer must confirm conversion or reject mapping.",
                )

            mapping_type = rule["mapping_type"]
            confidence = float(rule["mapping_confidence"])
            name_for_issue = compact(name)
            if mapping_type in {"feature_required", "one_quota_to_multi_bill"}:
                issue_once(issues, seen_issues, quota, "feature_required", "Mapping depends on project feature such as部位、土类、岩石类别、运输/回填范围.", "medium", "Manual reviewer must inspect project feature context.")
            if confidence < 0.75:
                issue_once(issues, seen_issues, quota, "low_confidence", f"Mapping confidence {confidence:.2f} requires manual review.", "medium", "Do not approve without manual evidence.")
            if "transport_item_uncertain" in rule.get("remark", ""):
                issue_once(issues, seen_issues, quota, "transport_item_uncertain", "Transport/loading quota may be only a construction process rather than an independent bill item.", "medium", "Review whether it belongs under 余方弃置 or bill work content.")
            if "construction_method_only" in rule.get("remark", "") or is_construction_method_only(name_for_issue):
                issue_once(issues, seen_issues, quota, "construction_method_only", "Quota name appears to describe a construction method or auxiliary process.", "medium", "Avoid direct high-confidence mapping unless bill work content supports it.")
            if mapping_type == "no_direct_bill_item":
                issue_once(issues, seen_issues, quota, "no_candidate_bill_item", "No direct GB/T Appendix A bill item is suitable under light rules.", "high", "Manual reviewer should reject mapping or route to another standard section.")
            if name_for_issue in {"土方", "石方"} or re.fullmatch(r".*(土方|石方)$", name_for_issue) and confidence < 0.75:
                issue_once(issues, seen_issues, quota, "quota_name_too_generic", "Quota name is too generic for a confident bill-code mapping.", "medium", "Use project feature or source chapter context before mapping.")
            if mapping_type == "direct_candidate" and confidence < 0.90:
                issue_once(issues, seen_issues, quota, "possible_wrong_mapping", "Direct-looking candidate still has confidence below high-confidence band.", "low", "Spot-check before review.")

            remark_parts = ["pending_rule_semantic_candidate", rule.get("remark", "")]
            if is_supplemental(code):
                remark_parts.append("supplemental_quota_code")
            if mapping_type == "no_direct_bill_item":
                remark_parts.append("no_bill_code_written")

            mapping_id_bill = bill_code if bill_code else "NO_DIRECT_BILL"
            mappings.append(
                {
                    "mapping_id": f"MAP_A111_{code}_{mapping_id_bill}_{idx}",
                    "source_type": SOURCE_TYPE,
                    "mapping_scope": MAPPING_SCOPE,
                    "quota_reference_id": quota.get("reference_id", ""),
                    "quota_source_code": code,
                    "quota_raw_name": name,
                    "quota_standard_name_candidate": quota.get("standard_name_candidate", ""),
                    "quota_unit": unit,
                    "bill_reference_id": bill.get("bill_reference_id", "") if bill else "",
                    "bill_code_9": bill_code,
                    "bill_name": bill.get("bill_name", "") if bill else "",
                    "bill_unit": bill_unit,
                    "bill_project_feature_raw": bill.get("project_feature_raw", "") if bill else "",
                    "bill_quantity_calculation_rule": bill.get("quantity_calculation_rule", "") if bill else "",
                    "bill_work_content_raw": bill.get("work_content_raw", "") if bill else "",
                    "mapping_type": mapping_type,
                    "mapping_basis": rule["mapping_basis"],
                    "mapping_confidence": f"{confidence:.2f}",
                    "review_status": REVIEW_STATUS,
                    "reviewer": "",
                    "review_comment": "",
                    "remark": ";".join([part for part in remark_parts if part]),
                }
            )

    return mappings, issues


def confidence_bucket(value: str) -> str:
    try:
        score = float(value)
    except ValueError:
        return "invalid"
    if score >= 0.90:
        return "0.90-0.98"
    if score >= 0.75:
        return "0.75-0.89"
    if score >= 0.50:
        return "0.50-0.74"
    return "<0.50"


def count_table(counter: Counter) -> str:
    lines = ["| Item | Count |", "|---|---:|"]
    for key in sorted(counter):
        lines.append(f"| {key or '(blank)'} | {counter[key]} |")
    return "\n".join(lines)


def write_report(
    path: Path,
    bill_path: Path,
    quota_path: Path,
    pricing_path: Path,
    quota_rows: Sequence[Dict[str, str]],
    bill_rows: Sequence[Dict[str, str]],
    pricing_rows: Sequence[Dict[str, str]],
    mappings: Sequence[Dict[str, Any]],
    issues: Sequence[Dict[str, str]],
) -> None:
    mapping_type_counts = Counter(row["mapping_type"] for row in mappings)
    confidence_counts = Counter(confidence_bucket(row["mapping_confidence"]) for row in mappings)
    issue_counts = Counter(row["issue_type"] for row in issues)
    supplemental_mappings = [row for row in mappings if row["quota_source_code"] in SUPPLEMENTAL_CODES]
    low_conf = [row for row in mappings if float(row["mapping_confidence"]) < 0.75]
    manual_types = {"feature_required", "one_quota_to_multi_bill", "needs_manual_review", "no_direct_bill_item"}
    manual_rows = [row for row in mappings if row["mapping_type"] in manual_types or float(row["mapping_confidence"]) < 0.75]
    non_pending = [row for row in mappings if row["review_status"] != REVIEW_STATUS]
    approved = [row for row in mappings if row["review_status"].lower() == "approved"]
    high_direct = [row for row in mappings if row["mapping_type"] == "direct_candidate" and float(row["mapping_confidence"]) >= 0.90]
    go = bool(mappings) and not non_pending and not approved and len(bill_rows) == 12 and len(quota_rows) == 143

    lines = [
        "# Stage MAP-A111-0 Report - Quota to Bill Mapping Trial",
        "",
        "## 1. Task Scope",
        "",
        "A.1.1 土石方工程 quota-to-bill mapping candidate trial only. Outputs are pending review candidates and issues. This run does not write a database, migration, existing pipeline, cost_items, knowledge_review_records, internal_price_library, quota_to_bill_mapping table, approved records, or bill_code back into quota references.",
        "",
        "## 2. Input Files",
        "",
        f"- bill_reference_appendix_A: `{bill_path}`",
        f"- quota_reference_A111: `{quota_path}`",
        f"- quota_pricing_snapshot_A111: `{pricing_path}`",
        "",
        "## 3. Quota Reference Summary",
        "",
        f"- quota_candidate_rows: {len(quota_rows)}",
        f"- pricing_snapshot_rows: {len(pricing_rows)}",
        f"- supplemental_quota_codes: {'; '.join(sorted(SUPPLEMENTAL_CODES, key=natural_quota_key))}",
        "",
        "## 4. Bill Reference Summary",
        "",
        f"- appendix_A_bill_rows: {len(bill_rows)}",
        f"- expected_bill_codes_present: {len([row for row in bill_rows if row['bill_code_9'] in EXPECTED_BILL_CODES])} / {len(EXPECTED_BILL_CODES)}",
        "",
        "## 5. Mapping Strategy",
        "",
        "- Use lightweight semantic rules only; do not force full high-confidence coverage.",
        "- Treat excavation object words such as 基坑、沟槽、一般土方、一般石方、淤泥流砂、回填、平整场地 as primary signals.",
        "- Mark transport/loading/施工方法 rows as feature-required or manual-review candidates.",
        "- Use one-to-many candidate rows when the quota combines 基坑/沟槽 or generic 回填 possibilities.",
        "- Keep all rows as `pending`; no mapping is final.",
        "",
        "## 6. Mapping Candidate Summary",
        "",
        f"- mapping_candidate_rows: {len(mappings)}",
        f"- unique_quota_codes_in_mapping: {len(set(row['quota_source_code'] for row in mappings))}",
        f"- high_confidence_direct_candidates: {len(high_direct)}",
        f"- manual_review_candidate_rows: {len(manual_rows)}",
        "",
        "## 7. Mapping Type Distribution",
        "",
        count_table(mapping_type_counts),
        "",
        "## 8. Confidence Distribution",
        "",
        count_table(confidence_counts),
        "",
        "## 9. Low Confidence / Manual Review Items",
        "",
        f"- low_confidence_rows_below_0_75: {len(low_conf)}",
        f"- manual_review_rows: {len(manual_rows)}",
        "- Review especially transport, loading, vertical transport, backfill, and construction-method-only rows.",
        "",
        "## 10. Supplemental Quota Codes",
        "",
        f"- supplemental_mapping_rows: {len(supplemental_mappings)}",
        f"- supplemental_quota_codes_in_output: {'; '.join(sorted(set(row['quota_source_code'] for row in supplemental_mappings), key=natural_quota_key)) if supplemental_mappings else 'none'}",
        "",
        "## 11. Issues and Risks",
        "",
        f"- issue_count: {len(issues)}",
        count_table(issue_counts) if issues else "No issues generated.",
        "- Rule-based mapping can miss local cost-department conventions.",
        "- Transport and construction-method quotas may be bill work content rather than independent bill items.",
        "",
        "## 12. Manual QA Checklist",
        "",
        "- Verify `quota_source_code` is truly an A1-1-* quota code.",
        "- Verify `bill_code_9` is truly a GB/T 50854-2024 bill code.",
        "- Verify one-to-many and many-to-one relationships.",
        "- Verify `mapping_type` is reasonable.",
        "- Verify `mapping_confidence` is reasonable.",
        "- Check whether any mapping is forced.",
        "- Manually judge transport, backfill, and construction-method rows.",
        "- Verify all `review_status` values are `pending`.",
        "",
        "## 13. Go / No-Go Recommendation for Mapping Review",
        "",
        "Go for manual mapping review. Do not import or approve these candidates until cost-department review is complete." if go else "No-Go until input counts and pending status checks are fixed.",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage MAP-A111-0 quota-to-bill mapping trial.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    bill_path = project_root / BILL_REFERENCE_REL
    quota_path = project_root / QUOTA_REFERENCE_REL
    pricing_path = project_root / PRICING_REFERENCE_REL
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in [bill_path, quota_path, pricing_path]:
        if not path.exists():
            raise SystemExit(f"Input file not found: {path}")

    all_bill_rows = read_csv(bill_path)
    bill_rows = [row for row in all_bill_rows if row.get("appendix_code") == "A"]
    bill_rows.sort(key=lambda row: row.get("bill_code_9", ""))
    quota_rows = read_csv(quota_path)
    quota_rows.sort(key=lambda row: natural_quota_key(row.get("source_code", "")))
    pricing_rows = read_csv(pricing_path)

    quota_snapshot, bill_snapshot = build_snapshots(quota_rows, bill_rows)
    mappings, issues = build_mapping_and_issues(quota_rows, bill_rows)

    write_csv(output_dir / "quota_reference_A111_input_snapshot.csv", SNAPSHOT_QUOTA_FIELDS, quota_snapshot)
    write_csv(output_dir / "bill_reference_appendix_A_input_snapshot.csv", SNAPSHOT_BILL_FIELDS, bill_snapshot)
    write_csv(output_dir / "quota_to_bill_mapping_A111_candidate.csv", MAPPING_FIELDS, mappings)
    write_csv(output_dir / "quota_to_bill_mapping_A111_issues.csv", ISSUE_FIELDS, issues)
    write_report(output_dir / "stage_map_A111_report.md", bill_path, quota_path, pricing_path, quota_rows, bill_rows, pricing_rows, mappings, issues)

    print(f"bill_appendix_A_rows={len(bill_rows)}")
    print(f"quota_rows={len(quota_rows)}")
    print(f"pricing_rows={len(pricing_rows)}")
    print(f"mapping_rows={len(mappings)}")
    print(f"issue_rows={len(issues)}")
    print("mapping_type_counts=" + json.dumps(dict(Counter(row["mapping_type"] for row in mappings)), ensure_ascii=False, sort_keys=True))
    print("confidence_counts=" + json.dumps(dict(Counter(confidence_bucket(row["mapping_confidence"]) for row in mappings)), ensure_ascii=False, sort_keys=True))
    print("issue_counts=" + json.dumps(dict(Counter(row["issue_type"] for row in issues)), ensure_ascii=False, sort_keys=True))
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
