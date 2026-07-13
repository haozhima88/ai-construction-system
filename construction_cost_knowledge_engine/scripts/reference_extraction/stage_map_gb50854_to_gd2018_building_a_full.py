#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build pending N:N mapping candidates from GB/T 50854 bills to GD2018 building quotas.

This stage is deliberately append-only. It reads the locked reference baselines,
writes independent mapping artifacts, and never writes bill codes into quota rows.
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
from typing import Any, Iterable, Sequence


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs"
GB_RUN_REL = RUNS_REL / "GB50854_2024_stageB_docx_full"
EVIDENCE_RUN_REL = RUNS_REL / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1"
GD_RUN_REL = RUNS_REL / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1"
OUTPUT_REL = RUNS_REL / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"

STAGE_NAME = "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1"
FINAL_READY = "building_mapping_ready_for_web_review"
FINAL_BACKLOG = "building_mapping_ready_with_manual_review_backlog"
REVIEW_STATUS = "pending"

ROUTING_CLASSES = {
    "direct_candidate",
    "feature_required",
    "work_content_component",
    "construction_method_component",
    "measure_item",
    "conversion_component",
    "shared_component",
    "route_to_other_bill",
    "no_direct_bill_item",
    "manual_review_required",
}

# GD chapter to the closest GB/T appendix. Chapters 17-19 are intentionally
# broad: their records still need lexical evidence before an edge is emitted.
CHAPTER_APPENDIX = {
    "A.1.1": {"A"}, "A.1.2": {"B"}, "A.1.3": {"C"}, "A.1.4": {"D"},
    "A.1.5": {"E"}, "A.1.6": {"E"}, "A.1.7": {"F"}, "A.1.8": {"G"},
    "A.1.9": {"H"}, "A.1.10": {"J"}, "A.1.11": {"K"}, "A.1.12": {"L"},
    "A.1.13": {"M"}, "A.1.14": {"N"}, "A.1.15": {"P"}, "A.1.16": {"Q"},
    "A.1.17": {"Q", "R"}, "A.1.18": {"Q"}, "A.1.19": {"Q", "R"},
    "A.1.20": {"R"}, "A.1.21": {"R"}, "A.1.22": {"R"},
    "A.1.23": {"R"}, "A.1.24": {"R"}, "A.1.25": {"R"},
    "A.1.26": {"R"}, "A.1.27": {"R"},
}

STOP_TERMS = {
    "工程", "项目", "其他", "以内", "以上", "以下", "制作", "安装", "施工",
    "人工", "机械", "材料", "计算", "设计", "图示", "尺寸", "工作", "内容",
}
METHOD_TERMS = {"运输", "拆除", "开挖", "打夯", "爆破", "吊装", "焊接", "切割", "钻孔", "灌注", "喷涂"}
CONVERSION_TERMS = {"增加", "每增", "换算", "系数", "调整", "增减", "厚度", "运距", "高度", "深度"}

EDGE_FIELDS = [
    "mapping_edge_id", "bill_reference_id", "bill_code_9", "bill_name", "bill_appendix_code",
    "bill_section_code", "bill_unit", "quota_uid", "source_code", "quota_name", "volume_code",
    "quota_chapter_code", "quota_section_code", "quota_unit", "quota_pdf_page_no", "mapping_role",
    "routing_class", "semantic_score", "chapter_score", "name_score", "work_content_score",
    "feature_score", "quantity_rule_score", "unit_compatibility", "source_evidence_status",
    "risk_level", "risk_reason", "ai_mapping_explanation", "review_status", "candidate_rank",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha1(payload).hexdigest()[:16]}"


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_unit(value: str) -> str:
    value = clean(value).lower().replace("³", "3").replace("²", "2").replace("㎡", "m2")
    value = value.replace("m³", "m3").replace("m²", "m2").replace("立方米", "m3").replace("平方米", "m2")
    return re.sub(r"[^a-z0-9吨个樘套组座项宗台根榀块片扇]", "", value)


