from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text


ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
sys.path.insert(0, str(ENGINE_ROOT))

from platform_db.database import build_engine  # noqa: E402
from platform_db.importers.hash_guard import validate_rc1_manifest  # noqa: E402
from platform_db.local_runtime import load_local_environment  # noqa: E402


STAGE = "ENTERPRISE_PRICE_SOURCE_CONFIRMATION_AND_A111_PRICING_UAT_1"
RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs" / STAGE
PRIOR_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_RESOURCE_MATCHING_AND_A111_QUOTA_PILOT_1"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"
FINAL_STATUS = "enterprise_price_confirmed_source_missing"


REGISTRY_FIELDS = [
    "source_price_document_id", "file_name", "absolute_path", "sha256", "file_size", "record_count",
    "source_role", "authority_status", "confirmed_by", "confirmed_at", "effective_region", "tax_mode",
    "effective_from", "effective_to", "remark",
]
VALIDATION_FIELDS = [
    "validation_id", "validation_scope", "source_row_no", "resource_code", "resource_name", "field_name",
    "issue_type", "severity", "expected", "actual", "status", "message", "payload_sha256",
]
RESOURCE_MATCH_FIELDS = [
    "enterprise_resource_id", "resource_code", "resource_name", "specification", "unit", "confirmed_price",
    "tax_mode", "region", "effective_from", "effective_to", "source_document", "match_status",
    "review_status", "issue",
]
PRICE_VERSION_FIELDS = [
    "price_version_code", "tenant_id", "source_document_id", "effective_region", "tax_mode", "effective_from",
    "created_by", "created_at", "row_version", "source_sha256", "status", "enterprise_price_record_count",
    "platform_import_job_id",
]
RECALC_FIELDS = [
    "enterprise_quota_version_id", "quota_code", "quota_name", "unit", "component_count",
    "priced_component_count", "missing_price_resource_count", "anomaly_resource_count", "enterprise_base_price",
    "provincial_base_price", "absolute_difference", "difference_percentage", "price_version_code",
    "calculation_rule_version", "calculation_status",
]
SUMMARY_FIELDS = [
    "enterprise_quota_version_id", "quota_code", "quota_name", "labor_total", "material_total",
    "machine_total", "other_total", "management_fee", "enterprise_base_price", "provincial_base_price",
    "absolute_difference", "difference_percentage", "missing_price_resource_count", "anomaly_resource_count",
    "calculation_status",
]
ISSUE_FIELDS = [
    "issue_id", "issue_type", "enterprise_resource_id", "resource_code", "resource_name", "specification",
    "unit", "source_row_no", "severity", "issue", "required_action", "review_status",
]
SNAPSHOT_FIELDS = [
    "enterprise_quota_version_id", "quota_code", "enterprise_resource_id", "price_version_id", "price_value",
    "unit", "tax_mode", "region", "effective_from", "source_document_id", "calculation_rule_version",
    "snapshot_code", "snapshot_sha256", "status",
]
UAT_FIELDS = [
    "sample_id", "quota_code", "quota_name", "price_completeness", "resource_match_status",
    "calculation_status", "reviewer_decision", "issue", "follow_up", "human_confirmed",
]
GATE_FIELDS = ["gate_id", "condition", "expected", "actual", "status", "evidence"]
SMOKE_FIELDS = ["check_id", "check", "expected", "actual", "status", "verification"]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def scalar_counts() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    engine = build_engine()
    count_sql = {
        "migration": "select version_num from alembic_version",
        "a111_reference_quota": "select count(*) from reference_quota_item where source_code like 'A1-1-%'",
        "a111_reference_resource_component": "select count(*) from reference_quota_resource r join reference_quota_item q on q.reference_quota_item_id=r.reference_quota_item_id where q.source_code like 'A1-1-%'",
        "enterprise_resource": "select count(*) from enterprise_resource",
        "exact_link": "select count(*) from enterprise_resource_reference_link where match_method in ('exact_code','normalized_code','exact_name_spec_unit')",
        "manual_link": "select count(*) from enterprise_resource_reference_link where match_method in ('semantic_candidate','manual_link')",
        "unmatched_link": "select count(*) from enterprise_resource_reference_link where match_method='unmatched'",
        "enterprise_price_record": "select count(*) from enterprise_price_version",
        "missing_price_resource": "select count(*) from enterprise_resource er where not exists (select 1 from enterprise_price_version ep where ep.enterprise_resource_id=er.enterprise_resource_id)",
        "enterprise_quota_draft": "select count(*) from enterprise_quota_version where source_quota_code like 'A1-1-%' and state='draft'",
        "approved": "select count(*) from enterprise_quota_version where state='approved'",
        "published": "select count(*) from enterprise_quota_version where state='published'",
    }
    resource_sql = """
        select er.enterprise_resource_id, er.resource_code, er.resource_name, er.specification, er.unit,
               er.resource_category, er.tenant_id
        from enterprise_resource er
        order by er.resource_code, er.resource_name, er.specification, er.unit
    """
    quota_sql = """
        select v.enterprise_quota_version_id, v.source_quota_code as quota_code, q.quota_name, v.unit,
               v.calculation_rule_version, rq.total_fee as provincial_base_price,
               count(c.enterprise_quota_component_version_id) as component_count,
               count(distinct c.enterprise_resource_id) as missing_price_resource_count
        from enterprise_quota_version v
        join enterprise_quota q on q.enterprise_quota_id=v.enterprise_quota_id
        join reference_quota_item rq on rq.reference_quota_item_id=q.source_reference_quota_id
        join enterprise_quota_component_version c on c.enterprise_quota_version_id=v.enterprise_quota_version_id
        where v.source_quota_code like 'A1-1-%' and v.state='draft'
        group by v.enterprise_quota_version_id, v.source_quota_code, q.quota_name, v.unit,
                 v.calculation_rule_version, rq.total_fee
        order by string_to_array(replace(v.source_quota_code, 'A1-1-', ''), '-')::int[]
    """
    with engine.connect() as connection:
        counts = {name: connection.scalar(text(sql)) for name, sql in count_sql.items()}
        resources = [dict(row) for row in connection.execute(text(resource_sql)).mappings()]
        quotas = [dict(row) for row in connection.execute(text(quota_sql)).mappings()]
    engine.dispose()
    return counts, resources, quotas


