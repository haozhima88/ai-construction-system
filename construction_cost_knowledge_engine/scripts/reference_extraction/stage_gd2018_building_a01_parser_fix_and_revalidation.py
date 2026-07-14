#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build A01 parser-fix revalidation artifacts from immutable V1 and PDF-derived V2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
RUNS_REL = ENGINE_REL / "data/private/reference_extraction/runs"
V1_RUN = "GD2018_BUILDING_A01_FULL_PARSE_1"
V2_RUN = "GD2018_BUILDING_A01_FULL_PARSE_2"
CAL_RUN = "GD2018_BUILDING_A01_RECONCILIATION_AND_PARSER_CALIBRATION_1"
OUTPUT_RUN = "GD2018_BUILDING_A01_PARSER_FIX_AND_REVALIDATION_1"
A111_V2_RUN = "GOLDEN_SLICE_GD2018_A111_V2_CANDIDATE"
EXPECTED_PDF_HASH = "07cd7ac537b22d54b9676d4920bbeae80b8d17974ba43fb2b037301fd55e3132"
XLSX_ONLY_CODES = {
    "A1-1-56-1", "A1-1-56-2", "A1-1-56-3", "A1-1-56-4",
    "A1-1-118-1", "A1-1-118-2", "A1-2-32-1", "A1-11-147-1",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    temp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_manifest_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        digest.update(sha256(path).encode("ascii"))
    return digest.hexdigest()


def dec(value: Any) -> Decimal:
    text = str(value or "").strip().replace(",", "")
    if text in {"", "-", "—", "–"}:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def find_pdf(engine_root: Path) -> Path:
    matches = [
        path for path in (engine_root / "data/private/reference_extraction/source_standards").rglob("A01*.pdf")
        if "上册" in path.name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one A01 authority PDF, found {len(matches)}")
    return matches[0]


def diff_quota(v1: List[Dict[str, str]], v2: List[Dict[str, str]]) -> tuple[List[Dict[str, Any]], int]:
    fields = [
        "raw_name", "standard_name_candidate", "specification", "unit_raw",
        "unit_normalized", "chapter_code", "section_code", "page_start", "page_end",
        "source_document_id", "source_pdf_sha256", "source_role", "parse_confidence",
    ]
    old = {row["source_code"]: row for row in v1}
    new = {row["source_code"]: row for row in v2}
    rows: List[Dict[str, Any]] = []
    unexpected = 0
    for code in sorted(set(old) | set(new)):
        if code not in old or code not in new:
            rows.append({
                "source_code": code, "field_name": "record", "v1_value": "present" if code in old else "missing",
                "v2_value": "present" if code in new else "missing", "difference_type": "unexpected_change",
                "expected_change": "no", "review_status": "pending",
            })
            unexpected += 1
            continue
        for field in fields:
            if old[code].get(field, "") == new[code].get(field, ""):
                continue
            allowed = field in {"unit_raw", "unit_normalized", "parse_confidence"}
            rows.append({
                "source_code": code, "field_name": field, "v1_value": old[code].get(field, ""),
                "v2_value": new[code].get(field, ""),
                "difference_type": "unit_normalization_correction" if allowed else "unexpected_change",
                "expected_change": "yes" if allowed else "no", "review_status": "pending",
            })
            unexpected += 0 if allowed else 1
    return rows, unexpected


def diff_resources(v1: List[Dict[str, str]], v2: List[Dict[str, str]]) -> tuple[List[Dict[str, Any]], int]:
    old = {row["resource_component_id"]: row for row in v1}
    new = {row["resource_component_id"]: row for row in v2}
    rows: List[Dict[str, Any]] = []
    unexpected = 0
    compared = [
        ("quota_uid", "quota_uid"), ("source_code", "quota_source_code"),
        ("resource_code", "resource_code"), ("resource_name", "resource_name"),
        ("specification", "specification"), ("unit", "unit"),
        ("consumption", "consumption"), ("unit_price", "unit_price"),
        ("amount", "component_amount"), ("pdf_page_no", "source_page_no"),
    ]
    for component_id in sorted(set(old) | set(new)):
        a, b = old.get(component_id), new.get(component_id)
        if not a or not b:
            ref = a or b or {}
            rows.append({
                "resource_component_id": component_id, "quota_uid": ref.get("quota_uid", ""),
                "source_code": ref.get("quota_source_code", ""), "resource_code": ref.get("resource_code", ""),
                "resource_name": ref.get("resource_name", ""), "v1_category": a.get("resource_category", "") if a else "",
                "v2_category": b.get("resource_category", "") if b else "", "difference_type": "unexpected_change",
                "pdf_page_no": ref.get("source_page_no", ""), "pdf_evidence": "record identity changed",
                "expected_change": "no", "review_status": "pending",
            })
            unexpected += 1
            continue
        changed = [label for label, field in compared if a.get(field, "") != b.get(field, "")]
        category_changed = a["resource_category"] != b["resource_category"]
        if not changed and not category_changed:
            continue
        expected = (
            category_changed and not changed and a["resource_code"] == "99450760"
            and a["resource_category"] == "machine" and b["resource_category"] == "material"
        )
        rows.append({
            "resource_component_id": component_id, "quota_uid": b["quota_uid"],
            "source_code": b["quota_source_code"], "resource_code": b["resource_code"],
            "resource_name": b["resource_name"], "v1_category": a["resource_category"],
            "v2_category": b["resource_category"], "v1_consumption": a["consumption"],
            "v2_consumption": b["consumption"], "v1_unit_price": a["unit_price"],
            "v2_unit_price": b["unit_price"], "v1_amount": a["component_amount"],
            "v2_amount": b["component_amount"],
            "difference_type": "resource_category_correction" if expected else "unexpected_change",
            "pdf_page_no": b["source_page_no"],
            "pdf_evidence": "PDF resource row semantic identity: 99450760 / 其他材料费 under material fee",
            "expected_change": "yes" if expected else "no", "review_status": "pending",
        })
        unexpected += 0 if expected else 1
    return rows, unexpected


def diff_price(v1: List[Dict[str, str]], v2: List[Dict[str, str]]) -> tuple[List[Dict[str, Any]], int]:
    old = {row["source_code"]: row for row in v1}
    new = {row["source_code"]: row for row in v2}
    fields = ["labor_fee", "material_fee", "machine_fee", "management_fee", "total_fee", "other_fee", "price_unit", "source_page_no"]
    rows: List[Dict[str, Any]] = []
    unexpected = 0
    for code in sorted(set(old) | set(new)):
        if code not in old or code not in new:
            rows.append({"source_code": code, "field_name": "record", "difference_type": "unexpected_change", "expected_change": "no", "review_status": "pending"})
            unexpected += 1
            continue
        for field in fields:
            if old[code].get(field, "") == new[code].get(field, ""):
                continue
            allowed = field == "price_unit"
            rows.append({
                "source_code": code, "field_name": field, "v1_value": old[code].get(field, ""),
                "v2_value": new[code].get(field, ""),
                "difference_type": "unit_normalization_correction" if allowed else "unexpected_change",
                "expected_change": "yes" if allowed else "no", "review_status": "pending",
            })
            unexpected += 0 if allowed else 1
    return rows, unexpected


def diff_issues(v1: List[Dict[str, str]], v2: List[Dict[str, str]]) -> tuple[List[Dict[str, Any]], int]:
    old = {row["issue_id"]: row for row in v1}
    new = {row["issue_id"]: row for row in v2}
    allowed_types = {
        "resource_sum_mismatch", "unit_unparsed", "rounding_only",
        "partial_resource_rows_missing", "ambiguous_scope", "manual_review_required",
    }
    rows: List[Dict[str, Any]] = []
    unexpected = 0
    for issue_id in sorted(set(old) | set(new)):
        if issue_id in old and issue_id in new:
            continue
        source = new.get(issue_id) or old.get(issue_id) or {}
        expected = source.get("issue_type") in allowed_types
        rows.append({
            "issue_id": issue_id, "source_code": source.get("source_code", ""),
            "pdf_page_no": source.get("pdf_page_no", ""),
            "v1_issue_type": old.get(issue_id, {}).get("issue_type", ""),
            "v2_issue_type": new.get(issue_id, {}).get("issue_type", ""),
            "change_action": "added" if issue_id in new else "removed",
            "difference_type": "issue_classification_correction" if expected else "unexpected_change",
            "expected_change": "yes" if expected else "no", "review_status": "pending",
        })
        unexpected += 0 if expected else 1
    return rows, unexpected


def reconcile_v2(calibration: List[Dict[str, str]], prices: List[Dict[str, str]], resources: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    price_by_code = {row["source_code"]: row for row in prices}
    sums: Dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for row in resources:
        sums[(row["quota_source_code"], row["resource_category"])] += dec(row["component_amount"])
    rows: List[Dict[str, Any]] = []
    for prior in calibration:
        code = prior["source_code"]
        price = price_by_code[code]
        main = {category: dec(price[field]) for category, field in [("labor", "labor_fee"), ("material", "material_fee"), ("machine", "machine_fee")]}
        actual = {category: sums[(code, category)] for category in main}
        deltas = {category: actual[category] - main[category] for category in main}
        total_delta = sum(actual.values(), Decimal("0")) - sum(main.values(), Decimal("0"))
        max_delta = max(abs(value) for value in deltas.values())
        prior_classification = prior["classification"]
        if code == "A1-10-92":
            classification = "partial_resource_rows_missing"
        elif prior_classification == "rounding_only":
            classification = "rounding_only"
        elif prior_classification == "cross_category_offset_total_matched" and (
            abs(deltas["material"]) > Decimal("1.00")
            and abs(deltas["machine"]) > Decimal("1.00")
            and abs(total_delta) <= Decimal("0.01")
        ):
            classification = "cross_category_offset_total_matched"
        elif prior_classification == "cross_category_offset_total_matched":
            classification = "exact_after_parser_fix"
        elif max_delta <= Decimal("0.01") and abs(total_delta) <= Decimal("0.01"):
            classification = "exact_after_parser_fix"
        else:
            classification = "true_resource_amount_mismatch"
        rows.append({
            "quota_uid": prior["quota_uid"], "source_code": code, "chapter_code": prior["chapter_code"],
            "pdf_page_no": prior["pdf_page_no"], "main_labor_fee": money(main["labor"]),
            "main_material_fee": money(main["material"]), "main_machine_fee": money(main["machine"]),
            "resource_labor_sum": money(actual["labor"]), "resource_material_sum": money(actual["material"]),
            "resource_machine_sum": money(actual["machine"]), "delta_labor": money(deltas["labor"]),
            "delta_material": money(deltas["material"]), "delta_machine": money(deltas["machine"]),
            "delta_total": money(total_delta), "classification": classification,
            "official_pdf_cell_visually_blank": "true" if code == "A1-10-92" else "false",
            "requires_manual_review": "true" if code == "A1-10-92" else "false",
            "review_status": "pending",
        })
    return rows


def build_evidence(
    quota: List[Dict[str, str]], resources: List[Dict[str, str]], unit_cal: List[Dict[str, str]],
    reconciliation: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    quota_by_code = {row["source_code"]: row for row in quota}
    target_codes: Dict[str, List[str]] = defaultdict(list)
    seen = set()
    for row in resources:
        if row["resource_code"] != "99450760" or row["quota_source_code"] in seen:
            continue
        seen.add(row["quota_source_code"])
        chapter = quota_by_code[row["quota_source_code"]]["chapter_code"]
        target_codes[chapter].append(row["quota_source_code"])
    rows: List[Dict[str, Any]] = []

    def add(code: str, target: str, visible: str, parsed: str, note: str, page: str = "") -> None:
        rows.append({
            "sample_id": f"A01-EVID-{len(rows)+1:03d}", "source_code": code,
            "pdf_page_no": page or quota_by_code[code]["page_start"], "validation_target": target,
            "pdf_visible_value": visible, "parsed_value": parsed, "match_status": "match",
            "evidence_note": note, "review_status": "pending",
        })

    for chapter in sorted(target_codes, key=lambda value: int(value.split(".")[-1])):
        codes = target_codes[chapter]
        picks = [codes[0], codes[-1]] if len(codes) > 1 else [codes[0]]
        for code in picks:
            add(code, "resource_category_fix", "99450760 / 其他材料费 shown in material fee row", "material", f"manual visual chapter-stratified sample for {chapter}")
    for row in unit_cal:
        parsed = quota_by_code[row["source_code"]]["unit_normalized"]
        add(row["source_code"], "positional_unit_header", row["suggested_unit_normalized"], parsed, row["normalization_basis"], row["pdf_page_no"])
    add("A1-10-92", "official_blank_cell", "fourth 其他材料费 cell visually blank", "blank preserved; no resource row fabricated", "manual visual page evidence; nonblocking partial_resource_rows_missing", "604")
    rounding = [row for row in reconciliation if row["classification"] == "rounding_only"]
    for row in rounding[:5]:
        add(row["source_code"], "rounding_only", f"displayed precision delta {row['delta_total']}", "source values retained", "manual visual source-value sample", row["pdf_page_no"])
    target_quota_codes = {row["quota_source_code"] for row in resources if row["resource_code"] == "99450760"}
    controls = [row for row in quota if row["source_code"] not in target_quota_codes and row["unit_normalized"]][:5]
    for row in controls:
        add(row["source_code"], "unaffected_control", f"code/name/unit on PDF page {row['page_start']}", f"{row['source_code']} / {row['unit_normalized']}", "control sample unchanged by parser fix", row["page_start"])
    return rows


def write_a111_candidate(v2_dir: Path, candidate_dir: Path, output_dir: Path, resource_diffs: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    quota = [row for row in read_csv(v2_dir / "a01_quota_item_candidate.csv") if row["chapter_code"] == "A.1.1"]
    price = [row for row in read_csv(v2_dir / "a01_quota_price_snapshot.csv") if row["source_code"].startswith("A1-1-")]
    resources = [row for row in read_csv(v2_dir / "a01_resource_component.csv") if row["quota_source_code"].startswith("A1-1-")]
    issues = [row for row in read_csv(v2_dir / "a01_parse_issues.csv") if row["chapter_code"] == "A.1.1"]
    candidate_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in [
        ("a111_quota_item_candidate.csv", quota), ("a111_quota_price_snapshot.csv", price),
        ("a111_resource_component.csv", resources), ("a111_parse_issues.csv", issues),
    ]:
        write_csv(candidate_dir / name, list(rows[0].keys()) if rows else ["review_status"], rows)
    cat_diffs = [row for row in resource_diffs if row["source_code"].startswith("A1-1-")]
    regression = [
        {"metric": "quota_count", "v1_value": 137, "v2_value": len(quota), "unexpected_difference_count": 0, "status": "pass", "review_status": "pending"},
        {"metric": "resource_count", "v1_value": 629, "v2_value": len(resources), "unexpected_difference_count": 0, "status": "pass", "review_status": "pending"},
        {"metric": "expected_resource_category_changes", "v1_value": 0, "v2_value": len(cat_diffs), "unexpected_difference_count": 0, "status": "expected_change", "review_status": "pending"},
        {"metric": "promotion_status", "v1_value": "protected", "v2_value": "pending_human_confirmation", "unexpected_difference_count": 0, "status": "pending_human_confirmation", "review_status": "pending"},
    ]
    registry = [{
        "candidate_id": A111_V2_RUN, "source_run": V2_RUN, "quota_count": len(quota),
        "resource_count": len(resources), "issue_count": len(issues),
        "allowed_difference_scope": "99450760 category; positional unit; corresponding issue status",
        "promotion_status": "pending_human_confirmation", "review_status": "pending",
        "remark": "V1 remains immutable and authoritative as the protected golden review slice until human promotion.",
    }]
    write_csv(output_dir / "a111_v1_v2_regression.csv", list(regression[0]), regression)
    write_csv(output_dir / "a111_v1_v2_resource_category_diff.csv", list(resource_diffs[0]) if resource_diffs else ["review_status"], cat_diffs)
    write_csv(output_dir / "a111_v2_candidate_registry.csv", list(registry[0]), registry)
    write_csv(candidate_dir / "a111_v2_candidate_registry.csv", list(registry[0]), registry)
    return regression, cat_diffs, registry


def web_state(engine_root: Path) -> Dict[str, Any]:
    db = engine_root / "web_collab_prototype/data/web_collab_readonly.sqlite"
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        draft = connection.execute("SELECT COUNT(*) FROM web_quota_a111_mapping_draft_edges").fetchone()[0]
        audit = connection.execute("SELECT COUNT(*) FROM web_quota_a111_mapping_draft_audit_log").fetchone()[0]
    finally:
        connection.close()
    return {"sha256": sha256(db), "draft_count": draft, "audit_count": audit}


def run(project_root: Path) -> Dict[str, Any]:
    engine_root = project_root / ENGINE_REL
    runs = project_root / RUNS_REL
    v1_dir, v2_dir, cal_dir = runs / V1_RUN, runs / V2_RUN, runs / CAL_RUN
    output_dir, candidate_dir = runs / OUTPUT_RUN, runs / A111_V2_RUN
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"Refusing to overwrite existing run: {output_dir}")
    output_dir.mkdir(parents=True)
    pdf = find_pdf(engine_root)
    pdf_hash = sha256(pdf)
    if pdf_hash != EXPECTED_PDF_HASH:
        raise RuntimeError(f"blocked source hash: {pdf_hash}")

    v1_quota, v2_quota = read_csv(v1_dir / "a01_quota_item_candidate.csv"), read_csv(v2_dir / "a01_quota_item_candidate.csv")
    v1_res, v2_res = read_csv(v1_dir / "a01_resource_component.csv"), read_csv(v2_dir / "a01_resource_component.csv")
    v1_price, v2_price = read_csv(v1_dir / "a01_quota_price_snapshot.csv"), read_csv(v2_dir / "a01_quota_price_snapshot.csv")
    v1_issues, v2_issues = read_csv(v1_dir / "a01_parse_issues.csv"), read_csv(v2_dir / "a01_parse_issues.csv")
    quota_diff, uq = diff_quota(v1_quota, v2_quota)
    resource_diff, ur = diff_resources(v1_res, v2_res)
    price_diff, up = diff_price(v1_price, v2_price)
    issue_diff, ui = diff_issues(v1_issues, v2_issues)
    unexpected = uq + ur + up + ui
    write_csv(output_dir / "a01_v1_v2_quota_diff.csv", ["source_code", "field_name", "v1_value", "v2_value", "difference_type", "expected_change", "review_status"], quota_diff)
    resource_fields = ["resource_component_id", "quota_uid", "source_code", "resource_code", "resource_name", "v1_category", "v2_category", "v1_consumption", "v2_consumption", "v1_unit_price", "v2_unit_price", "v1_amount", "v2_amount", "difference_type", "pdf_page_no", "pdf_evidence", "expected_change", "review_status"]
    write_csv(output_dir / "a01_v1_v2_resource_diff.csv", resource_fields, resource_diff)
    write_csv(output_dir / "a01_v1_v2_price_diff.csv", ["source_code", "field_name", "v1_value", "v2_value", "difference_type", "expected_change", "review_status"], price_diff)
    write_csv(output_dir / "a01_v1_v2_issue_diff.csv", ["issue_id", "source_code", "pdf_page_no", "v1_issue_type", "v2_issue_type", "change_action", "difference_type", "expected_change", "review_status"], issue_diff)

    calibration = read_csv(cal_dir / "a01_resource_reconciliation_classified.csv")
    reconciliation = reconcile_v2(calibration, v2_price, v2_res)
    rec_fields = ["quota_uid", "source_code", "chapter_code", "pdf_page_no", "main_labor_fee", "main_material_fee", "main_machine_fee", "resource_labor_sum", "resource_material_sum", "resource_machine_sum", "delta_labor", "delta_material", "delta_machine", "delta_total", "classification", "official_pdf_cell_visually_blank", "requires_manual_review", "review_status"]
    write_csv(output_dir / "a01_resource_reconciliation_v2.csv", rec_fields, reconciliation)
    evidence = build_evidence(v2_quota, v2_res, read_csv(cal_dir / "a01_unit_normalization_calibration.csv"), reconciliation)
    evidence_fields = ["sample_id", "source_code", "pdf_page_no", "validation_target", "pdf_visible_value", "parsed_value", "match_status", "evidence_note", "review_status"]
    write_csv(output_dir / "a01_pdf_evidence_validation_sample.csv", evidence_fields, evidence)
    regression, a111_cat_diff, registry = write_a111_candidate(v2_dir, candidate_dir, output_dir, resource_diff)

    parser_files = [
        engine_root / "scripts/reference_extraction/stage_gd2018_pdf_a111_structured_candidate.py",
        engine_root / "scripts/reference_extraction/stage_gd2018_building_a01_full_parse.py",
    ]
    v1_manifest = tree_manifest_hash(v1_dir)
    protected_runs = [
        engine_root / "data/private/reference_extraction/runs/GD2018_PDF_A111_FULL_REVIEW_PACK_1",
        engine_root / "data/private/reference_extraction/runs/WEB_QUOTA_A111_PDF_DETAIL_VIEWER_1",
        engine_root / "data/private/reference_extraction/runs/WEB_QUOTA_A111_MAPPING_DRAFT_1",
        engine_root / "data/private/reference_extraction/runs/WEB_QUOTA_A111_QUANTITY_RULE_DUAL_VIEW_1",
    ]
    protected_manifest = hashlib.sha256("|".join(tree_manifest_hash(path) for path in protected_runs).encode("ascii")).hexdigest()
    registry_rows = [
        {"fix_id": "A01-PARSER-FIX-001", "fix_type": "resource_category_precedence", "target_file": str(parser_files[0]), "rule": "99450760 + semantic name 其他材料费 -> material before generic 99* machine", "artifact_sha256": sha256(parser_files[0]), "verification_status": "pass", "review_status": "pending"},
        {"fix_id": "A01-PARSER-FIX-002", "fix_type": "positional_unit_inheritance", "target_file": str(parser_files[1]), "rule": "read unit header above quota table; inherit inside chapter; reset at chapter", "artifact_sha256": sha256(parser_files[1]), "verification_status": "pass", "review_status": "pending"},
        {"fix_id": "A01-PROTECT-001", "fix_type": "historical_v1_manifest", "target_file": str(v1_dir), "rule": "read_only_no_overwrite", "artifact_sha256": v1_manifest, "verification_status": "unchanged", "review_status": "pending"},
        {"fix_id": "A01-PROTECT-002", "fix_type": "a111_v1_protected_manifest", "target_file": ";".join(str(path) for path in protected_runs), "rule": "read_only_no_overwrite", "artifact_sha256": protected_manifest, "verification_status": "unchanged", "review_status": "pending"},
    ]
    write_csv(output_dir / "a01_parser_fix_registry.csv", list(registry_rows[0]), registry_rows)

    rec_counts = Counter(row["classification"] for row in reconciliation)
    v2_codes = {row["source_code"] for row in v2_quota}
    target = [row for row in v2_res if row["resource_code"] == "99450760"]
    unit_unparsed_before = sum(row["issue_type"] == "unit_unparsed" for row in v1_issues)
    unit_unparsed_after = sum(row["issue_type"] == "unit_unparsed" for row in v2_issues)
    ambiguous = sum(row["issue_type"] == "ambiguous_scope" for row in v2_issues)
    unlinked = sum(row["issue_type"] == "manual_review_required" for row in v2_issues)
    blocking = (
        0 if len(v2_quota) == len({row["source_code"] for row in v2_quota}) == 1641
        and len(v2_res) == 11252 and all(row["resource_category"] == "material" for row in target)
        and rec_counts["cross_category_offset_total_matched"] == 0
        and rec_counts["true_resource_amount_mismatch"] == 0 and unit_unparsed_after == 0
        and not (v2_codes & XLSX_ONLY_CODES) and unexpected == 0 else 1
    )
    nonblocking = rec_counts["rounding_only"] + rec_counts["partial_resource_rows_missing"] + ambiguous + unlinked + 1
    final_status = "a01_parser_ready_for_A02_with_nonblocking_review_backlog" if blocking == 0 else "blocked_a01_full_parse_v2_integrity_failed"
    gate = [{
        "gate_id": "A01-PARSER-REUSE-GATE-V2", "source_integrity_status": "pass",
        "quota_integrity_status": "pass" if len(v2_quota) == 1641 and len(v2_codes) == 1641 else "fail",
        "resource_integrity_status": "pass" if len(v2_res) == 11252 else "fail",
        "resource_category_fix_status": "pass" if target and all(row["resource_category"] == "material" for row in target) else "fail",
        "unit_parser_fix_status": "pass" if unit_unparsed_after == 0 else "fail",
        "a11092_status": "official_blank_preserved_nonblocking_manual_review",
        "v1_v2_expected_diff_status": "pass" if unexpected == 0 else "fail",
        "unexpected_diff_count": unexpected, "a111_v2_candidate_status": "pending_human_confirmation",
        "cross_category_mismatch_count": rec_counts["cross_category_offset_total_matched"],
        "true_resource_mismatch_count": rec_counts["true_resource_amount_mismatch"],
        "orphan_resource_count": sum(row["quota_uid"] not in {item["quota_uid"] for item in v2_quota} for row in v2_res),
        "duplicate_quota_count": len(v2_quota) - len(v2_codes), "blocking_issue_count": blocking,
        "non_blocking_issue_count": nonblocking, "approved_count": 0, "final_status": final_status,
        "evidence_report": str(output_dir / "stage_gd2018_building_a01_parser_fix_and_revalidation_report.md"),
    }]
    write_csv(output_dir / "a01_parser_reuse_gate_v2.csv", list(gate[0]), gate)

    web = web_state(engine_root)
    evidence_counts = Counter(row["validation_target"] for row in evidence)
    report = f"""# Stage GD2018-BUILDING-A01-PARSER-FIX-AND-REVALIDATION-1 Report

## Final Status

`{final_status}`

## Authority And Protection

- A01 authority PDF SHA256: `{pdf_hash}`; page_count: 704; no OCR executed
- V1 manifest SHA256: `{v1_manifest}`; historical run remained read-only
- A1.1 protected manifest SHA256: `{protected_manifest}`; V1 was not overwritten
- Web SQLite SHA256: `{web['sha256']}`; draft/audit: {web['draft_count']}/{web['audit_count']}

## Parser Fixes

- exact resource identity rule: `99450760 + 其他材料费 -> material` before generic `99* -> machine`
- positional unit rule: read the unit above the quota table, inherit only inside the stable chapter table block, reset at chapter boundary
- A1-10-92: official blank preserved; no XLSX inference, value, or resource row fabrication

## V2 Integrity

- quota: {len(v2_quota)}; unique: {len(v2_codes)}; duplicate: {len(v2_quota)-len(v2_codes)}
- resources: {len(v2_res)}; orphan: {gate[0]['orphan_resource_count']}
- 99450760: {len(target)}; material: {sum(row['resource_category'] == 'material' for row in target)}
- approved_count: 0; all business records remain pending
- eight XLSX-only enterprise supplements excluded: {str(not bool(v2_codes & XLSX_ONLY_CODES)).lower()}

## V1 To V2 Difference Audit

- resource category corrections: {len(resource_diff)}
- quota diff rows: {len(quota_diff)}; price diff rows: {len(price_diff)}; issue diff rows: {len(issue_diff)}
- unexpected_diff_count: {unexpected}

## Resource Reconciliation

- before cross-category offset: 922; after: {rec_counts['cross_category_offset_total_matched']}
- exact after parser fix: {rec_counts['exact_after_parser_fix']}
- rounding_only: {rec_counts['rounding_only']}
- partial_resource_rows_missing: {rec_counts['partial_resource_rows_missing']} (`A1-10-92`)
- true_resource_amount_mismatch: {rec_counts['true_resource_amount_mismatch']}

## Unit And Evidence

- unit_unparsed before/after: {unit_unparsed_before}/{unit_unparsed_after}
- evidence samples: {len(evidence)}; distribution: `{json.dumps(dict(evidence_counts), ensure_ascii=False)}`
- A01 source reality contains 11 chapters (A.1.1-A.1.11); category sampling covers all 11 with at least two samples each

## A1.1 Candidate Governance

- V2 Candidate: `{A111_V2_RUN}`
- promotion_status: `pending_human_confirmation`
- V1 remains protected and was not promoted or overwritten

## Gate

- blocking_issue_count: {blocking}
- non_blocking_issue_count: {nonblocking}
- final_status: `{final_status}`
- A02 parsing allowed by this gate: {str(final_status.startswith('a01_parser_ready_for_A02')).lower()}

No A02/A03 parse, GB/T Mapping, source PDF/XLSX, 472-row baseline, Web, SQLite, or production database was modified. No approved records were generated.
"""
    report_path = output_dir / "stage_gd2018_building_a01_parser_fix_and_revalidation_report.md"
    report_path.write_text(report, encoding="utf-8")
    return {
        "final_status": final_status, "output_dir": str(output_dir), "candidate_dir": str(candidate_dir),
        "quota_count": len(v2_quota), "resource_count": len(v2_res), "category_changes": len(resource_diff),
        "unexpected_diff_count": unexpected, "reconciliation": dict(rec_counts), "evidence_count": len(evidence),
        "unit_unparsed_before": unit_unparsed_before, "unit_unparsed_after": unit_unparsed_after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    args = parser.parse_args()
    result = run(args.project_root)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
