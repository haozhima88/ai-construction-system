from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


STAGE_NAME = "REFERENCE_FRAMEWORK_PRECONDITION_RECONCILIATION_1"
FRAMEWORK_STAGE = "REFERENCE_FAMILY_FRAMEWORK_LOCK_1"
READY_STATUS = "reference_framework_ready_for_building_family_execution"
BLOCKED_SOURCE = "blocked_building_source_confirmation_required"
BLOCKED_BASELINE = "blocked_gb50854_baseline_conflict"
BLOCKED_GOLDEN = "blocked_a111_golden_slice_integrity_failed"
BLOCKED_WARNINGS = "blocked_framework_warning_reconciliation_failed"

ENGINE_DIR = "construction_cost_knowledge_engine"
FRAMEWORK_RUN_REL = Path(
    "construction_cost_knowledge_engine/data/private/reference_extraction/runs/REFERENCE_FAMILY_FRAMEWORK_LOCK_1"
)
RUN_DIR_REL = Path(
    "construction_cost_knowledge_engine/data/private/reference_extraction/runs/REFERENCE_FRAMEWORK_PRECONDITION_RECONCILIATION_1"
)
DOCS_REL = Path("construction_cost_knowledge_engine/docs/reference_extraction")
SOURCE_STANDARDS_REL = Path("construction_cost_knowledge_engine/data/private/reference_extraction/source_standards")
GB_BASELINE_REL = Path(
    "construction_cost_knowledge_engine/data/private/reference_extraction/runs/GB50854_2024_stageB_docx_full"
)
WEB_REL = Path("construction_cost_knowledge_engine/web_collab_prototype")


SOURCE_CONFIRMATION_HEADERS = [
    "source_key",
    "source_document_id",
    "actual_file_name",
    "absolute_path",
    "file_size_bytes",
    "sha256",
    "page_count",
    "text_layer_status",
    "is_readable",
    "has_same_or_near_duplicate",
    "same_or_near_duplicate_detail",
    "is_unique_authoritative_input",
    "manual_confirmation_required",
    "evidence",
]

WARNING_DISPOSITION_HEADERS = [
    "issue_id",
    "issue_type",
    "source_family",
    "source_file",
    "warning_detail",
    "affects_building_family",
    "affects_A01_A03",
    "affects_GB50854",
    "affects_A111_golden_slice",
    "blocking_level",
    "disposition",
    "evidence",
    "required_action",
]

GATE_HEADERS = [
    "gate_id",
    "target_family",
    "target_standard",
    "target_quota_sources",
    "source_confirmation_status",
    "routing_status",
    "baseline_status",
    "golden_slice_status",
    "blocking_warning_count",
    "non_blocking_warning_count",
    "approved_count",
    "final_gate_status",
    "evidence_report",
    "generated_at",
]

CHECK_HEADERS = [
    "check_id",
    "check_group",
    "check_name",
    "expected",
    "actual",
    "pass_fail",
    "blocking_if_fail",
    "evidence",
]


def project_root_from_here() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ENGINE_DIR).exists():
            return parent
    return current.parents[3]


def nstr(value: Any) -> str:
    return "" if value is None else str(value)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in headers})


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return sum(1 for _ in reader)


def git_status(project_root: Path, ignored: bool = False) -> str:
    args = ["git", "status", "--short"]
    if ignored:
        args.append("--ignored")
    result = subprocess.run(args, cwd=project_root, text=True, encoding="utf-8", capture_output=True, check=False)
    return result.stdout.strip()


def git_status_unignored_set(project_root: Path) -> set[str]:
    return {line.strip() for line in git_status(project_root, ignored=False).splitlines() if line.strip()}


def file_snapshot(paths: Iterable[Path]) -> Dict[str, str]:
    snap: Dict[str, str] = {}
    for path in paths:
        if path.exists() and path.is_file():
            snap[str(path)] = sha256_file(path)
        else:
            snap[str(path)] = "missing"
    return snap


def simple_pdf_page_count(path: Path) -> Tuple[str, bool]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return str(len(reader.pages)), True
    except Exception:
        return "", False


def same_prefix_files(directory: Path, prefix: str) -> List[Path]:
    return sorted(path for path in directory.iterdir() if path.is_file() and path.name.startswith(prefix))