def assert_preflight(counts: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "migration": "0004_enterprise_price_a111_pilot",
        "a111_reference_quota": 137,
        "a111_reference_resource_component": 629,
        "enterprise_resource": 55,
        "exact_link": 629,
        "manual_link": 0,
        "unmatched_link": 0,
        "enterprise_price_record": 0,
        "missing_price_resource": 55,
        "enterprise_quota_draft": 137,
        "approved": 0,
        "published": 0,
    }
    failures = {key: {"expected": value, "actual": counts.get(key)} for key, value in expected.items() if counts.get(key) != value}
    prior_checkpoint = (PRIOR_DIR / "checkpoint_enterprise_price_a111_pilot.md").read_text(encoding="utf-8")
    prior_report = (PRIOR_DIR / "stage_enterprise_price_resource_matching_and_a111_quota_pilot_report.md").read_text(encoding="utf-8")
    if "enterprise_price_source_confirmation_required" not in prior_checkpoint or "enterprise_price_source_confirmation_required" not in prior_report:
        failures["prior_final_status"] = {"expected": "enterprise_price_source_confirmation_required", "actual": "missing"}
    guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    sqlite_sha256 = hashlib.sha256(SQLITE.read_bytes()).hexdigest()
    if not guard["ok"]:
        failures["hash_guard"] = guard["failures"]
    if sqlite_sha256 != EXPECTED_SQLITE_SHA256:
        failures["sqlite_sha256"] = {"expected": EXPECTED_SQLITE_SHA256, "actual": sqlite_sha256}
    if failures:
        raise RuntimeError("Preflight changed; stage stopped: " + json.dumps(failures, ensure_ascii=False, default=str))
    return {"hash_guard": guard, "sqlite_sha256": sqlite_sha256}


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    missing_environment = load_local_environment(ENGINE_ROOT / ".env.platform.local")
    if missing_environment:
        raise RuntimeError("Platform environment incomplete: " + ", ".join(missing_environment))
    counts, resources, quotas = scalar_counts()
    integrity = assert_preflight(counts)

    configured_value = os.environ.get("ENTERPRISE_PRICE_CONFIRMED_SOURCE_PATH", "").strip()
    source_path = Path(configured_value).expanduser() if configured_value else None
    source_exists = bool(source_path and source_path.is_file())
    if source_exists:
        raise RuntimeError(
            "A confirmed source appeared after the missing-source preflight. Restart this Stage so the file can be "
            "validated and imported without reusing missing-source artifacts."
        )

    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    validation_rows = [{
        "validation_id": "CONFIG-001",
        "validation_scope": "stage_configuration",
        "source_row_no": "",
        "resource_code": "",
        "resource_name": "",
        "field_name": "ENTERPRISE_PRICE_CONFIRMED_SOURCE_PATH",
        "issue_type": "confirmed_source_missing",
        "severity": "blocking",
        "expected": "existing user-confirmed CSV/XLSX path",
        "actual": configured_value or "not_set",
        "status": "fail",
        "message": "No confirmed price source was configured; no price row was imported or synthesized.",
        "payload_sha256": "",
    }]
    resource_match_rows = [{
        "enterprise_resource_id": row["enterprise_resource_id"],
        "resource_code": row["resource_code"],
        "resource_name": row["resource_name"],
        "specification": row["specification"],
        "unit": row["unit"],
        "confirmed_price": "",
        "tax_mode": "",
        "region": "",
        "effective_from": "",
        "effective_to": "",
        "source_document": "",
        "match_status": "unmatched",
        "review_status": "pending",
        "issue": "missing_price",
    } for row in resources]
    issue_rows = [{
        "issue_id": f"PRICE-MISSING-{index:03d}",
        "issue_type": "missing_price",
        "enterprise_resource_id": row["enterprise_resource_id"],
        "resource_code": row["resource_code"],
        "resource_name": row["resource_name"],
        "specification": row["specification"],
        "unit": row["unit"],
        "source_row_no": "",
        "severity": "blocking",
        "issue": "Confirmed Enterprise Price source is not configured.",
        "required_action": "Set ENTERPRISE_PRICE_CONFIRMED_SOURCE_PATH to the user-confirmed source and rerun validation.",
        "review_status": "pending",
    } for index, row in enumerate(resources, 1)]
    recalculation_rows = [{
        "enterprise_quota_version_id": row["enterprise_quota_version_id"],
        "quota_code": row["quota_code"],
        "quota_name": row["quota_name"],
        "unit": row["unit"],
        "component_count": row["component_count"],
        "priced_component_count": 0,
        "missing_price_resource_count": row["missing_price_resource_count"],
        "anomaly_resource_count": row["missing_price_resource_count"],
        "enterprise_base_price": "",
        "provincial_base_price": row["provincial_base_price"],
        "absolute_difference": "",
        "difference_percentage": "",
        "price_version_code": "",
        "calculation_rule_version": row["calculation_rule_version"],
        "calculation_status": "blocked_confirmed_source_missing",
    } for row in quotas]
    summary_rows = [{
        "enterprise_quota_version_id": row["enterprise_quota_version_id"],
        "quota_code": row["quota_code"],
        "quota_name": row["quota_name"],
        "labor_total": "",
        "material_total": "",
        "machine_total": "",
        "other_total": "",
        "management_fee": "",
        "enterprise_base_price": "",
        "provincial_base_price": row["provincial_base_price"],
        "absolute_difference": "",
        "difference_percentage": "",
        "missing_price_resource_count": row["missing_price_resource_count"],
        "anomaly_resource_count": row["missing_price_resource_count"],
        "calculation_status": "blocked_confirmed_source_missing",
    } for row in quotas]

    prior_uat = read_csv(PRIOR_DIR / "a111_enterprise_quota_pilot_uat.csv")
    uat_rows = [{
        "sample_id": row["uat_case_id"],
        "quota_code": row["source_quota_code"],
        "quota_name": row["enterprise_quota_name"],
        "price_completeness": row.get("enterprise_price_completeness", "0/0"),
        "resource_match_status": "confirmed_source_missing",
        "calculation_status": "blocked_confirmed_source_missing",
        "reviewer_decision": "",
        "issue": "missing_price",
        "follow_up": "User/cost department must configure the confirmed source; then rerun input validation and pricing UAT.",
        "human_confirmed": "false",
    } for row in prior_uat]

    gate_rows = [
        {"gate_id": "G01", "condition": "55 resources completed price processing", "expected": 55, "actual": 0, "status": "fail", "evidence": "confirmed source missing"},
        {"gate_id": "G02", "condition": "missing prices", "expected": 0, "actual": 55, "status": "fail", "evidence": "a111_enterprise_price_issue.csv"},
        {"gate_id": "G03", "condition": "unit conflicts", "expected": 0, "actual": "not_evaluated", "status": "blocked", "evidence": "no input rows"},
        {"gate_id": "G04", "condition": "specification conflicts have human conclusions", "expected": "complete", "actual": "not_evaluated", "status": "blocked", "evidence": "no input rows"},
        {"gate_id": "G05", "condition": "tax mode complete", "expected": 55, "actual": 0, "status": "fail", "evidence": "no input rows"},
        {"gate_id": "G06", "condition": "region complete", "expected": 55, "actual": 0, "status": "fail", "evidence": "no input rows"},
        {"gate_id": "G07", "condition": "effective date complete", "expected": 55, "actual": 0, "status": "fail", "evidence": "no input rows"},
        {"gate_id": "G08", "condition": "137 quotas recalculated", "expected": 137, "actual": 0, "status": "fail", "evidence": "recalculation rows remain null"},
        {"gate_id": "G09", "condition": "price snapshot round-trip", "expected": "pass", "actual": "not_run", "status": "blocked", "evidence": "no price version"},
        {"gate_id": "G10", "condition": "20 UAT samples user-confirmed", "expected": 20, "actual": 0, "status": "fail", "evidence": "human_confirmed=false"},
        {"gate_id": "G11", "condition": "Reference/Mapping/SQLite hash unchanged", "expected": "pass", "actual": "pass", "status": "pass", "evidence": integrity["sqlite_sha256"]},
    ]
    prior_browser = PRIOR_DIR / "enterprise_quota_browser_result.json"
    browser_result = json.loads(prior_browser.read_text(encoding="utf-8")) if prior_browser.exists() else {"checks": []}
    prior_browser_passed = sum(row.get("status") == "pass" for row in browser_result["checks"])
    smoke_rows = [
        {"check_id": "WEB-001", "check": "confirmed source gate", "expected": "block without configured source", "actual": FINAL_STATUS, "status": "pass", "verification": "stage configuration gate"},
        {"check_id": "WEB-002", "check": "existing authenticated A1.1 workbench evidence", "expected": "7/7 prior browser checks", "actual": f"{prior_browser_passed}/{len(browser_result['checks'])}", "status": "pass" if prior_browser_passed == len(browser_result["checks"]) == 7 else "fail", "verification": str(prior_browser)},
        {"check_id": "WEB-003", "check": "price confirmation UAT execution", "expected": "confirmed source", "actual": "not_run_confirmed_source_missing", "status": "not_run", "verification": "no price Draft or recalculation was created"},
    ]

    write_csv(RUN_DIR / "confirmed_price_source_registry.csv", REGISTRY_FIELDS, [])
    write_csv(RUN_DIR / "enterprise_price_input_validation.csv", VALIDATION_FIELDS, validation_rows)
    write_csv(RUN_DIR / "a111_enterprise_resource_price_match.csv", RESOURCE_MATCH_FIELDS, resource_match_rows)
    write_csv(RUN_DIR / "a111_enterprise_price_draft_version.csv", PRICE_VERSION_FIELDS, [])
    write_csv(RUN_DIR / "a111_enterprise_quota_recalculation.csv", RECALC_FIELDS, recalculation_rows)
    write_csv(RUN_DIR / "a111_enterprise_quota_cost_summary.csv", SUMMARY_FIELDS, summary_rows)
    write_csv(RUN_DIR / "a111_enterprise_price_issue.csv", ISSUE_FIELDS, issue_rows)
    write_csv(RUN_DIR / "a111_enterprise_price_snapshot_preview.csv", SNAPSHOT_FIELDS, [])
    write_csv(RUN_DIR / "a111_enterprise_price_uat_20.csv", UAT_FIELDS, uat_rows)
    write_csv(RUN_DIR / "enterprise_price_approval_gate.csv", GATE_FIELDS, gate_rows)
    write_csv(RUN_DIR / "enterprise_price_web_smoke.csv", SMOKE_FIELDS, smoke_rows)

    summary = {
        "stage": STAGE,
        "final_status": FINAL_STATUS,
        "generated_at": now,
        "confirmed_source_configured": bool(configured_value),
        "confirmed_source_exists": source_exists,
        "confirmed_source_path": configured_value,
        "input_record_count": 0,
        "enterprise_resource_count": len(resources),
        "price_match_exact": 0,
        "price_match_manual_confirmation_required": 0,
        "price_match_unmatched": len(resources),
        "missing_price_count": len(resources),
        "unit_conflict_count": None,
        "specification_conflict_count": None,
        "enterprise_price_draft_version_count": 0,
        "quota_recalculation_complete_count": 0,
        "quota_recalculation_blocked_count": len(quotas),
        "new_preview_snapshot_count": 0,
        "uat_sample_count": len(uat_rows),
        "human_confirmed_count": 0,
        "approved_count": counts["approved"],
        "published_count": counts["published"],
        "preflight": counts,
        "hash_guard": integrity["hash_guard"],
        "sqlite_sha256": integrity["sqlite_sha256"],
    }
    (RUN_DIR / "stage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    checkpoint = f"""# Checkpoint: {STAGE}

- Final status: `{FINAL_STATUS}`
- `ENTERPRISE_PRICE_CONFIRMED_SOURCE_PATH`: `not set`
- Confirmed source registry / input records / price Draft versions: `0 / 0 / 0`
- Enterprise Resource price coverage exact/manual/unmatched: `0 / 0 / 55`
- Missing prices: `55`; unit/specification conflict checks: `not evaluated without input`
- A1.1 quota recalculation complete/blocked: `0 / 137`
- New preview snapshots: `0`; round-trip: `not run without price version`
- UAT samples: `20`; `human_confirmed=true`: `0`
- Web route: `/enterprise-quota/a111-pilot`; price-confirmation UAT was not run because no confirmed source exists.
- approved / published: `{counts['approved']} / {counts['published']}`
- Reference/Baseline/Mapping Hash Guard: `pass`
- SQLite SHA256 unchanged: `{integrity['sqlite_sha256']}`
- No database import, import job, price version, Reference write, Mapping write or SQLite write occurred.
"""
    (RUN_DIR / "checkpoint_enterprise_price_a111_pricing_uat.md").write_text(checkpoint, encoding="utf-8")

    report = f"""# Stage {STAGE} Report

## Final Status

`{FINAL_STATUS}`

## Confirmed Source Gate

`ENTERPRISE_PRICE_CONFIRMED_SOURCE_PATH` was not set in the process, user, machine or local platform environment. The Stage did not select a file by name, did not treat any internal workbook as authoritative, and did not synthesize a price.

## Pricing Result

- Confirmed source documents / input records / Enterprise Price Draft versions: `0 / 0 / 0`.
- A1.1 Enterprise Resources: `55`; price-source match exact/manual/unmatched: `0 / 0 / 55`.
- Missing prices: `55`. Unit and specification conflicts cannot be evaluated without input rows.
- A1.1 Enterprise Quota Drafts: `137`; recalculation complete/blocked: `0 / 137`.
- Enterprise totals, differences and percentages remain null. Provincial reference values are shown for comparison only.
- New preview snapshots: `0`; no price version exists to snapshot or restore.

## Human UAT And Approval Gate

- The prior 20 representative samples were carried forward with `human_confirmed=false`.
- Approval readiness is false: only the Reference/Mapping/SQLite integrity gate passes.
- Web price-confirmation UAT was not run because the required confirmed source and Draft price version do not exist.
- The retained authenticated workbench route is `/enterprise-quota/a111-pilot`.

## Integrity

- Preflight counts remain `137/137`, `629/55`, links `629/0/0`, Enterprise prices `0`, missing resources `55`, approved/published `0/0`.
- RC1 Source/Baseline/Mapping Hash Guard: `pass`.
- SQLite SHA256: `{integrity['sqlite_sha256']}` (unchanged).
- This run made no database mutation and did not modify Reference, Mapping Candidate or SQLite.

## Next Required Action

The user or cost department must explicitly set `ENTERPRISE_PRICE_CONFIRMED_SOURCE_PATH` to the confirmed CSV/XLSX file. The next run must register its identity and hash, validate every input row, and only then create Draft prices, recalculation previews and new snapshots.
"""
    (RUN_DIR / "stage_enterprise_price_source_confirmation_and_a111_pricing_uat_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
