#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare WorkBuddy vs Codex Appendix A bill item extraction outputs.

This script is read-only for Codex baseline and WorkBuddy original outputs. It
only writes comparison artifacts into the WorkBuddy benchmark run directory.
It does not write databases, modify pipeline code, generate approvals, or build
quota_to_bill_mapping.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

PROJECT_ROOT = Path(r"E:\workspace\01_Projects\ai-construction-system\construction_cost_knowledge_engine")

COMPARE_FIELDS = [
    "bill_code_9",
    "bill_name",
    "section_code",
    "section_name",
    "table_code",
    "table_name",
    "project_feature_raw",
    "unit",
    "quantity_calculation_rule",
    "work_content_raw",
    "review_status",
]

NORMALIZED_FIELDS = [
    "bill_code_9",
    "bill_name",
    "section_code",
    "section_name",
    "table_code",
    "table_name",
    "project_feature_raw",
    "unit",
    "quantity_calculation_rule",
    "work_content_raw",
    "review_status",
    "source_row_id",
    "source_file",
    "remark",
    "normalization_remark",
]

COMPARISON_FIELDS = [
    "bill_code_9",
    "compare_status",
    "codex_exists",
    "workbuddy_exists",
    "bill_name_match",
    "unit_match",
    "project_feature_match_level",
    "quantity_rule_match_level",
    "work_content_match_level",
    "codex_bill_name",
    "workbuddy_bill_name",
    "codex_unit",
    "workbuddy_unit",
    "codex_project_feature_raw",
    "workbuddy_project_feature_raw",
    "codex_quantity_calculation_rule",
    "workbuddy_quantity_calculation_rule",
    "codex_work_content_raw",
    "workbuddy_work_content_raw",
    "manual_review_required",
    "remark",
]