def terms(value: str) -> set[str]:
    text = re.sub(r"[\d\W_]+", "", clean(value).lower())
    result: set[str] = set()
    for size in (2, 3, 4):
        result.update(text[index:index + size] for index in range(max(0, len(text) - size + 1)))
    return {term for term in result if term not in STOP_TERMS}


def overlap(left: str, right: str) -> float:
    a, b = terms(left), terms(right)
    if not a or not b:
        return 0.0
    return min(1.0, (2.0 * len(a & b)) / (len(a) + len(b)))


def code_key(code: str) -> tuple[int, ...]:
    nums = [int(value) for value in re.findall(r"\d+", code)]
    return tuple(nums + [0] * (4 - len(nums)))


def in_code_range(code: str, start: str, end: str) -> bool:
    key = code_key(code)
    return code_key(start) <= key <= code_key(end)


def scoped_text(
    quotas: list[dict[str, str]],
    blocks: list[dict[str, str]],
    links: list[dict[str, str]],
    block_id: str,
    text_field: str,
) -> dict[str, str]:
    block_text = {row[block_id]: clean(row[text_field]) for row in blocks}
    by_volume: dict[str, list[dict[str, str]]] = defaultdict(list)
    for quota in quotas:
        by_volume[quota["volume_code"]].append(quota)
    attached: dict[str, list[str]] = defaultdict(list)
    for link in links:
        text_value = block_text.get(link.get(block_id, ""), "")
        if not text_value:
            continue
        if link.get("quota_uid"):
            attached[link["quota_uid"]].append(text_value)
            continue
        start, end = link.get("scope_start_code", ""), link.get("scope_end_code", "")
        if not start or not end:
            continue
        for quota in by_volume.get(link.get("volume_code", ""), []):
            if in_code_range(quota["source_code"], start, end):
                attached[quota["quota_uid"]].append(text_value)
    return {key: " ".join(dict.fromkeys(values)) for key, values in attached.items()}


def component_score(bill: dict[str, str], quota: dict[str, str], work: str, rule: str) -> dict[str, float]:
    bill_name = clean(bill["bill_name"])
    quota_name = clean(quota["raw_name"])
    name_score = overlap(bill_name, quota_name)
    if bill_name and quota_name and (bill_name in quota_name or quota_name in bill_name):
        name_score = max(name_score, 0.92)
    chapter_score = 1.0 if bill["appendix_code"] in CHAPTER_APPENDIX.get(quota["chapter_code"], set()) else 0.0
    work_score = overlap(clean(bill["work_content_raw"]), f"{quota_name} {work}")
    feature_score = overlap(clean(bill["project_feature_raw"]), f"{quota_name} {quota.get('specification', '')} {work}")
    quantity_score = overlap(clean(bill["quantity_calculation_rule"]), f"{quota_name} {rule}")
    left_unit, right_unit = normalize_unit(bill["unit"]), normalize_unit(quota["unit_normalized"] or quota["unit_raw"])
    unit_score = 1.0 if left_unit and right_unit and left_unit == right_unit else (0.35 if not left_unit or not right_unit else 0.0)
    semantic = (
        0.37 * name_score + 0.18 * chapter_score + 0.18 * work_score +
        0.10 * feature_score + 0.08 * quantity_score + 0.09 * unit_score
    )
    return {
        "semantic_score": min(1.0, semantic), "chapter_score": chapter_score,
        "name_score": name_score, "work_content_score": work_score,
        "feature_score": feature_score, "quantity_rule_score": quantity_score,
        "unit_compatibility": unit_score,
    }


