#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage MAP-PREFLIGHT-A111 input readiness checks.

This script only checks whether quota and bill-reference candidate inputs are
ready for an A.1.1 mapping pilot. It does not write databases, migrations,
pipeline files, approvals, internal price libraries, quota-to-bill mappings, or
modify any source Excel/CSV inputs.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")

A111_CANDIDATE_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "GD2018_stage2R_A111_full" / "standard_cost_item_reference_A111_candidate.csv"
BILL_REFERENCE_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "GB50854_2024_stageB_docx_full" / "bill_item_reference_all_candidate.csv"
GD_EXCEL_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "source_excels" / "广东省房屋建筑与装饰工程综合定额（2018 ）.xlsx"
OUTPUT_DIR_REL = ENGINE_REL / "data" / "private" / "reference_extraction" / "runs" / "MAP_A111_preflight"

STATUS_FIELDS = ["check_item", "status", "expected", "actual", "severity", "remark"]
REQUIRED_A111_CODES = ["A1-1-1", "A1-1-67", "A1-1-126", "A1-1-137"]
REQUIRED_BILL_A_CODES = ["010101001", "010102001", "010103001"]


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})


def add_status(
    rows: List[Dict[str, str]],
    check_item: str,
    status: str,
    expected: Any,
    actual: Any,
    severity: str,
    remark: str = "",
) -> None:
    rows.append(
        {
            "check_item": check_item,
            "status": status,
            "expected": compact(expected),
            "actual": compact(actual),
            "severity": severity,
            "remark": remark,
        }
    )


def status_from_bool(ok: bool, fail_status: str = "fail") -> str:
    return "pass" if ok else fail_status