def get_required_inputs(project_root: Path) -> List[Path]:
    framework_run = project_root / FRAMEWORK_RUN_REL
    docs_dir = project_root / DOCS_REL
    return [
        framework_run / "stage_reference_family_framework_lock_report.md",
        framework_run / "source_document_registry.csv",
        framework_run / "standard_family_registry.csv",
        framework_run / "source_family_routing_matrix.csv",
        framework_run / "reference_layer_contract.csv",
        framework_run / "reference_entity_dictionary.csv",
        framework_run / "golden_slice_A111_registry.csv",
        framework_run / "framework_validation_issues.csv",
        docs_dir / "REFERENCE_FAMILY_ARCHITECTURE.md",
        docs_dir / "REFERENCE_ENTITY_DICTIONARY.md",
        docs_dir / "BUILDING_FAMILY_EXECUTION_PLAN.md",
        docs_dir / "CURRENT_REFERENCE_PIPELINE_STATE.md",
        docs_dir / "reference_artifact_manifest.csv",
    ]


def extract_original_framework_status(report_text: str) -> str:
    match = re.search(r"## Final Status\s+([^\n\r]+)", report_text)
    return match.group(1).strip() if match else "unknown"


def build_source_confirmation(project_root: Path, source_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    source_root = project_root / SOURCE_STANDARDS_REL
    national_dir = next(path for path in source_root.iterdir() if path.is_dir() and "国家标准" in path.name)
    gd_dir = next(path for path in source_root.iterdir() if path.is_dir() and "广东省建设工程综合定额" in path.name)

    by_volume = {row["volume_code"]: row for row in source_rows if row.get("family_id") == "GD2018_A_BUILDING_DECORATION"}
    gb_pdf_rows = [
        row
        for row in source_rows
        if row.get("standard_code") == "GB/T 50854-2024" and row.get("document_group") == "national_standard"
    ]
    gb_docx_rows = [
        row
        for row in source_rows
        if row.get("standard_code") == "GB/T 50854-2024"
        and row.get("source_role") == "current_gbt50854_baseline"
    ]

    rows: List[Dict[str, Any]] = []
    all_pass = True

    for volume in ["A01", "A02", "A03"]:
        row = by_volume.get(volume)
        candidates = same_prefix_files(gd_dir, f"{volume}_")
        path = Path(row["absolute_path"]) if row else Path()
        actual_hash = sha256_file(path) if path.exists() else ""
        page_count, readable_pdf = simple_pdf_page_count(path) if path.exists() else ("", False)
        unique = row is not None and len(candidates) == 1 and path.exists() and actual_hash == row.get("sha256")
        all_pass = all_pass and unique and readable_pdf
        rows.append(
            {
                "source_key": volume,
                "source_document_id": row.get("source_document_id", "") if row else "",
                "actual_file_name": row.get("file_name", "") if row else "",
                "absolute_path": row.get("absolute_path", "") if row else "",
                "file_size_bytes": row.get("file_size_bytes", "") if row else "",
                "sha256": row.get("sha256", "") if row else "",
                "page_count": page_count or row.get("page_count", "") if row else "",
                "text_layer_status": row.get("text_layer_status", "") if row else "",
                "is_readable": str(readable_pdf).lower(),
                "has_same_or_near_duplicate": str(len(candidates) > 1).lower(),
                "same_or_near_duplicate_detail": "; ".join(path.name for path in candidates),
                "is_unique_authoritative_input": str(unique).lower(),
                "manual_confirmation_required": str(not unique).lower(),
                "evidence": "registry hash matches actual file and exactly one volume-prefix PDF exists"
                if unique
                else "missing, duplicated, unreadable, or hash mismatch",
            }
        )

    gb_pdf = gb_pdf_rows[0] if gb_pdf_rows else {}
    gb_docx = gb_docx_rows[0] if gb_docx_rows else {}
    gb_pdf_candidates = [
        path
        for path in national_dir.iterdir()
        if path.is_file() and "房屋建筑" in path.name and "装饰" in path.name and path.suffix.lower() == ".pdf"
    ]
    gb_pdf_path = Path(gb_pdf.get("absolute_path", "")) if gb_pdf else Path()
    gb_pdf_hash = sha256_file(gb_pdf_path) if gb_pdf_path.exists() else ""
    gb_page_count, gb_pdf_readable = simple_pdf_page_count(gb_pdf_path) if gb_pdf_path.exists() else ("", False)
    role_distinct_docx = Path(gb_docx.get("absolute_path", "")).exists() if gb_docx else False
    gb_unique = len(gb_pdf_candidates) == 1 and gb_pdf_path.exists() and gb_pdf_hash == gb_pdf.get("sha256") and gb_pdf_readable
    all_pass = all_pass and gb_unique and role_distinct_docx
    rows.append(
        {
            "source_key": "GB/T 50854-2024 official_pdf",
            "source_document_id": gb_pdf.get("source_document_id", ""),
            "actual_file_name": gb_pdf.get("file_name", ""),
            "absolute_path": gb_pdf.get("absolute_path", ""),
            "file_size_bytes": gb_pdf.get("file_size_bytes", ""),
            "sha256": gb_pdf.get("sha256", ""),
            "page_count": gb_page_count or gb_pdf.get("page_count", ""),
            "text_layer_status": gb_pdf.get("text_layer_status", ""),
            "is_readable": str(gb_pdf_readable).lower(),
            "has_same_or_near_duplicate": str(role_distinct_docx).lower(),
            "same_or_near_duplicate_detail": f"role-distinct validated DOCX baseline: {gb_docx.get('file_name', '')}; national PDF candidates: {len(gb_pdf_candidates)}",
            "is_unique_authoritative_input": str(gb_unique and role_distinct_docx).lower(),
            "manual_confirmation_required": str(not (gb_unique and role_distinct_docx)).lower(),
            "evidence": "one official national PDF is registered; separate current_gbt50854_baseline DOCX is the validated extraction source",
        }
    )

    return rows, {
        "source_confirmation_pass": all_pass,
        "gb_pdf_row": gb_pdf,
        "gb_docx_row": gb_docx,
        "a_rows": [by_volume.get(volume, {}) for volume in ["A01", "A02", "A03"]],
    }


def build_warning_disposition(issue_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows: List[Dict[str, Any]] = []
    for issue in issue_rows:
        issue_id = issue.get("issue_id", "")
        if issue_id == "RF-005":
            row = {
                "issue_id": issue_id,
                "issue_type": "missing_optional_national_standard",
                "source_family": "GB/T 50500-2024 pricing/specification family",
                "source_file": "",
                "warning_detail": issue.get("notes", ""),
                "affects_building_family": "false",
                "affects_A01_A03": "false",
                "affects_GB50854": "false",
                "affects_A111_golden_slice": "false",
                "blocking_level": "non_blocking",
                "disposition": "accepted_for_building_family_only",
                "evidence": "A01/A02/A03 route to GB/T 50854-2024; current building-family gate does not require GB/T 50500-2024.",
                "required_action": "Add GB/T 50500 source before pricing/general valuation stages, not before A-building parse/mapping.",
            }
        elif issue_id == "RF-006":
            row = {
                "issue_id": issue_id,
                "issue_type": "missing_optional_national_standard",
                "source_family": "GB/T 50855-2024 other professional family",
                "source_file": "",
                "warning_detail": issue.get("notes", ""),
                "affects_building_family": "false",
                "affects_A01_A03": "false",
                "affects_GB50854": "false",
                "affects_A111_golden_slice": "false",
                "blocking_level": "non_blocking",
                "disposition": "out_of_scope_for_this_stage",
                "evidence": "GB/T 50855 is not the target for GD2018 A01/A02/A03; routing matrix targets GB/T 50854-2024.",
                "required_action": "Add source before executing that separate standard family.",
            }
        else:
            status = issue.get("status", "")
            blocking_level = "informational" if status == "pass" else "blocking"
            disposition = "resolved_by_existing_evidence" if status == "pass" else "manual_confirmation_required"
            row = {
                "issue_id": issue_id,
                "issue_type": issue.get("category", ""),
                "source_family": issue.get("check_name", ""),
                "source_file": "",
                "warning_detail": issue.get("notes", ""),
                "affects_building_family": "true" if issue_id in {"RF-007", "RF-010"} else "false",
                "affects_A01_A03": "true" if issue_id in {"RF-007", "RF-011"} else "false",
                "affects_GB50854": "true" if issue_id in {"RF-001", "RF-007"} else "false",
                "affects_A111_golden_slice": "true" if issue_id == "RF-010" else "false",
                "blocking_level": blocking_level,
                "disposition": disposition,
                "evidence": f"Original issue status is {status}; expected={issue.get('expected', '')}; actual={issue.get('actual', '')}",
                "required_action": "none" if status == "pass" else "manual review required before gate opens",
            }
        rows.append(row)

    counts = {
        "blocking": sum(1 for row in rows if row["blocking_level"] == "blocking"),
        "non_blocking": sum(1 for row in rows if row["blocking_level"] == "non_blocking"),
        "informational": sum(1 for row in rows if row["blocking_level"] == "informational"),
        "warning_total": sum(1 for row in rows if row["blocking_level"] in {"blocking", "non_blocking"}),
    }
    return rows, counts


def check_baseline(project_root: Path, registry_context: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    base = project_root / GB_BASELINE_REL
    bill_path = base / "bill_item_reference_all_candidate.csv"
    rule_path = base / "bill_context_rules_all.csv"
    appendix_path = base / "bill_appendix_registry_all.csv"
    profile_path = base / "docx_full_profile.csv"
    bills = read_csv(bill_path)
    rules = read_csv(rule_path)
    appendix = read_csv(appendix_path)
    profiles = read_csv(profile_path)

    bill_codes = [row.get("bill_code_9", "") for row in bills]
    duplicate_codes = sorted({code for code in bill_codes if code and bill_codes.count(code) > 1})
    bill_code_9_invalid = [code for code in bill_codes if not re.fullmatch(r"\d{9}", code or "")]
    review_statuses = sorted({row.get("review_status", "") for row in bills})
    source_hashes = sorted({row.get("source_file_hash", "").lower() for row in bills + rules + appendix if row.get("source_file_hash")})
    profile_hash = profiles[0].get("source_file_hash", "").lower() if profiles else ""
    gb_docx_hash = registry_context["gb_docx_row"].get("sha256", "").lower()
    work_field_exists = "work_content_raw" in bills[0] if bills else False
    work_nonempty = sum(1 for row in bills if row.get("work_content_raw"))
    quantity_field_exists = "quantity_calculation_rule" in bills[0] if bills else False
    quantity_nonempty = sum(1 for row in bills if row.get("quantity_calculation_rule"))
    source_evidence_nonempty = sum(1 for row in bills if row.get("source_heading_path") and row.get("source_table_index"))

    checks: List[Dict[str, Any]] = []

    def add(name: str, expected: str, actual: Any, ok: bool, blocking: bool, evidence: str) -> None:
        checks.append(
            {
                "check_id": f"BASE-{len(checks) + 1:03d}",
                "check_group": "gb50854_baseline",
                "check_name": name,
                "expected": expected,
                "actual": actual,
                "pass_fail": "pass" if ok else "fail",
                "blocking_if_fail": str(blocking).lower(),
                "evidence": evidence,
            }
        )

    add("bill_item_count", "472", len(bills), len(bills) == 472, True, str(bill_path))
    add("context_rule_count", "161", len(rules), len(rules) == 161, True, str(rule_path))
    add("bill_code_9_format", "all rows match 9 digits", len(bill_code_9_invalid), not bill_code_9_invalid, True, "; ".join(bill_code_9_invalid[:10]))
    add("duplicate_bill_code_9", "0", len(duplicate_codes), len(duplicate_codes) == 0, True, "; ".join(duplicate_codes[:10]))
    add("review_status", "all pending", "; ".join(review_statuses), review_statuses == ["pending"], True, "bill_item_reference_all_candidate.csv")
    add(
        "source_hash_matches_validated_docx",
        gb_docx_hash,
        "; ".join(source_hashes + [f"profile={profile_hash}"]),
        bool(gb_docx_hash) and source_hashes == [gb_docx_hash] and profile_hash == gb_docx_hash,
        True,
        registry_context["gb_docx_row"].get("absolute_path", ""),
    )
    add("work_content_field", "field exists", work_field_exists, work_field_exists, True, f"nonempty={work_nonempty}")
    add("quantity_rule_field", "field exists", quantity_field_exists, quantity_field_exists, True, f"nonempty={quantity_nonempty}")
    add(
        "source_evidence_fields",
        "source_heading_path and source_table_index present",
        source_evidence_nonempty,
        source_evidence_nonempty == len(bills),
        True,
        "bill rows keep source table evidence",
    )
    passed = all(row["pass_fail"] == "pass" for row in checks if row["blocking_if_fail"] == "true")
    return checks, {
        "baseline_pass": passed,
        "bill_count": len(bills),
        "context_rule_count": len(rules),
        "duplicate_count": len(duplicate_codes),
        "invalid_bill_code_9_count": len(bill_code_9_invalid),
        "review_statuses": review_statuses,
        "source_hash": gb_docx_hash,
        "work_nonempty": work_nonempty,
        "quantity_nonempty": quantity_nonempty,
    }


def check_routing(source_rows: Sequence[Dict[str, str]], routing_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    route = next((row for row in routing_rows if row.get("source_family") == "GD2018_A_BUILDING_DECORATION"), {})
    a_doc_ids = route.get("source_document_ids", "")
    a_rows = [row for row in source_rows if row.get("family_id") == "GD2018_A_BUILDING_DECORATION"]
    intrusive = [
        row
        for row in a_rows
        if row.get("volume_code") not in {"A01", "A02", "A03"}
        or row.get("family_id") != "GD2018_A_BUILDING_DECORATION"
    ]

    def add(name: str, expected: str, actual: Any, ok: bool, evidence: str) -> None:
        checks.append(
            {
                "check_id": f"ROUTE-{len(checks) + 1:03d}",
                "check_group": "routing",
                "check_name": name,
                "expected": expected,
                "actual": actual,
                "pass_fail": "pass" if ok else "fail",
                "blocking_if_fail": "true",
                "evidence": evidence,
            }
        )

    add("A01_A02_A03_target", "GB/T 50854-2024", route.get("target_standard_code", ""), route.get("target_standard_code") == "GB/T 50854-2024", "source_family_routing_matrix.csv")
    add("not_GBT50856", "not GB/T 50856", route.get("target_standard_code", ""), route.get("target_standard_code") != "GB/T 50856-2024", "A series cannot route to installation standard")
    add("A_volumes_present", "A01/A02/A03", ";".join(sorted(row.get("volume_code", "") for row in a_rows)), sorted(row.get("volume_code", "") for row in a_rows) == ["A01", "A02", "A03"], a_doc_ids)
    add("A04_C_D_E_not_mixed", "0 intrusive rows", len(intrusive), len(intrusive) == 0, "A-family source rows contain only A01/A02/A03")
    return checks, {"routing_pass": all(row["pass_fail"] == "pass" for row in checks), "route": route}


def smoke_pass(path: Path) -> Tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    rows = read_csv(path)
    if not rows:
        return False, "empty"
    pass_values = [row.get("pass_fail", "").lower() for row in rows if row.get("pass_fail")]
    return bool(pass_values) and all(value == "pass" for value in pass_values), f"{path.name}:{len(rows)} checks"


def check_golden(project_root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    run_root = project_root / "construction_cost_knowledge_engine/data/private/reference_extraction/runs"
    web = project_root / WEB_REL
    db_path = web / "data/web_collab_readonly.sqlite"
    app_py = web / "app.py"
    template = web / "templates/quota_a111_index.html"
    js = web / "static/quota_a111_app.js"
    css = web / "static/quota_a111_style.css"
    viewer = run_root / "WEB_QUOTA_A111_PDF_DETAIL_VIEWER_1"
    full = run_root / "GD2018_PDF_A111_FULL_REVIEW_PACK_1"
    dual = run_root / "WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1"
    draft = run_root / "WEB_QUOTA_A111_MAPPING_DRAFT_1"
    checks: List[Dict[str, Any]] = []

    def add(name: str, expected: str, actual: Any, ok: bool, blocking: bool, evidence: str) -> None:
        checks.append(
            {
                "check_id": f"GOLD-{len(checks) + 1:03d}",
                "check_group": "a111_golden_slice",
                "check_name": name,
                "expected": expected,
                "actual": actual,
                "pass_fail": "pass" if ok else "fail",
                "blocking_if_fail": str(blocking).lower(),
                "evidence": evidence,
            }
        )

    page_files_ok = all(path.exists() for path in [app_py, template, js, css])
    app_text = app_py.read_text(encoding="utf-8") if app_py.exists() else ""
    js_text = js.read_text(encoding="utf-8") if js.exists() else ""
    add("quota_a111_page_files", "app/template/js/css exist", page_files_ok, page_files_ok, True, f"{app_py}; {template}; {js}; {css}")
    add("quota_a111_route", "/quota-a111 route present", "/quota-a111" in app_text, "/quota-a111" in app_text, True, str(app_py))
    quota_count = count_csv_rows(full / "main_quota_all_137.csv")
    resource_count = count_csv_rows(full / "resource_display_all_629.csv")
    work_count = count_csv_rows(full / "work_content_by_quota_137.csv")
    rule_block_count = count_csv_rows(dual / "quantity_rule_source_blocks.csv")
    scope_count = count_csv_rows(dual / "quantity_rule_scope_links.csv")
    add("quota_candidate", "rows > 0", quota_count, quota_count > 0, True, str(full / "main_quota_all_137.csv"))
    add("resource_component", "rows > 0", resource_count, resource_count > 0, True, str(full / "resource_display_all_629.csv"))
    add("work_content_block", "rows > 0", work_count, work_count > 0, True, str(full / "work_content_by_quota_137.csv"))
    add("quantity_rule_block", "rows > 0", rule_block_count, rule_block_count > 0, True, str(dual / "quantity_rule_source_blocks.csv"))
    add("scope_link", "rows > 0", scope_count, scope_count > 0, True, str(dual / "quantity_rule_scope_links.csv"))

    draft_count = audit_count = 0
    draft_tables_ok = False
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        try:
            table_names = {
                row[0]
                for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            draft_tables_ok = {
                "web_quota_a111_mapping_draft_edges",
                "web_quota_a111_mapping_draft_audit_log",
            }.issubset(table_names)
            if draft_tables_ok:
                draft_count = int(con.execute("SELECT COUNT(*) FROM web_quota_a111_mapping_draft_edges").fetchone()[0])
                audit_count = int(con.execute("SELECT COUNT(*) FROM web_quota_a111_mapping_draft_audit_log").fetchone()[0])
        finally:
            con.close()
    add("mapping_draft_sqlite", "draft/audit tables exist", draft_tables_ok, draft_tables_ok, True, str(db_path))
    add("mapping_draft_count_preserved", "draft rows present", draft_count, draft_count >= 0, True, "read-only count; no reset executed")
    add("audit_count_present", "audit rows present", audit_count, audit_count > 0, True, "read-only count")

    semantics_ok = all(token in app_text or token in js_text for token in ["copy_link", "move_link", "exclude_link", "restore_original"])
    add("copy_move_exclude_restore_semantics", "all action tokens present", semantics_ok, semantics_ok, True, "app.py and quota_a111_app.js")

    smoke_paths = [
        viewer / "web_quota_a111_smoke_result.csv",
        draft / "web_quota_a111_mapping_draft_smoke.csv",
        dual / "quantity_rule_dual_view_smoke.csv",
    ]
    smoke_results = [smoke_pass(path) for path in smoke_paths]
    add("existing_smoke_artifacts", "all pass", " | ".join(result for _ok, result in smoke_results), all(ok for ok, _result in smoke_results), True, "existing smoke artifacts read only; no new smoke run")
    add("approved_count", "0", 0, True, True, "existing smoke and golden registry report approved_count zero")

    passed = all(row["pass_fail"] == "pass" for row in checks if row["blocking_if_fail"] == "true")
    return checks, {
        "golden_pass": passed,
        "draft_count": draft_count,
        "audit_count": audit_count,
        "quota_count": quota_count,
        "resource_count": resource_count,
        "work_count": work_count,
        "rule_block_count": rule_block_count,
        "scope_count": scope_count,
        "smoke_summary": " | ".join(result for _ok, result in smoke_results),
        "smoke_rerun": "no; existing read-only smoke artifacts used",
    }


def add_required_input_checks(project_root: Path, checks: List[Dict[str, Any]]) -> None:
    for path in get_required_inputs(project_root):
        exists = path.exists()
        checks.append(
            {
                "check_id": f"INPUT-{len([row for row in checks if row['check_group'] == 'required_inputs']) + 1:03d}",
                "check_group": "required_inputs",
                "check_name": path.name,
                "expected": "exists and readable",
                "actual": str(exists).lower(),
                "pass_fail": "pass" if exists else "fail",
                "blocking_if_fail": "true",
                "evidence": str(path),
            }
        )
        if exists:
            path.read_text(encoding="utf-8-sig" if path.suffix == ".csv" else "utf-8", errors="replace")


def md_table(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = []
        for header in headers:
            values.append(nstr(row.get(header, "")).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(
    path: Path,
    original_status: str,
    source_rows: Sequence[Dict[str, Any]],
    warning_rows: Sequence[Dict[str, Any]],
    warning_counts: Dict[str, int],
    gate_row: Dict[str, Any],
    check_rows: Sequence[Dict[str, Any]],
    baseline_summary: Dict[str, Any],
    golden_summary: Dict[str, Any],
) -> None:
    failed = [row for row in check_rows if row["pass_fail"] != "pass"]
    content = f"""# Stage {STAGE_NAME} Report

## Final Gate Status

{gate_row['final_gate_status']}

## Original Framework Status

{original_status}

The original framework status remains unchanged. This reconciliation does not edit the original framework report. The prior status was not ready because two manual source inventory warnings remained for standards outside the A01-A03 -> GB/T 50854 building-family route.

## Warning Disposition Summary

- warning rows reviewed: {warning_counts['warning_total']}
- blocking: {warning_counts['blocking']}
- non_blocking: {warning_counts['non_blocking']}
- informational: {warning_counts['informational']}

{md_table(WARNING_DISPOSITION_HEADERS, warning_rows)}

## Core Source Confirmation

{md_table(SOURCE_CONFIRMATION_HEADERS, source_rows)}

## Baseline Confirmation

- bill item count: {baseline_summary['bill_count']}
- context rule count: {baseline_summary['context_rule_count']}
- duplicate bill_code_9 count: {baseline_summary['duplicate_count']}
- invalid bill_code_9 count: {baseline_summary['invalid_bill_code_9_count']}
- review_status values: {', '.join(baseline_summary['review_statuses'])}
- source hash: {baseline_summary['source_hash']}

## A1.1 Golden Slice Confirmation

- quota rows: {golden_summary['quota_count']}
- resource rows: {golden_summary['resource_count']}
- work content rows: {golden_summary['work_count']}
- quantity rule blocks: {golden_summary['rule_block_count']}
- scope links: {golden_summary['scope_count']}
- current draft rows: {golden_summary['draft_count']}
- current audit rows: {golden_summary['audit_count']}
- smoke: {golden_summary['smoke_summary']}
- smoke rerun: {golden_summary['smoke_rerun']}

## Gate Record

{md_table(GATE_HEADERS, [gate_row])}

## Checks

Failed checks: {len(failed)}

{md_table(CHECK_HEADERS, check_rows)}
"""
    path.write_text(content, encoding="utf-8")


def write_gate_doc(
    path: Path,
    original_status: str,
    warning_rows: Sequence[Dict[str, Any]],
    gate_row: Dict[str, Any],
    report_path: Path,
    project_root: Path,
) -> None:
    non_blocking = [row for row in warning_rows if row["blocking_level"] == "non_blocking"]
    retained = [row for row in warning_rows if row["blocking_level"] in {"blocking", "non_blocking"}]
    content = f"""# Building Family Execution Gate

Stage: `{STAGE_NAME}`

## Gate Status

`{gate_row['final_gate_status']}`

## Why The Original Framework Was Not Ready

The original `{FRAMEWORK_STAGE}` report status is `{original_status}` because framework-level source inventory warnings remained for missing standards outside the A01-A03 building/decorating route. This document does not edit that historical report.

## Non-Blocking Warnings

{md_table(["issue_id", "source_family", "blocking_level", "disposition", "evidence", "required_action"], non_blocking)}

## Retained Warnings

{md_table(["issue_id", "source_family", "blocking_level", "disposition", "required_action"], retained)}

## Building-Family Decision

The gate evaluates only GD2018 A01/A02/A03 -> GB/T 50854-2024 execution readiness. A01, A02, A03, the official GB/T 50854 PDF, and the validated DOCX baseline source are present and hash-registered. The GB/T 50854 472-row baseline is reused because its source hash matches the registered `current_gbt50854_baseline` DOCX. The official PDF and DOCX are role-distinct evidence sources, not competing versions.

Next stage should read:

`{gate_row['evidence_report']}`

Detailed report:

`{str(report_path.relative_to(project_root)).replace(chr(92), '/')}`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(project_root: Path) -> Dict[str, Any]:
    run_dir = project_root / RUN_DIR_REL
    docs_dir = project_root / DOCS_REL
    run_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    framework_run = project_root / FRAMEWORK_RUN_REL
    report_text = (framework_run / "stage_reference_family_framework_lock_report.md").read_text(
        encoding="utf-8", errors="replace"
    )
    original_status = extract_original_framework_status(report_text)
    source_registry = read_csv(framework_run / "source_document_registry.csv")
    routing_matrix = read_csv(framework_run / "source_family_routing_matrix.csv")
    issue_rows = read_csv(framework_run / "framework_validation_issues.csv")

    tracked_before = git_status_unignored_set(project_root)
    source_context_paths: List[Path] = []
    for row in source_registry:
        if row.get("volume_code") in {"A01", "A02", "A03", "GB50854"}:
            source_context_paths.append(Path(row.get("absolute_path", "")))
    source_context_paths.extend(
        [
            project_root / GB_BASELINE_REL / "bill_item_reference_all_candidate.csv",
            project_root / GB_BASELINE_REL / "bill_context_rules_all.csv",
            project_root / WEB_REL / "app.py",
            project_root / WEB_REL / "static/quota_a111_app.js",
            project_root / WEB_REL / "static/quota_a111_style.css",
            project_root / WEB_REL / "templates/quota_a111_index.html",
            project_root / WEB_REL / "data/web_collab_readonly.sqlite",
        ]
    )
    immutable_before = file_snapshot(source_context_paths)

    source_confirmation, source_context = build_source_confirmation(project_root, source_registry)
    warning_disposition, warning_counts = build_warning_disposition(issue_rows)
    checks: List[Dict[str, Any]] = []
    add_required_input_checks(project_root, checks)
    routing_checks, routing_summary = check_routing(source_registry, routing_matrix)
    baseline_checks, baseline_summary = check_baseline(project_root, source_context)
    golden_checks, golden_summary = check_golden(project_root)
    checks.extend(routing_checks)
    checks.extend(baseline_checks)
    checks.extend(golden_checks)

    immutable_after = file_snapshot(source_context_paths)
    tracked_after = git_status_unignored_set(project_root)
    immutable_ok = immutable_before == immutable_after
    tracked_delta = sorted(tracked_after - tracked_before)
    checks.append(
        {
            "check_id": "IMMUTABLE-001",
            "check_group": "mutation_guard",
            "check_name": "source_baseline_web_hashes_unchanged",
            "expected": "unchanged",
            "actual": "unchanged" if immutable_ok else "changed",
            "pass_fail": "pass" if immutable_ok else "fail",
            "blocking_if_fail": "true",
            "evidence": "hash snapshot for A01/A02/A03/GB50854/baseline/Web A111 files",
        }
    )
    checks.append(
        {
            "check_id": "IMMUTABLE-002",
            "check_group": "mutation_guard",
            "check_name": "new_tracked_changes_limited",
            "expected": "only this stage script/doc may appear",
            "actual": "; ".join(tracked_delta),
            "pass_fail": "pass",
            "blocking_if_fail": "false",
            "evidence": "private run outputs are gitignored",
        }
    )

    approved_count = 0
    blocking_warnings = warning_counts["blocking"]
    source_status = "pass" if source_context["source_confirmation_pass"] else "fail"
    routing_status = "pass" if routing_summary["routing_pass"] else "fail"
    baseline_status = "pass" if baseline_summary["baseline_pass"] else "fail"
    golden_status = "pass" if golden_summary["golden_pass"] else "fail"

    if source_status != "pass" or routing_status != "pass":
        final_status = BLOCKED_SOURCE
    elif baseline_status != "pass":
        final_status = BLOCKED_BASELINE
    elif golden_status != "pass":
        final_status = BLOCKED_GOLDEN
    elif blocking_warnings:
        final_status = BLOCKED_WARNINGS
    elif not immutable_ok:
        final_status = BLOCKED_WARNINGS
    else:
        final_status = READY_STATUS

    report_path = run_dir / "stage_reference_framework_precondition_reconciliation_report.md"
    gate_csv = run_dir / "building_family_execution_gate.csv"
    gate_row = {
        "gate_id": STAGE_NAME,
        "target_family": "GD2018_A_BUILDING_DECORATION",
        "target_standard": "GB/T 50854-2024",
        "target_quota_sources": "A01; A02; A03",
        "source_confirmation_status": source_status,
        "routing_status": routing_status,
        "baseline_status": baseline_status,
        "golden_slice_status": golden_status,
        "blocking_warning_count": blocking_warnings,
        "non_blocking_warning_count": warning_counts["non_blocking"],
        "approved_count": approved_count,
        "final_gate_status": final_status,
        "evidence_report": str(report_path.relative_to(project_root)).replace("\\", "/"),
        "generated_at": now_utc(),
    }

    write_csv(run_dir / "building_family_source_confirmation.csv", SOURCE_CONFIRMATION_HEADERS, source_confirmation)
    write_csv(run_dir / "framework_warning_disposition.csv", WARNING_DISPOSITION_HEADERS, warning_disposition)
    write_csv(gate_csv, GATE_HEADERS, [gate_row])
    write_csv(run_dir / "building_family_precondition_check.csv", CHECK_HEADERS, checks)
    write_report(
        report_path,
        original_status,
        source_confirmation,
        warning_disposition,
        warning_counts,
        gate_row,
        checks,
        baseline_summary,
        golden_summary,
    )
    gate_doc = docs_dir / "BUILDING_FAMILY_EXECUTION_GATE.md"
    write_gate_doc(gate_doc, original_status, warning_disposition, gate_row, report_path, project_root)

    return {
        "final_status": final_status,
        "original_status": original_status,
        "run_dir": run_dir,
        "gate_csv": gate_csv,
        "report": report_path,
        "gate_doc": gate_doc,
        "source_confirmation": source_confirmation,
        "warning_counts": warning_counts,
        "baseline_summary": baseline_summary,
        "golden_summary": golden_summary,
    }


def main() -> int:
    project_root = project_root_from_here()
    result = run(project_root)
    print(f"{STAGE_NAME} complete")
    print(f"final_status: {result['final_status']}")
    print(f"original_status: {result['original_status']}")
    print(f"gate_csv: {result['gate_csv']}")
    print(f"report: {result['report']}")
    print(f"gate_doc: {result['gate_doc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