def classify(bill: dict[str, str], quota: dict[str, str], scores: dict[str, float]) -> tuple[str, str, str, str]:
    name = clean(quota["raw_name"])
    if bill["appendix_code"] == "R" or quota["chapter_code"] in {f"A.1.{n}" for n in range(20, 28)}:
        route, role = "measure_item", "measure_candidate"
    elif any(term in name for term in CONVERSION_TERMS):
        route, role = "conversion_component", "conversion_candidate"
    elif scores["semantic_score"] < 0.42:
        route, role = "manual_review_required", "manual_review_candidate"
    elif scores["name_score"] >= 0.55:
        route, role = "direct_candidate", "primary_candidate"
    elif any(term in name for term in METHOD_TERMS):
        route, role = "construction_method_component", "component_candidate"
    elif scores["feature_score"] >= scores["work_content_score"] and scores["feature_score"] >= 0.18:
        route, role = "feature_required", "variant_candidate"
    else:
        route, role = "work_content_component", "component_candidate"
    risk = "low" if scores["semantic_score"] >= 0.66 and scores["chapter_score"] == 1 else "medium"
    reason = "semantic evidence requires human confirmation"
    if scores["semantic_score"] < 0.42 or scores["chapter_score"] == 0 or scores["unit_compatibility"] == 0:
        risk = "high"
        reason = "low semantic score, cross-chapter route, or unit mismatch"
    return route, role, risk, reason