def validate_a111_candidate(path: Path, statuses: List[Dict[str, str]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "exists": path.exists(),
        "rows": 0,
        "invalid_source_code_count": "",
        "missing_required_codes": REQUIRED_A111_CODES[:],
        "supplemental_codes": [],
        "missing_raw_name_count": "",
        "missing_standard_name_candidate_count": "",
        "missing_unit_count": "",
        "non_pending_count": "",
        "ready": False,
    }
    if not path.exists():
        add_status(
            statuses,
            "a111_quota_candidate_file",
            "missing_a111_full_candidate",
            "standard_cost_item_reference_A111_candidate.csv exists",
            str(path),
            "blocker",
            "Do not start mapping. Run Stage GD2018-A111-FULL first.",
        )
        return summary

    rows = read_csv(path)
    summary["rows"] = len(rows)
    add_status(statuses, "a111_quota_candidate_file", "pass", "file exists", str(path), "info", "A.1.1 quota candidate file is readable.")
    add_status(statuses, "a111_quota_candidate_row_count", "pass" if rows else "fail", "> 0", len(rows), "blocker" if not rows else "info", "Candidate row count.")

    source_codes = [compact(row.get("source_code")) for row in rows]
    invalid_codes = [code for code in source_codes if not re.fullmatch(r"A1-1-\d+(?:-\d+)?", code)]
    summary["invalid_source_code_count"] = len(invalid_codes)
    add_status(
        statuses,
        "a111_source_code_format",
        status_from_bool(not invalid_codes),
        "all source_code values match A1-1-* or A1-1-*-*",
        len(invalid_codes),
        "blocker" if invalid_codes else "info",
        ("Invalid examples: " + "; ".join(invalid_codes[:5])) if invalid_codes else "",
    )

    source_code_set = set(source_codes)
    missing_required = [code for code in REQUIRED_A111_CODES if code not in source_code_set]
    summary["missing_required_codes"] = missing_required
    for code in REQUIRED_A111_CODES:
        add_status(
            statuses,
            f"a111_contains_{code}",
            status_from_bool(code in source_code_set),
            code,
            "present" if code in source_code_set else "missing",
            "blocker" if code not in source_code_set else "info",
            "Required boundary/control source code for A.1.1 mapping preflight.",
        )

    supplemental_codes = sorted(code for code in source_codes if re.fullmatch(r"A1-1-\d+-\d+", code))
    summary["supplemental_codes"] = supplemental_codes
    add_status(
        statuses,
        "a111_supplemental_source_codes",
        "pass" if supplemental_codes else "warn",
        "detect supplemental codes such as A1-1-56-1 or A1-1-118-1 when present",
        ";".join(supplemental_codes[:20]) if supplemental_codes else "none detected",
        "info" if supplemental_codes else "low",
        "Supplemental codes are allowed but should be reviewed during mapping.",
    )
    for code in ["A1-1-56-1", "A1-1-118-1"]:
        add_status(
            statuses,
            f"a111_contains_{code}",
            "pass" if code in source_code_set else "warn",
            f"{code} if source includes this supplement",
            "present" if code in source_code_set else "not present",
            "low",
            "Presence depends on the source candidate extraction; this is not a hard blocker.",
        )

    missing_raw_name = sum(1 for row in rows if not compact(row.get("raw_name")))
    missing_standard_name = sum(1 for row in rows if not compact(row.get("standard_name_candidate")))
    missing_unit = sum(1 for row in rows if not compact(row.get("unit")))
    non_pending = sum(1 for row in rows if compact(row.get("review_status")) != "pending")
    summary["missing_raw_name_count"] = missing_raw_name
    summary["missing_standard_name_candidate_count"] = missing_standard_name
    summary["missing_unit_count"] = missing_unit
    summary["non_pending_count"] = non_pending

    for field, count in [
        ("raw_name", missing_raw_name),
        ("standard_name_candidate", missing_standard_name),
        ("unit", missing_unit),
    ]:
        add_status(
            statuses,
            f"a111_missing_{field}",
            status_from_bool(count == 0),
            "0 missing",
            count,
            "blocker" if count else "info",
            f"{field} must be available before mapping review.",
        )
    add_status(
        statuses,
        "a111_review_status_pending",
        status_from_bool(non_pending == 0),
        "all pending",
        non_pending,
        "blocker" if non_pending else "info",
        "Do not map approved/final status from extraction candidates.",
    )

    summary["ready"] = (
        bool(rows)
        and not invalid_codes
        and not missing_required
        and missing_raw_name == 0
        and missing_standard_name == 0
        and missing_unit == 0
        and non_pending == 0
    )
    return summary


def validate_bill_reference(path: Path, statuses: List[Dict[str, str]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "exists": path.exists(),
        "appendix_a_rows": 0,
        "invalid_bill_code_count": "",
        "missing_required_bill_codes": REQUIRED_BILL_A_CODES[:],
        "non_pending_count": "",
        "ready": False,
    }
    if not path.exists():
        add_status(
            statuses,
            "gb50854_bill_reference_file",
            "missing",
            "bill_item_reference_all_candidate.csv exists",
            str(path),
            "blocker",
            "Cannot validate Appendix A bill references.",
        )
        return summary

    rows = read_csv(path)
    appendix_a = [row for row in rows if compact(row.get("appendix_code")) == "A"]
    summary["appendix_a_rows"] = len(appendix_a)
    add_status(statuses, "gb50854_bill_reference_file", "pass", "file exists", str(path), "info", "Full bill reference candidate file is readable.")
    add_status(
        statuses,
        "gb50854_appendix_A_row_count",
        status_from_bool(len(appendix_a) == 12),
        "12 Appendix A rows",
        len(appendix_a),
        "blocker" if len(appendix_a) != 12 else "info",
        "Appendix A should contain 12 bill items from Stage B-DOCX-2.",
    )

    codes = [compact(row.get("bill_code_9")) for row in appendix_a]
    invalid_codes = [code for code in codes if not re.fullmatch(r"\d{9}", code)]
    summary["invalid_bill_code_count"] = len(invalid_codes)
    add_status(
        statuses,
        "gb50854_appendix_A_bill_code_9_format",
        status_from_bool(not invalid_codes),
        "all bill_code_9 values are 9 digits",
        len(invalid_codes),
        "blocker" if invalid_codes else "info",
        ("Invalid examples: " + "; ".join(invalid_codes[:5])) if invalid_codes else "",
    )

    code_set = set(codes)
    missing_required = [code for code in REQUIRED_BILL_A_CODES if code not in code_set]
    summary["missing_required_bill_codes"] = missing_required
    for code in REQUIRED_BILL_A_CODES:
        add_status(
            statuses,
            f"gb50854_appendix_A_contains_{code}",
            status_from_bool(code in code_set),
            code,
            "present" if code in code_set else "missing",
            "blocker" if code not in code_set else "info",
            "Required representative bill code for A.1.1 mapping preflight.",
        )

    non_pending = sum(1 for row in appendix_a if compact(row.get("review_status")) != "pending")
    summary["non_pending_count"] = non_pending
    add_status(
        statuses,
        "gb50854_appendix_A_review_status_pending",
        status_from_bool(non_pending == 0),
        "all pending",
        non_pending,
        "blocker" if non_pending else "info",
        "Bill reference candidates must remain pending before human review.",
    )

    summary["ready"] = len(appendix_a) == 12 and not invalid_codes and not missing_required and non_pending == 0
    return summary


def decide_recommendation(a111: Dict[str, Any], bill: Dict[str, Any]) -> str:
    if not bill["exists"]:
        return "blocked_by_missing_inputs"
    if not a111["exists"]:
        return "need_generate_A111_quota_candidate_first"
    if a111["ready"] and bill["ready"]:
        return "ready_for_mapping"
    return "blocked_by_missing_inputs"


def write_report(
    path: Path,
    project_root: Path,
    a111_path: Path,
    bill_path: Path,
    excel_path: Path,
    statuses: Sequence[Dict[str, str]],
    a111: Dict[str, Any],
    bill: Dict[str, Any],
    recommendation: str,
) -> None:
    blocking = [row for row in statuses if row["severity"] == "blocker" and row["status"] not in {"pass"}]
    status_counts = Counter(row["status"] for row in statuses)
    severity_counts = Counter(row["severity"] for row in statuses)
    lines = [
        "# Stage MAP-PREFLIGHT-A111 Report",
        "",
        "## 1. Task Scope",
        "",
        "Preflight check for the planned A.1.1 quota-to-bill mapping pilot. This run only checks whether required candidate inputs are available and structurally ready. It does not write a database, migration, pipeline, approved data, internal_price_library, quota_to_bill_mapping, or any A1-1-* to bill_code mapping.",
        "",
        "## 2. Input Files Checked",
        "",
        f"- project_root: `{project_root}`",
        f"- Guangdong quota Excel: `{excel_path}`",
        f"- A.1.1 quota candidate: `{a111_path}`",
        f"- GB/T 50854 bill reference: `{bill_path}`",
        f"- status_counts: {dict(status_counts)}",
        f"- severity_counts: {dict(severity_counts)}",
        "",
        "## 3. A.1.1 Quota Candidate Availability",
        "",
        f"- file_exists: {str(a111['exists']).lower()}",
        f"- candidate_rows: {a111['rows']}",
        f"- invalid_source_code_count: {a111['invalid_source_code_count']}",
        f"- missing_required_codes: {'; '.join(a111['missing_required_codes']) if a111['missing_required_codes'] else 'none'}",
        f"- supplemental_source_codes_detected: {'; '.join(a111['supplemental_codes'][:20]) if a111['supplemental_codes'] else 'none'}",
        f"- missing_raw_name_count: {a111['missing_raw_name_count']}",
        f"- missing_standard_name_candidate_count: {a111['missing_standard_name_candidate_count']}",
        f"- missing_unit_count: {a111['missing_unit_count']}",
        f"- non_pending_review_status_count: {a111['non_pending_count']}",
        "",
        "## 4. Appendix A Bill Reference Availability",
        "",
        f"- file_exists: {str(bill['exists']).lower()}",
        f"- appendix_A_rows: {bill['appendix_a_rows']}",
        f"- invalid_bill_code_9_count: {bill['invalid_bill_code_count']}",
        f"- missing_required_bill_codes: {'; '.join(bill['missing_required_bill_codes']) if bill['missing_required_bill_codes'] else 'none'}",
        f"- non_pending_review_status_count: {bill['non_pending_count']}",
        "",
        "## 5. Blocking Issues",
        "",
    ]
    if blocking:
        lines.extend(["| Check Item | Status | Expected | Actual | Remark |", "|---|---|---|---|---|"])
        for row in blocking:
            lines.append(f"| {row['check_item']} | {row['status']} | {row['expected']} | {row['actual']} | {row['remark']} |")
    else:
        lines.append("No blocking issues detected by preflight checks.")
    lines.extend(
        [
            "",
            "## 6. Recommendation",
            "",
            f"`{recommendation}`",
            "",
        ]
    )
    if recommendation == "need_generate_A111_quota_candidate_first":
        lines.append("Next step: execute Stage GD2018-A111-FULL to generate the full A.1.1 quota candidate file before any mapping pilot.")
    elif recommendation == "ready_for_mapping":
        lines.append("Next step: proceed to the A.1.1 mapping pilot design, still keeping all outputs as pending review candidates.")
    else:
        lines.append("Next step: resolve the blocking input or structural issues listed above before mapping.")
    lines.extend(["", f"Generated at: {datetime.now().isoformat(timespec='seconds')}"])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MAP-PREFLIGHT-A111 readiness checks.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root
    output_dir = project_root / OUTPUT_DIR_REL
    output_dir.mkdir(parents=True, exist_ok=True)

    a111_path = project_root / A111_CANDIDATE_REL
    bill_path = project_root / BILL_REFERENCE_REL
    excel_path = project_root / GD_EXCEL_REL
    statuses: List[Dict[str, str]] = []

    add_status(
        statuses,
        "gd2018_source_excel",
        "pass" if excel_path.exists() else "missing",
        "Guangdong quota source Excel exists",
        str(excel_path),
        "info" if excel_path.exists() else "blocker",
        "Source Excel is not modified by this preflight.",
    )

    a111_summary = validate_a111_candidate(a111_path, statuses)
    bill_summary = validate_bill_reference(bill_path, statuses)
    recommendation = decide_recommendation(a111_summary, bill_summary)
    add_status(
        statuses,
        "map_a111_preflight_recommendation",
        recommendation,
        "one of ready_for_mapping / need_generate_A111_quota_candidate_first / blocked_by_missing_inputs",
        recommendation,
        "blocker" if recommendation != "ready_for_mapping" else "info",
        "This preflight does not perform mapping.",
    )

    write_csv(output_dir / "a111_preflight_status.csv", statuses)
    write_report(
        output_dir / "a111_preflight_report.md",
        project_root,
        a111_path,
        bill_path,
        excel_path,
        statuses,
        a111_summary,
        bill_summary,
        recommendation,
    )

    print(f"status_rows={len(statuses)}")
    print(f"a111_candidate_exists={str(a111_summary['exists']).lower()}")
    print(f"bill_reference_exists={str(bill_summary['exists']).lower()}")
    print(f"bill_appendix_a_rows={bill_summary['appendix_a_rows']}")
    print(f"recommendation={recommendation}")
    print(f"output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