ISSUE_FIELDS = [
    "issue_id",
    "bill_code_9",
    "issue_type",
    "issue_detail",
    "severity",
    "codex_value",
    "workbuddy_value",
    "suggested_action",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    text = text.replace("\u3000", " ")
    return re.sub(r"[ \t]+", " ", text)


def compact(value: Any) -> str:
    return re.sub(r"\s+", "", norm_text(value))


def punctuation_light(value: Any) -> str:
    text = compact(value)
    table = str.maketrans(
        {
            "，": ",",
            "。": ".",
            "；": ";",
            "：": ":",
            "（": "(",
            "）": ")",
            "、": ",",
            "．": ".",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "㎥": "m3",
            "m³": "m3",
            "㎡": "m2",
        }
    )
    return text.translate(table)


def normalize_unit(value: Any) -> str:
    text = compact(value)
    return (
        text.replace("㎥", "m3")
        .replace("m³", "m3")
        .replace("M3", "m3")
        .replace("㎡", "m2")
        .replace("M2", "m2")
    )


def compare_level(codex_value: Any, workbuddy_value: Any, unit: bool = False) -> str:
    c = norm_text(codex_value)
    w = norm_text(workbuddy_value)
    if not c and not w:
        return "both_missing"
    if not c or not w:
        return "missing"
    if c == w:
        return "exact"
    if compact(c) == compact(w):
        return "whitespace_only"
    if unit and normalize_unit(c) == normalize_unit(w):
        return "unit_equivalent"
    if punctuation_light(c) == punctuation_light(w):
        return "minor_punctuation"
    return "different"


def is_core_match(level: str) -> bool:
    return level in {"exact", "whitespace_only", "minor_punctuation", "unit_equivalent"}


def is_bill_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{9}", norm_text(value)))


def expected_section_for_code(code: str) -> Tuple[str, str, str, str]:
    if code.startswith("010101"):
        return "A.1", "单独土石方", "表A.1.1", "单独土石方"
    if code.startswith("010102"):
        return "A.2", "基础土石方", "表A.2.1", "基础土石方"
    if code.startswith("010103"):
        return "A.3", "平整场地及其他", "表A.3.1", "平整场地及其他"
    return "", "", "", ""


def standardize_workbuddy(rows: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        code = norm_text(row.get("bill_code_9", ""))
        norm_row = {field: norm_text(row.get(field, "")) for field in COMPARE_FIELDS}
        norm_row["bill_code_9"] = code
        norm_row["source_row_id"] = norm_text(row.get("wb_row_id", f"workbuddy_row_{idx}"))
        norm_row["source_file"] = norm_text(row.get("source_file", ""))
        norm_row["remark"] = norm_text(row.get("remark", ""))
        remarks = []
        if "\r" in str(row.get("work_content_raw", "")):
            remarks.append("normalized_crlf")
        if not code:
            remarks.append("missing_bill_code")
        elif not is_bill_code(code):
            remarks.append("invalid_bill_code")
        if re.search(r"A1-1-\d+", json.dumps(row, ensure_ascii=False)):
            remarks.append("A1_code_mixed_in")
        norm_row["normalization_remark"] = ";".join(remarks)
        normalized.append(norm_row)
    return normalized


def by_code(rows: Sequence[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    for row in rows:
        code = norm_text(row.get("bill_code_9", ""))
        if code and code not in result:
            result[code] = row
    return result


def add_issue(issues: List[Dict[str, Any]], code: str, issue_type: str, detail: str, severity: str, codex_value: Any = "", workbuddy_value: Any = "", action: str = "") -> None:
    issues.append(
        {
            "issue_id": f"COMPARE_A_{len(issues) + 1:03d}",
            "bill_code_9": code,
            "issue_type": issue_type,
            "issue_detail": detail,
            "severity": severity,
            "codex_value": norm_text(codex_value),
            "workbuddy_value": norm_text(workbuddy_value),
            "suggested_action": action or "Manual review required before downstream use.",
        }
    )


def validate_input_rows(label: str, rows: Sequence[Dict[str, str]], issues: List[Dict[str, Any]]) -> None:
    counts = Counter(norm_text(row.get("bill_code_9", "")) for row in rows)
    if len(rows) != 12:
        add_issue(issues, "", "unexpected_row_count", f"{label} row count is {len(rows)}, expected 12.", "high", action="Check extraction completeness.")
    for idx, row in enumerate(rows, start=1):
        code = norm_text(row.get("bill_code_9", ""))
        if not code:
            add_issue(issues, "", "missing_bill_code", f"{label} row {idx} has no bill_code_9.", "critical", workbuddy_value=json.dumps(row, ensure_ascii=False), action="Do not use this row until code is resolved.")
            continue
        if not is_bill_code(code):
            add_issue(issues, code, "invalid_bill_code", f"{label} row {idx} bill_code_9 is not 9 digits.", "critical", workbuddy_value=code, action="Correct or exclude invalid bill code.")
        if counts[code] > 1:
            add_issue(issues, code, "duplicate_bill_code", f"{label} contains duplicate bill_code_9.", "high", action="Deduplicate before full-stage use.")
        if re.search(r"A1-1-\d+", json.dumps(row, ensure_ascii=False)):
            add_issue(issues, code, "A1_code_mixed_in", f"{label} row {idx} contains A1-1-* text.", "critical", workbuddy_value=json.dumps(row, ensure_ascii=False), action="Remove quota code contamination.")
        expected_section, _, expected_table, _ = expected_section_for_code(code)
        if expected_section and norm_text(row.get("section_code", "")) != expected_section:
            add_issue(issues, code, "wrong_section", f"{label} section_code does not match code prefix.", "medium", codex_value=expected_section, workbuddy_value=row.get("section_code", ""), action="Verify section classification.")
        if norm_text(row.get("section_code", "")) == "A.4":
            add_issue(issues, code, "A4_rule_mixed_into_bill_items", f"{label} has A.4 row in bill item table.", "critical", action="Move A.4 row to context rules, not bill item candidates.")
        if expected_table and norm_text(row.get("table_code", "")) != expected_table:
            add_issue(issues, code, "wrong_section", f"{label} table_code does not match code prefix.", "low", codex_value=expected_table, workbuddy_value=row.get("table_code", ""), action="Verify table metadata.")
        for field, issue_type in [
            ("bill_name", "missing_bill_name"),
            ("unit", "missing_unit"),
            ("project_feature_raw", "feature_missing"),
            ("quantity_calculation_rule", "quantity_rule_missing"),
            ("work_content_raw", "work_content_missing"),
        ]:
            if not norm_text(row.get(field, "")):
                add_issue(issues, code, issue_type, f"{label} missing {field}.", "high", action="Fill from verified source before use.")


def compare_rows(codex_rows: Sequence[Dict[str, str]], workbuddy_rows: Sequence[Dict[str, str]], issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    codex = by_code(codex_rows)
    workbuddy = by_code(workbuddy_rows)
    codes = sorted(set(codex) | set(workbuddy))
    result: List[Dict[str, Any]] = []
    for code in codes:
        c = codex.get(code)
        w = workbuddy.get(code)
        if not c:
            add_issue(issues, code, "missing_bill_code", "Code exists in WorkBuddy but missing in Codex baseline.", "high", workbuddy_value=code, action="Review Codex baseline coverage.")
            result.append(
                {
                    "bill_code_9": code,
                    "compare_status": "code_missing_in_codex",
                    "codex_exists": "false",
                    "workbuddy_exists": "true",
                    "bill_name_match": "missing",
                    "unit_match": "missing",
                    "project_feature_match_level": "missing",
                    "quantity_rule_match_level": "missing",
                    "work_content_match_level": "missing",
                    "codex_bill_name": "",
                    "workbuddy_bill_name": w.get("bill_name", ""),
                    "codex_unit": "",
                    "workbuddy_unit": w.get("unit", ""),
                    "codex_project_feature_raw": "",
                    "workbuddy_project_feature_raw": w.get("project_feature_raw", ""),
                    "codex_quantity_calculation_rule": "",
                    "workbuddy_quantity_calculation_rule": w.get("quantity_calculation_rule", ""),
                    "codex_work_content_raw": "",
                    "workbuddy_work_content_raw": w.get("work_content_raw", ""),
                    "manual_review_required": "true",
                    "remark": "Code missing in Codex baseline.",
                }
            )
            continue
        if not w:
            add_issue(issues, code, "missing_bill_code", "Code exists in Codex baseline but missing in WorkBuddy.", "high", codex_value=code, action="Review WorkBuddy extraction coverage.")
            result.append(
                {
                    "bill_code_9": code,
                    "compare_status": "code_missing_in_workbuddy",
                    "codex_exists": "true",
                    "workbuddy_exists": "false",
                    "bill_name_match": "missing",
                    "unit_match": "missing",
                    "project_feature_match_level": "missing",
                    "quantity_rule_match_level": "missing",
                    "work_content_match_level": "missing",
                    "codex_bill_name": c.get("bill_name", ""),
                    "workbuddy_bill_name": "",
                    "codex_unit": c.get("unit", ""),
                    "workbuddy_unit": "",
                    "codex_project_feature_raw": c.get("project_feature_raw", ""),
                    "workbuddy_project_feature_raw": "",
                    "codex_quantity_calculation_rule": c.get("quantity_calculation_rule", ""),
                    "workbuddy_quantity_calculation_rule": "",
                    "codex_work_content_raw": c.get("work_content_raw", ""),
                    "workbuddy_work_content_raw": "",
                    "manual_review_required": "true",
                    "remark": "Code missing in WorkBuddy output.",
                }
            )
            continue

        name_level = compare_level(c.get("bill_name", ""), w.get("bill_name", ""))
        unit_level = compare_level(c.get("unit", ""), w.get("unit", ""), unit=True)
        feature_level = compare_level(c.get("project_feature_raw", ""), w.get("project_feature_raw", ""))
        quantity_level = compare_level(c.get("quantity_calculation_rule", ""), w.get("quantity_calculation_rule", ""))
        work_level = compare_level(c.get("work_content_raw", ""), w.get("work_content_raw", ""))
        core_levels = [name_level, unit_level, feature_level, quantity_level, work_level]

        status = "match"
        manual_review = "false"
        remark_parts = []
        if any(level == "missing" for level in core_levels):
            status = "field_missing"
            manual_review = "true"
        elif all(is_core_match(level) for level in core_levels):
            if any(level != "exact" for level in core_levels):
                status = "minor_text_difference"
                remark_parts.append("Core fields differ only by whitespace/punctuation/unit notation normalization.")
        else:
            status = "needs_manual_review"
            manual_review = "true"

        if name_level == "different":
            add_issue(issues, code, "name_mismatch", "bill_name differs between Codex and WorkBuddy.", "medium", c.get("bill_name", ""), w.get("bill_name", ""), "Manual compare against source DOCX.")
        if unit_level not in {"exact", "unit_equivalent"}:
            add_issue(issues, code, "unit_mismatch", "unit differs between Codex and WorkBuddy.", "medium", c.get("unit", ""), w.get("unit", ""), "Manual compare against source DOCX.")
        if feature_level == "missing":
            add_issue(issues, code, "feature_missing", "project_feature_raw missing on one side.", "high", c.get("project_feature_raw", ""), w.get("project_feature_raw", ""))
        if quantity_level == "missing":
            add_issue(issues, code, "quantity_rule_missing", "quantity_calculation_rule missing on one side.", "high", c.get("quantity_calculation_rule", ""), w.get("quantity_calculation_rule", ""))
        if work_level == "missing":
            add_issue(issues, code, "work_content_missing", "work_content_raw missing on one side.", "high", c.get("work_content_raw", ""), w.get("work_content_raw", ""))

        codex_remark = norm_text(c.get("remark", ""))
        workbuddy_remark = norm_text(w.get("remark", ""))
        if codex_remark != workbuddy_remark and all(is_core_match(level) for level in core_levels):
            add_issue(issues, code, "remark_difference_only", "Only remark differs while core fields match.", "info", codex_remark, workbuddy_remark, "No blocker; preserve as note for reviewer.")
            if status == "match":
                remark_parts.append("remark_only_difference")

        result.append(
            {
                "bill_code_9": code,
                "compare_status": status,
                "codex_exists": "true",
                "workbuddy_exists": "true",
                "bill_name_match": name_level,
                "unit_match": unit_level,
                "project_feature_match_level": feature_level,
                "quantity_rule_match_level": quantity_level,
                "work_content_match_level": work_level,
                "codex_bill_name": c.get("bill_name", ""),
                "workbuddy_bill_name": w.get("bill_name", ""),
                "codex_unit": c.get("unit", ""),
                "workbuddy_unit": w.get("unit", ""),
                "codex_project_feature_raw": c.get("project_feature_raw", ""),
                "workbuddy_project_feature_raw": w.get("project_feature_raw", ""),
                "codex_quantity_calculation_rule": c.get("quantity_calculation_rule", ""),
                "workbuddy_quantity_calculation_rule": w.get("quantity_calculation_rule", ""),
                "codex_work_content_raw": c.get("work_content_raw", ""),
                "workbuddy_work_content_raw": w.get("work_content_raw", ""),
                "manual_review_required": manual_review,
                "remark": ";".join(remark_parts) if remark_parts else "",
            }
        )
    return result


def compare_rules(codex_rules: Sequence[Dict[str, str]], workbuddy_rules: Sequence[Dict[str, str]], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    codex_codes = {norm_text(row.get("rule_code", "")) for row in codex_rules if norm_text(row.get("rule_code", ""))}
    workbuddy_codes = {norm_text(row.get("rule_code", "")) for row in workbuddy_rules if norm_text(row.get("rule_code", ""))}
    missing_workbuddy = sorted(codex_codes - workbuddy_codes)
    missing_codex = sorted(workbuddy_codes - codex_codes)
    if missing_workbuddy:
        add_issue(issues, "", "field_missing", "A.4 rule codes missing in WorkBuddy context rules: " + ";".join(missing_workbuddy), "medium", action="Review context rule extraction.")
    if missing_codex:
        add_issue(issues, "", "field_missing", "A.4 rule codes missing in Codex context rules: " + ";".join(missing_codex), "medium", action="Review Codex context rule extraction.")
    return {
        "codex_rule_count": len(codex_rules),
        "workbuddy_rule_count": len(workbuddy_rules),
        "rule_code_match": not missing_workbuddy and not missing_codex,
        "missing_in_workbuddy": missing_workbuddy,
        "missing_in_codex": missing_codex,
    }


def markdown_count_table(counter: Counter) -> str:
    lines = ["| Item | Count |", "|---|---:|"]
    for key in sorted(counter):
        lines.append(f"| {key} | {counter[key]} |")
    return "\n".join(lines)


def write_report(
    path: Path,
    paths: Dict[str, Path],
    codex_rows: Sequence[Dict[str, str]],
    workbuddy_rows: Sequence[Dict[str, str]],
    normalized_rows: Sequence[Dict[str, Any]],
    comparison_rows: Sequence[Dict[str, Any]],
    issues: Sequence[Dict[str, Any]],
    rule_summary: Dict[str, Any],
) -> None:
    compare_counts = Counter(row["compare_status"] for row in comparison_rows)
    issue_counts = Counter(row["issue_type"] for row in issues)
    manual = [row for row in comparison_rows if row["manual_review_required"] == "true"]
    coverage_codes = sorted(row["bill_code_9"] for row in comparison_rows)
    core_match_count = sum(1 for row in comparison_rows if row["compare_status"] in {"match", "minor_text_difference"})
    remark_only_count = sum(1 for row in issues if row["issue_type"] == "remark_difference_only")
    missing_fields = Counter()
    for row in normalized_rows:
        for field in ["bill_name", "unit", "project_feature_raw", "quantity_calculation_rule", "work_content_raw", "review_status"]:
            if not norm_text(row.get(field, "")):
                missing_fields[field] += 1

    lines = [
        "# WorkBuddy vs Codex Comparison Report - GB/T 50854-2024 Appendix A",
        "",
        "## 1. Task Scope",
        "",
        "Compare WorkBuddy blind-test extraction against the Codex Appendix A baseline by `bill_code_9`. This run does not modify either source output, write databases, create approvals, generate internal_price_library, or build quota_to_bill_mapping.",
        "",
        "## 2. Input Files",
        "",
        f"- Codex bill items: `{paths['codex_candidates']}`",
        f"- Codex A.4 rules: `{paths['codex_rules']}`",
        f"- WorkBuddy bill items: `{paths['workbuddy_candidates']}`",
        f"- WorkBuddy A.4 rules: `{paths['workbuddy_rules']}`",
        f"- WorkBuddy issues: `{paths['workbuddy_issues']}`",
        "",
        "## 3. Row Count Comparison",
        "",
        f"- Codex candidate rows: {len(codex_rows)}",
        f"- WorkBuddy candidate rows: {len(workbuddy_rows)}",
        f"- Normalized WorkBuddy rows: {len(normalized_rows)}",
        f"- Comparison rows: {len(comparison_rows)}",
        f"- Codex A.4 rule rows: {rule_summary['codex_rule_count']}",
        f"- WorkBuddy A.4 rule rows: {rule_summary['workbuddy_rule_count']}",
        "",
        "## 4. Code Coverage Comparison",
        "",
        f"- Compared bill_code_9 values: {', '.join(coverage_codes)}",
        "- Missing in WorkBuddy: " + (", ".join(row["bill_code_9"] for row in comparison_rows if row["compare_status"] == "code_missing_in_workbuddy") or "none"),
        "- Missing in Codex: " + (", ".join(row["bill_code_9"] for row in comparison_rows if row["compare_status"] == "code_missing_in_codex") or "none"),
        f"- A.4 rule code coverage match: {rule_summary['rule_code_match']}",
        "",
        "## 5. Core Field Comparison",
        "",
        markdown_count_table(compare_counts),
        "",
        f"- Core match/minor-difference rows: {core_match_count} / {len(comparison_rows)}",
        "",
        "## 6. Remark Field Difference",
        "",
        f"- remark-only differences: {remark_only_count}",
        "- Remark-only differences are non-blocking when all core fields match.",
        "",
        "## 7. Field Completeness Comparison",
        "",
        markdown_count_table(missing_fields) if missing_fields else "No missing core fields in normalized WorkBuddy rows.",
        "",
        "## 8. Manual Review Required Items",
        "",
        "- Manual review required bill codes: " + (", ".join(row["bill_code_9"] for row in manual) or "none"),
        "",
        "Issue summary:",
        "",
        markdown_count_table(issue_counts) if issue_counts else "No comparison issues generated.",
        "",
        "## 9. Final Recommendation",
        "",
        "The WorkBuddy output matches Codex on all 12 Appendix A bill item core fields if all comparison statuses are `match` or `minor_text_difference`. Remark-only differences should be treated as reviewer notes, not extraction failures. Proceed only after manual spot-checking the source DOCX for the 12 compared rows.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare WorkBuddy vs Codex GB/T 50854-2024 Appendix A outputs.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root
    codex_dir = root / "data" / "private" / "reference_extraction" / "runs" / "GB50854_2024_stageB_docx_A"
    wb_dir = root / "data" / "private" / "reference_extraction" / "runs" / "GB50854_2024_workbuddy_benchmark_A"
    paths = {
        "codex_candidates": codex_dir / "bill_item_reference_A_candidate.csv",
        "codex_rules": codex_dir / "bill_context_rules_A.csv",
        "workbuddy_candidates": wb_dir / "workbuddy_bill_item_reference_A_candidate.csv",
        "workbuddy_rules": wb_dir / "workbuddy_bill_context_rules_A.csv",
        "workbuddy_issues": wb_dir / "workbuddy_extraction_issues_A.csv",
        "workbuddy_normalized": wb_dir / "workbuddy_normalized_A.csv",
        "comparison_result": wb_dir / "comparison_result_A.csv",
        "comparison_issues": wb_dir / "comparison_issues_A.csv",
        "report": wb_dir / "workbuddy_vs_codex_report_A.md",
    }
    for key in ["codex_candidates", "codex_rules", "workbuddy_candidates", "workbuddy_rules", "workbuddy_issues"]:
        if not paths[key].exists():
            raise SystemExit(f"Required input missing: {paths[key]}")

    codex_rows = read_csv(paths["codex_candidates"])
    codex_rules = read_csv(paths["codex_rules"])
    workbuddy_original = read_csv(paths["workbuddy_candidates"])
    workbuddy_rules = read_csv(paths["workbuddy_rules"])
    _workbuddy_issues = read_csv(paths["workbuddy_issues"])

    normalized_workbuddy = standardize_workbuddy(workbuddy_original)
    issues: List[Dict[str, Any]] = []
    validate_input_rows("Codex baseline", codex_rows, issues)
    validate_input_rows("WorkBuddy normalized", normalized_workbuddy, issues)
    comparison_rows = compare_rows(codex_rows, normalized_workbuddy, issues)
    rule_summary = compare_rules(codex_rules, workbuddy_rules, issues)

    write_csv(paths["workbuddy_normalized"], NORMALIZED_FIELDS, normalized_workbuddy)
    write_csv(paths["comparison_result"], COMPARISON_FIELDS, comparison_rows)
    write_csv(paths["comparison_issues"], ISSUE_FIELDS, issues)
    write_report(paths["report"], paths, codex_rows, workbuddy_original, normalized_workbuddy, comparison_rows, issues, rule_summary)

    print(f"codex_rows={len(codex_rows)}")
    print(f"workbuddy_rows={len(workbuddy_original)}")
    print(f"normalized_rows={len(normalized_workbuddy)}")
    print(f"comparison_rows={len(comparison_rows)}")
    print(f"issue_rows={len(issues)}")
    print("compare_status_counts=" + json.dumps(dict(Counter(row["compare_status"] for row in comparison_rows)), ensure_ascii=False, sort_keys=True))
    print("issue_counts=" + json.dumps(dict(Counter(row["issue_type"] for row in issues)), ensure_ascii=False, sort_keys=True))
    print(f"output_dir={wb_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