def build(args: argparse.Namespace) -> dict[str, Any]:
    root = args.project_root.resolve()
    gb_dir, evidence_dir, gd_dir, output = root / GB_RUN_REL, root / EVIDENCE_RUN_REL, root / GD_RUN_REL, root / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)
    bills_path = gb_dir / "bill_item_reference_all_candidate.csv"
    quotas_path = gd_dir / "gd_building_quota_items.csv"
    protected = [bills_path, gb_dir / "bill_context_rules_all.csv", evidence_dir / "gb50854_evidence_link_backlog.csv"]
    protected.extend(sorted(gd_dir.glob("*.csv")))
    before = {str(path): sha256(path) for path in protected}

    bills, quotas = read_csv(bills_path), read_csv(quotas_path)
    backlog = {row["bill_reference_id"]: row for row in read_csv(evidence_dir / "gb50854_evidence_link_backlog.csv")}
    work = scoped_text(quotas, read_csv(gd_dir / "gd_building_work_content_blocks.csv"), read_csv(gd_dir / "gd_building_work_content_scope_links.csv"), "work_content_block_id", "content_text")
    rules = scoped_text(quotas, read_csv(gd_dir / "gd_building_quantity_rule_blocks.csv"), read_csv(gd_dir / "gd_building_quantity_rule_scope_links.csv"), "quantity_rule_block_id", "rule_text")

    quota_by_appendix: dict[str, list[dict[str, str]]] = defaultdict(list)
    for quota in quotas:
        for appendix in CHAPTER_APPENDIX.get(quota["chapter_code"], set()):
            quota_by_appendix[appendix].append(quota)

    edges: list[dict[str, Any]] = []
    matrix: list[dict[str, Any]] = []
    zero_rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for bill in bills:
        scored: list[tuple[float, dict[str, str], dict[str, float]]] = []
        for quota in quota_by_appendix.get(bill["appendix_code"], []):
            scores = component_score(bill, quota, work.get(quota["quota_uid"], ""), rules.get(quota["quota_uid"], ""))
            lexical = max(scores["name_score"], scores["work_content_score"], scores["feature_score"])
            if lexical >= 0.10 or scores["semantic_score"] >= 0.36:
                scored.append((scores["semantic_score"], quota, scores))
        scored.sort(key=lambda item: (-item[0], code_key(item[1]["source_code"])))
        selected = scored[:6]
        evidence = backlog.get(bill["bill_reference_id"], {})
        bill_edges: list[dict[str, Any]] = []
        for rank, (_, quota, scores) in enumerate(selected, 1):
            route, role, risk, risk_reason = classify(bill, quota, scores)
            explanation = (
                f"chapter={scores['chapter_score']:.2f}; name={scores['name_score']:.2f}; "
                f"work={scores['work_content_score']:.2f}; feature={scores['feature_score']:.2f}; "
                f"rule={scores['quantity_rule_score']:.2f}; unit={scores['unit_compatibility']:.2f}. "
                "Candidate only; cost engineer review is required."
            )
            edge = {
                "mapping_edge_id": stable_id("MAP-GB-GD", bill["bill_reference_id"], quota["quota_uid"]),
                "bill_reference_id": bill["bill_reference_id"], "bill_code_9": bill["bill_code_9"],
                "bill_name": bill["bill_name"], "bill_appendix_code": bill["appendix_code"],
                "bill_section_code": bill["section_code"], "bill_unit": bill["unit"],
                "quota_uid": quota["quota_uid"], "source_code": quota["source_code"],
                "quota_name": quota["raw_name"], "volume_code": quota["volume_code"],
                "quota_chapter_code": quota["chapter_code"], "quota_section_code": quota["section_code"],
                "quota_unit": quota["unit_normalized"] or quota["unit_raw"],
                "quota_pdf_page_no": quota["pdf_page_no"], "mapping_role": role,
                "routing_class": route, **{key: f"{value:.4f}" for key, value in scores.items()},
                "source_evidence_status": evidence.get("authority_verification_status", "pending_evidence_link"),
                "risk_level": risk, "risk_reason": risk_reason, "ai_mapping_explanation": explanation,
                "review_status": REVIEW_STATUS, "candidate_rank": rank,
            }
            bill_edges.append(edge)
            edges.append(edge)
            if risk == "high":
                issues.append({
                    "issue_id": stable_id("MAP-ISSUE", edge["mapping_edge_id"]), "issue_type": "high_risk_candidate",
                    "severity": "warning", "bill_reference_id": bill["bill_reference_id"],
                    "bill_code_9": bill["bill_code_9"], "quota_uid": quota["quota_uid"],
                    "source_code": quota["source_code"], "description": risk_reason,
                    "recommended_action": "Review semantic evidence and source PDF pages before any adoption.",
                    "review_status": REVIEW_STATUS,
                })
        counts = Counter(edge["routing_class"] for edge in bill_edges)
        matrix.append({
            "bill_reference_id": bill["bill_reference_id"], "bill_code_9": bill["bill_code_9"],
            "bill_name": bill["bill_name"], "appendix_code": bill["appendix_code"],
            "appendix_name": bill["appendix_name"], "section_code": bill["section_code"],
            "section_name": bill["section_name"], "unit": bill["unit"],
            "project_feature_raw": bill["project_feature_raw"],
            "quantity_calculation_rule": bill["quantity_calculation_rule"],
            "work_content_raw": bill["work_content_raw"], "source_heading_path": bill["source_heading_path"],
            "source_table_index": bill["source_table_index"],
            "authority_evidence_status": evidence.get("authority_verification_status", "pending_evidence_link"),
            "candidate_count": len(bill_edges),
            "candidate_quota_uids": "|".join(edge["quota_uid"] for edge in bill_edges),
            "candidate_source_codes": "|".join(edge["source_code"] for edge in bill_edges),
            "routing_class_counts_json": json.dumps(counts, ensure_ascii=False, sort_keys=True),
            "top_semantic_score": bill_edges[0]["semantic_score"] if bill_edges else "",
            "manual_review_required": "yes" if not bill_edges or any(edge["risk_level"] == "high" for edge in bill_edges) else "no",
            "review_status": REVIEW_STATUS,
        })
        if not bill_edges:
            zero_rows.append({
                "bill_reference_id": bill["bill_reference_id"], "bill_code_9": bill["bill_code_9"],
                "bill_name": bill["bill_name"], "appendix_code": bill["appendix_code"],
                "section_code": bill["section_code"], "reason": "No candidate met the lexical evidence threshold.",
                "recommended_action": "Manual routing review; do not force a 1:1 mapping.", "review_status": REVIEW_STATUS,
            })

    quota_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        quota_edges[edge["quota_uid"]].append(edge)
    routing: list[dict[str, Any]] = []
    unrouted: list[dict[str, Any]] = []
    for quota in quotas:
        candidates = sorted(quota_edges.get(quota["quota_uid"], []), key=lambda row: float(row["semantic_score"]), reverse=True)
        if not candidates:
            unrouted.append({
                "quota_uid": quota["quota_uid"], "source_code": quota["source_code"], "quota_name": quota["raw_name"],
                "volume_code": quota["volume_code"], "chapter_code": quota["chapter_code"], "section_code": quota["section_code"],
                "pdf_page_no": quota["pdf_page_no"], "routing_class": "no_direct_bill_item",
                "reason": "No bill candidate selected without forcing semantic fit.", "review_status": REVIEW_STATUS,
            })
        dominant = candidates[0]["routing_class"] if candidates else "no_direct_bill_item"
        routing.append({
            "quota_uid": quota["quota_uid"], "source_code": quota["source_code"], "quota_name": quota["raw_name"],
            "volume_code": quota["volume_code"], "chapter_code": quota["chapter_code"], "section_code": quota["section_code"],
            "pdf_page_no": quota["pdf_page_no"], "candidate_bill_count": len(candidates),
            "candidate_bill_codes": "|".join(row["bill_code_9"] for row in candidates),
            "candidate_edge_ids": "|".join(row["mapping_edge_id"] for row in candidates),
            "dominant_routing_class": dominant, "routing_status": "candidate_routed" if candidates else "unrouted",
            "review_status": REVIEW_STATUS,
        })

    shared: list[dict[str, Any]] = []
    for quota_uid, candidate_rows in sorted(quota_edges.items()):
        if len(candidate_rows) < 4:
            continue
        quota = next(row for row in quotas if row["quota_uid"] == quota_uid)
        shared.append({
            "quota_uid": quota_uid, "source_code": quota["source_code"], "quota_name": quota["raw_name"],
            "candidate_bill_count": len(candidate_rows),
            "candidate_bill_codes": "|".join(row["bill_code_9"] for row in candidate_rows),
            "shared_component_type": "multi_bill_candidate", "risk_level": "high" if len(candidate_rows) >= 10 else "medium",
            "review_status": REVIEW_STATUS,
        })

    route_counts = Counter(edge["routing_class"] for edge in edges)
    high_risk = sum(edge["risk_level"] == "high" for edge in edges)
    final_status = FINAL_BACKLOG if zero_rows or unrouted or high_risk else FINAL_READY
    dashboard = [
        {"metric_name": "final_status", "metric_value": final_status, "expected_or_threshold": f"{FINAL_READY}|{FINAL_BACKLOG}", "status": "pass", "severity": "info", "remark": ""},
        {"metric_name": "bill_count", "metric_value": len(bills), "expected_or_threshold": "472", "status": "pass" if len(bills) == 472 else "fail", "severity": "blocking", "remark": "all bills retained in matrix"},
        {"metric_name": "quota_count", "metric_value": len(quotas), "expected_or_threshold": "3700", "status": "pass" if len(quotas) == 3700 else "fail", "severity": "blocking", "remark": "consolidated input"},
        {"metric_name": "mapping_edge_count", "metric_value": len(edges), "expected_or_threshold": ">0", "status": "pass" if edges else "fail", "severity": "blocking", "remark": "independent N:N edges"},
        {"metric_name": "zero_candidate_bill_count", "metric_value": len(zero_rows), "expected_or_threshold": "retained", "status": "pass", "severity": "warning", "remark": "not forced"},
        {"metric_name": "unrouted_quota_count", "metric_value": len(unrouted), "expected_or_threshold": "retained", "status": "pass", "severity": "warning", "remark": "not forced"},
        {"metric_name": "high_risk_edge_count", "metric_value": high_risk, "expected_or_threshold": "manual review", "status": "pass", "severity": "warning", "remark": ""},
        {"metric_name": "approved_count", "metric_value": 0, "expected_or_threshold": "0", "status": "pass", "severity": "blocking", "remark": "all edges pending"},
    ]
    for route in sorted(ROUTING_CLASSES):
        dashboard.append({"metric_name": f"routing_class:{route}", "metric_value": route_counts.get(route, 0), "expected_or_threshold": ">=0", "status": "pass", "severity": "info", "remark": ""})

    matrix_fields = ["bill_reference_id", "bill_code_9", "bill_name", "appendix_code", "appendix_name", "section_code", "section_name", "unit", "project_feature_raw", "quantity_calculation_rule", "work_content_raw", "source_heading_path", "source_table_index", "authority_evidence_status", "candidate_count", "candidate_quota_uids", "candidate_source_codes", "routing_class_counts_json", "top_semantic_score", "manual_review_required", "review_status"]
    routing_fields = ["quota_uid", "source_code", "quota_name", "volume_code", "chapter_code", "section_code", "pdf_page_no", "candidate_bill_count", "candidate_bill_codes", "candidate_edge_ids", "dominant_routing_class", "routing_status", "review_status"]
    zero_fields = ["bill_reference_id", "bill_code_9", "bill_name", "appendix_code", "section_code", "reason", "recommended_action", "review_status"]
    unrouted_fields = ["quota_uid", "source_code", "quota_name", "volume_code", "chapter_code", "section_code", "pdf_page_no", "routing_class", "reason", "review_status"]
    shared_fields = ["quota_uid", "source_code", "quota_name", "candidate_bill_count", "candidate_bill_codes", "shared_component_type", "risk_level", "review_status"]
    issue_fields = ["issue_id", "issue_type", "severity", "bill_reference_id", "bill_code_9", "quota_uid", "source_code", "description", "recommended_action", "review_status"]
    dashboard_fields = ["metric_name", "metric_value", "expected_or_threshold", "status", "severity", "remark"]
    outputs = {
        "building_bill_to_quota_matrix_472.csv": (matrix_fields, matrix),
        "building_bill_to_quota_edges.csv": (EDGE_FIELDS, edges),
        "building_quota_to_bill_routing.csv": (routing_fields, routing),
        "building_zero_candidate_bills.csv": (zero_fields, zero_rows),
        "building_unrouted_quotas.csv": (unrouted_fields, unrouted),
        "building_shared_components.csv": (shared_fields, shared),
        "building_mapping_issues.csv": (issue_fields, issues),
        "building_mapping_dashboard.csv": (dashboard_fields, dashboard),
    }
    for filename, (fields, rows) in outputs.items():
        write_csv(output / filename, fields, rows)

    after = {str(path): sha256(path) for path in protected}
    unchanged = before == after
    report = f"""# {STAGE_NAME}\n\n- Final status: `{final_status}`\n- GB/T bill rows: {len(bills)}\n- GD2018 quota rows: {len(quotas)}\n- Mapping edges: {len(edges)}\n- Zero-candidate bills: {len(zero_rows)}\n- Unrouted quotas: {len(unrouted)}\n- Shared components: {len(shared)}\n- High-risk edges: {high_risk}\n- Approved count: 0\n- Protected source and baseline hashes unchanged: {str(unchanged).lower()}\n\n## Governance\n\nThis is an independent N:N candidate edge layer. No edge is approved, no bill code is written into a quota baseline, and low-confidence or unmatched records remain visible for human review. Official GB/T PDF evidence remains authoritative; missing page evidence is reported as `pending_evidence_link`.\n\n## Routing counts\n\n"""
    report += "\n".join(f"- `{name}`: {route_counts.get(name, 0)}" for name in sorted(ROUTING_CLASSES)) + "\n"
    (output / "stage_map_gb50854_to_gd2018_building_a_full_report.md").write_text(report, encoding="utf-8")
    checkpoint = {
        "stage_name": STAGE_NAME, "completed_at": datetime.now().astimezone().isoformat(),
        "final_status": final_status, "bill_count": len(bills), "quota_count": len(quotas),
        "mapping_edge_count": len(edges), "zero_candidate_bill_count": len(zero_rows),
        "unrouted_quota_count": len(unrouted), "shared_component_count": len(shared),
        "high_risk_edge_count": high_risk, "approved_count": 0,
        "routing_counts": dict(sorted(route_counts.items())), "protected_hashes_unchanged": unchanged,
        "protected_hashes": after,
    }
    (output / "checkpoint_mapping_complete.md").write_text("# Mapping checkpoint\n\n```json\n" + json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    if len(bills) != 472 or len(quotas) != 3700 or not edges or not unchanged:
        raise RuntimeError("Mapping integrity gate failed; inspect dashboard and checkpoint.")
    return checkpoint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), ensure_ascii=False, indent=2))
