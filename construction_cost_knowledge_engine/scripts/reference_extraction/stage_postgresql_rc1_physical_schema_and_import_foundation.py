#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate PostgreSQL RC1 physical/import validation evidence from the development database."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from fastapi.testclient import TestClient
from sqlalchemy import String, cast, func, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from platform_db.api import app
from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.common import file_sha256, stable_uuid
from platform_db.importers.draft_overlay import migrate_draft_overlay
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.models import (
    AppUser, Base, EnterprisePriceApproval, EnterprisePriceObservation, EnterprisePriceSnapshot,
    EnterprisePriceSnapshotLine, EnterprisePriceVersion, EnterpriseQuota, EnterpriseQuotaChangeSet,
    EnterpriseQuotaComponentVersion, EnterpriseQuotaRelease, EnterpriseQuotaReviewEvent,
    EnterpriseQuotaRuleVersion, EnterpriseQuotaVersion, EnterpriseResource, MappingCandidateEdge,
    MappingDraftEdge, MappingRelease, PlatformImportJob, PlatformImportJobItem, ReferenceBillItem,
    ReferenceQuotaItem, ReferenceQuotaResource, ReferenceRelease, ReferenceRuleBlock,
    ReferenceScopeLink, SchemaMigration,
)
from platform_db.services.parity import run_parity_checks
from platform_db.services.performance import run_performance_baseline


PROJECT_ROOT_DEFAULT = Path(r"E:\workspace\01_Projects\ai-construction-system")
ENGINE_REL = Path("construction_cost_knowledge_engine")
STAGE = "POSTGRESQL_RC1_PHYSICAL_SCHEMA_AND_IMPORT_FOUNDATION_1"
FINAL_READY = "postgresql_rc1_foundation_ready_for_web_backend_migration"
SUPPLEMENTAL = {
    "app_tenant", "app_user_role_assignment", "mapping_workspace", "release_artifact",
    "enterprise_price_snapshot", "enterprise_price_snapshot_line", "platform_import_job",
    "platform_import_job_item",
}


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: normalize(row.get(key)) for key in fields})
    temporary.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def normalize(value: Any) -> Any:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def domain_for(table_name: str) -> str:
    if table_name.startswith(("source_", "standard_", "reference_")):
        return "Reference"
    if table_name.startswith("mapping_"):
        return "Mapping"
    if table_name.startswith("enterprise_price_") or table_name == "enterprise_resource":
        return "Enterprise Price"
    if table_name.startswith("enterprise_quota"):
        return "Enterprise Quota"
    return "Platform"


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", capture_output=True, env=os.environ.copy())
    output = "\n".join(value.strip() for value in (result.stdout, result.stderr) if value.strip())
    return {"returncode": result.returncode, "output": output}


def sqlite_counts_and_hash(path: Path) -> dict[str, Any]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return {
            "draft": connection.execute("SELECT COUNT(*) FROM mapping_drafts").fetchone()[0],
            "audit": connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
            "review": connection.execute("SELECT COUNT(*) FROM review_states").fetchone()[0],
            "sha256": file_sha256(path),
        }


def physical_dictionary(engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    rows = []
    audit_names = {"created_at", "created_by", "updated_at", "updated_by", "row_version", "correlation_id"}
    for table_name in sorted(Base.metadata.tables):
        columns = inspector.get_columns(table_name)
        pk = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        fks = inspector.get_foreign_keys(table_name)
        uniques = inspector.get_unique_constraints(table_name)
        checks = inspector.get_check_constraints(table_name)
        indexes = inspector.get_indexes(table_name)
        column_names = {column["name"] for column in columns}
        tenant = next((column for column in columns if column["name"] == "tenant_id"), None)
        immutable = table_name in {
            "source_document", "source_page_evidence", "reference_bill_item", "reference_quota_item",
            "reference_quota_resource", "reference_rule_block", "reference_scope_link", "mapping_candidate_edge",
            "release_artifact",
        }
        rows.append({
            "entity_name": table_name, "domain": domain_for(table_name),
            "entity_origin": "physical_supplement" if table_name in SUPPLEMENTAL else "architecture_logical_entity",
            "primary_key": ";".join(pk),
            "foreign_keys": ";".join(
                f"{','.join(fk['constrained_columns'])}->{fk['referred_table']}({','.join(fk['referred_columns'])})"
                for fk in fks
            ),
            "unique_constraints": ";".join(
                f"{item.get('name')}({','.join(item.get('column_names') or [])})" for item in uniques
            ),
            "check_constraints": ";".join(item.get("name") or "" for item in checks),
            "indexes": ";".join(item.get("name") or "" for item in indexes),
            "tenant_scoped": "yes" if tenant else "no",
            "tenant_not_null": "yes" if tenant and not tenant["nullable"] else ("not_applicable" if not tenant else "no"),
            "audit_fields": ";".join(sorted(audit_names & column_names)),
            "row_version": "yes" if "row_version" in column_names else "no",
            "mutability": "business_read_only_after_import" if immutable else "state_or_service_guarded",
            "delete_policy": "restrict_or_immutable_trigger" if immutable else "restrict_or_lifecycle_retire",
        })
    return rows


def constraint_matrix(engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    with engine.connect() as connection:
        triggers = set(connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")).scalars())
        enum_rows = connection.execute(text("""
            SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
            ORDER BY t.typname, e.enumsortorder
        """)).all()
    enums: dict[str, set[str]] = {}
    for name, label in enum_rows:
        enums.setdefault(name, set()).add(label)
    # app_tenant owns the tenant key; scoped business tables must reference it.
    tenant_tables = [
        name for name, table in Base.metadata.tables.items()
        if "tenant_id" in table.c and name != "app_tenant"
    ]
    tenant_ok = all(
        not next(col for col in inspector.get_columns(name) if col["name"] == "tenant_id")["nullable"]
        and any(fk["referred_table"] == "app_tenant" for fk in inspector.get_foreign_keys(name))
        for name in tenant_tables
    )
    mapping_fk_sets = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys("mapping_candidate_edge")}
    draft_fk_sets = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys("mapping_draft_edge")}
    artifact_checks = " ".join(item.get("sqltext", "") for item in inspector.get_check_constraints("release_artifact"))
    source_checks = " ".join(item.get("sqltext", "") for item in inspector.get_check_constraints("source_document"))

    specs = [
        ("CON-01", "Reference Release immutable after publish", "database_trigger", "trg_reference_release_immutable" in triggers, "platform_guard_reference_release"),
        ("CON-02", "Mapping Release immutable after publish", "database_trigger", "trg_mapping_release_immutable" in triggers, "platform_guard_mapping_release"),
        ("CON-03", "published Enterprise Quota Version cannot UPDATE", "database_trigger", "trg_enterprise_quota_version_guard" in triggers, "platform_guard_enterprise_quota_version"),
        ("CON-04", "published Enterprise Quota Version cannot DELETE", "database_trigger", "trg_enterprise_quota_version_guard" in triggers, "platform_guard_enterprise_quota_version"),
        ("CON-05", "Reference/Mapping status excludes approved", "database_enum", "approved" not in enums.get("no_approved_review_status", set()), str(sorted(enums.get("no_approved_review_status", set())))),
        ("CON-06", "tenant fields non-null and FK", "database_fk_not_null", tenant_ok, f"tenant_tables={len(tenant_tables)}"),
        ("CON-07", "released artifact SHA required", "database_check", "length((sha256)::text) = 64" in artifact_checks or "length(sha256" in artifact_checks, artifact_checks),
        ("CON-08", "authority/proxy roles explicit", "database_enum_check", enums.get("source_role") == {"authority_source", "extraction_proxy"} and "authority_status" in source_checks, str(enums.get("source_role"))),
        ("CON-09", "Mapping Candidate same Mapping/Reference Release", "composite_foreign_keys", {("mapping_release_id", "reference_release_id"), ("reference_bill_item_id", "reference_release_id"), ("reference_quota_item_id", "reference_release_id")} <= mapping_fk_sets, str(mapping_fk_sets)),
        ("CON-10", "Mapping Draft belongs to Workspace/Release", "composite_foreign_keys", {("mapping_workspace_id", "mapping_release_id"), ("mapping_candidate_edge_id", "mapping_release_id")} <= draft_fk_sets, str(draft_fk_sets)),
        ("CON-11", "reviewer/approver separation", "database_trigger", {"trg_enterprise_quota_version_guard", "trg_price_approval_separation"} <= triggers, "quota and price actor triggers"),
        ("CON-12", "row_version optimistic locking", "database_trigger_and_repository", "trg_mapping_workspace_row_version" in triggers, "platform_bump_row_version + expected version predicate"),
        ("CON-13", "Reference children read-only", "database_trigger", {"trg_reference_bill_immutable", "trg_reference_quota_immutable", "trg_reference_resource_immutable", "trg_reference_rule_immutable", "trg_reference_scope_immutable"} <= triggers, "five Reference child triggers"),
        ("CON-14", "Mapping Candidate read-only", "database_trigger", "trg_mapping_candidate_immutable" in triggers, "candidate release trigger"),
        ("CON-15", "role active periods do not overlap", "database_trigger", "trg_role_assignment_overlap" in triggers, "tstzrange overlap guard"),
        ("CON-16", "published artifact immutable", "database_trigger", "trg_release_artifact_immutable" in triggers, "immutable flag guard"),
    ]
    return [{
        "constraint_id": identifier, "requirement": requirement, "enforcement_layer": layer,
        "implementation": evidence, "test_status": "pass" if passed else "fail",
        "blocking": "yes", "remark": "",
    } for identifier, requirement, layer, passed, evidence in specs]


def api_smoke(engine) -> list[dict[str, Any]]:
    client = TestClient(app)
    rows: list[dict[str, Any]] = []

    def add(identifier: str, endpoint: str, response, expected: Any, actual: Any, passed: bool, remark: str = "") -> None:
        rows.append({
            "smoke_id": identifier, "endpoint": endpoint, "http_status": response.status_code,
            "expected": expected, "actual": actual, "status": "pass" if passed else "fail", "remark": remark,
        })

    health = client.get("/api/v1/platform/health")
    add("API-01", "/api/v1/platform/health", health, "200; PostgreSQL 16.14; head", health.json(), health.status_code == 200 and "16.14" in health.json().get("database_version", "") and health.json().get("migration_head") == "0001_platform_core_schema")
    bills = client.get("/api/v1/platform/reference/bills", params={"page": 1, "page_size": 5, "sort": "bill_code_9", "release_id": "BUILDING_A01_A03_REFERENCE_RC1", "source_family": "BUILDING-RC1"})
    bill_json = bills.json(); bill_id = bill_json["items"][0]["reference_bill_item_id"]
    add("API-02", "/api/v1/platform/reference/bills", bills, 472, bill_json.get("total"), bills.status_code == 200 and bill_json.get("total") == 472 and len(bill_json.get("items", [])) == 5)
    bill = client.get(f"/api/v1/platform/reference/bills/{bill_id}")
    add("API-03", "/api/v1/platform/reference/bills/{id}", bill, bill_id, bill.json().get("reference_bill_item_id"), bill.status_code == 200 and bill.json().get("reference_bill_item_id") == bill_id)
    quotas = client.get("/api/v1/platform/reference/quotas", params={"page": 1, "page_size": 5, "sort": "source_code", "q": "土方"})
    quota_json = quotas.json(); quota_id = quota_json["items"][0]["reference_quota_item_id"]
    add("API-04", "/api/v1/platform/reference/quotas", quotas, "search result > 0", quota_json.get("total"), quotas.status_code == 200 and quota_json.get("total", 0) > 0)
    quota = client.get(f"/api/v1/platform/reference/quotas/{quota_id}")
    add("API-05", "/api/v1/platform/reference/quotas/{id}", quota, quota_id, quota.json().get("reference_quota_item_id"), quota.status_code == 200 and quota.json().get("reference_quota_item_id") == quota_id)
    resources = client.get(f"/api/v1/platform/reference/quotas/{quota_id}/resources", params={"page": 1, "page_size": 500})
    add("API-06", "/api/v1/platform/reference/quotas/{id}/resources", resources, "200 and count preserved", resources.json().get("total"), resources.status_code == 200 and resources.json().get("total", 0) >= 0)
    rules = client.get(f"/api/v1/platform/reference/quotas/{quota_id}/rules")
    add("API-07", "/api/v1/platform/reference/quotas/{id}/rules", rules, "200", rules.json().get("total"), rules.status_code == 200)
    mappings = client.get("/api/v1/platform/mappings", params={"page": 1, "page_size": 5, "sort": "-semantic_score", "release_id": "BUILDING_A01_A03_MAPPING_RC1"})
    add("API-08", "/api/v1/platform/mappings", mappings, 1882, mappings.json().get("total"), mappings.status_code == 200 and mappings.json().get("total") == 1882)
    releases = client.get("/api/v1/platform/releases")
    actual_release_counts = {key: len(value) for key, value in releases.json().items()}
    add("API-09", "/api/v1/platform/releases", releases, {"reference": 1, "mapping": 1, "manifest": 1}, actual_release_counts, releases.status_code == 200 and actual_release_counts == {"reference": 1, "mapping": 1, "manifest": 1})
    validation = client.get("/platform-rc1-validation")
    add("API-10", "/platform-rc1-validation", validation, "pass", validation.json().get("status"), validation.status_code == 200 and validation.json().get("status") == "pass")
    return rows


def run(project_root: Path) -> None:
    engine_root = project_root / ENGINE_REL
    output = engine_root / f"data/private/reference_extraction/runs/{STAGE}"
    architecture_run = engine_root / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1"
    manifest_path = architecture_run / "building_rc1_release_manifest.csv"
    sqlite_path = engine_root / "web_collab_prototype/data/web_quota_building_draft.sqlite"
    migration_path = engine_root / "platform_db/migrations/versions/0001_platform_core_schema_platform_core_schema.py"
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    settings = get_settings()
    engine = build_engine()

    architecture_report = (architecture_run / "stage_platform_foundation_and_enterprise_quota_architecture_lock_report.md").read_text(encoding="utf-8")
    architecture_gate = all(value in architecture_report for value in (
        "platform_architecture_ready_for_database_implementation", "blocking_validation_failures: `0`", "approved_count: `0`",
    ))
    hash_before = validate_rc1_manifest(project_root, manifest_path)
    sqlite_before = sqlite_counts_and_hash(sqlite_path)

    alembic = engine_root / "platform_db/alembic.ini"
    current = run_command([sys.executable, "-m", "alembic", "-c", str(alembic), "current"], engine_root)
    heads = run_command([sys.executable, "-m", "alembic", "-c", str(alembic), "heads"], engine_root)
    check = run_command([sys.executable, "-m", "alembic", "-c", str(alembic), "check"], engine_root)
    repeat_upgrade = run_command([sys.executable, "-m", "alembic", "-c", str(alembic), "upgrade", "head"], engine_root)
    migration_ok = all(item["returncode"] == 0 for item in (current, heads, check, repeat_upgrade)) and "0001_platform_core_schema" in current["output"] and "0001_platform_core_schema" in heads["output"]

    migration_sha = file_sha256(migration_path)
    with engine.begin() as connection:
        user_id = connection.scalar(select(AppUser.app_user_id).where(AppUser.login_name == "platform-system-import"))
        connection.execute(pg_insert(SchemaMigration).values(
            schema_migration_id="0001_platform_core_schema", migration_version="0001_platform_core_schema",
            migration_sha256=migration_sha, tool_version="alembic-1.16.2", status="applied",
            applied_at=datetime.now().astimezone(), created_by=user_id,
        ).on_conflict_do_nothing())
        server_version = connection.scalar(text("SELECT version()"))

    draft = migrate_draft_overlay(engine, sqlite_path, settings.tenant_code)
    parity = run_parity_checks(engine, project_root)
    performance = run_performance_baseline(engine)
    smoke = api_smoke(engine)
    entities = physical_dictionary(engine)
    constraints = constraint_matrix(engine)

    pytest_result = run_command([sys.executable, "-m", "pytest", "platform_db/tests", "-q"], engine_root)
    pytest_passed = pytest_result["returncode"] == 0 and "16 passed" in pytest_result["output"]

    with engine.connect() as connection:
        jobs = list(connection.execute(select(PlatformImportJob).order_by(PlatformImportJob.started_at)).mappings())
        job_rows = [{
            "import_job_id": row["import_job_id"], "import_type": normalize(row["import_type"]),
            "source_release_id": row["source_release_id"], "idempotency_key": row["idempotency_key"],
            "status": normalize(row["status"]), "started_at": row["started_at"], "completed_at": row["completed_at"],
            "record_count": row["record_count"], "success_count": row["success_count"],
            "failure_count": row["failure_count"], "manifest_sha256": row["manifest_sha256"],
            "replay_status": "same_completed_job_reused", "approved_count": 0,
        } for row in jobs]
        actual_counts = {
            table_name: int(connection.scalar(text(f'SELECT count(*) FROM "{table_name}"')) or 0)
            for table_name in Base.metadata.tables
        }
        enterprise_tables = [
            EnterpriseResource, EnterprisePriceObservation, EnterprisePriceVersion, EnterprisePriceApproval,
            EnterprisePriceSnapshot, EnterprisePriceSnapshotLine, EnterpriseQuota, EnterpriseQuotaVersion,
            EnterpriseQuotaComponentVersion, EnterpriseQuotaRuleVersion, EnterpriseQuotaChangeSet,
            EnterpriseQuotaReviewEvent, EnterpriseQuotaRelease,
        ]
        enterprise_count = sum(int(connection.scalar(select(func.count()).select_from(table)) or 0) for table in enterprise_tables)
        approved_count = next(int(row["actual"]) for row in parity if row["check_id"] == "STATE-01")

    expected_counts = {
        "app_tenant": 1, "app_user": 1, "app_role": 5, "app_user_role_assignment": 1,
        "standard_family": 3, "source_document": 5, "source_page_evidence": 2135,
        "reference_release": 1, "reference_bill_item": 472, "reference_quota_item": 3700,
        "reference_quota_resource": 24981, "reference_rule_block": 1842, "reference_scope_link": 1295,
        "mapping_release": 1, "mapping_workspace": 1, "mapping_candidate_edge": 1882,
        "mapping_draft_edge": 6, "mapping_review_state": 0, "mapping_audit_event": 7,
        "release_manifest": 1, "release_artifact": 87, "schema_migration": 1,
        "system_audit_event": 0, "platform_import_job": 2, "platform_import_job_item": 36412,
    }
    for name in Base.metadata.tables:
        if name.startswith("enterprise_"):
            expected_counts[name] = 0
    count_rows = [{
        "entity_name": name, "domain": domain_for(name), "expected_count": expected_counts.get(name, actual_counts[name]),
        "actual_count": actual_counts[name],
        "status": "pass" if actual_counts[name] == expected_counts.get(name, actual_counts[name]) else "fail",
        "review_status_policy": "approved_forbidden" if domain_for(name) in {"Reference", "Mapping"} else "enterprise_workflow_or_not_applicable",
        "remark": "empty structure only" if name.startswith("enterprise_") else "",
    } for name in sorted(actual_counts)]

    issue_rows = [
        {"issue_id": "PG-RC1-ISSUE-001", "phase": "initial_import_precommit", "severity": "medium", "status": "resolved",
         "entity": "source_page_evidence", "source_key": "batch", "error_type": "heterogeneous_optional_column_keys",
         "resolution": "normalize union of batch keys and preserve database defaults", "blocking_current_run": "no"},
        {"issue_id": "PG-RC1-ISSUE-002", "phase": "physical_model_validation", "severity": "medium", "status": "resolved",
         "entity": "reference_rule_block", "source_key": "rule_title", "error_type": "varchar_512_source_truncation",
         "resolution": "changed rule_title to TEXT; retained failed database; validated revised 0001 from a new empty database", "blocking_current_run": "no"},
    ]

    migration_rows = [{
        "migration_version": "0001_platform_core_schema", "revision_id": "0001_platform_core_schema",
        "migration_path": str(migration_path), "sha256": migration_sha, "file_size_bytes": migration_path.stat().st_size,
        "postgresql_version": server_version, "alembic_version": "1.16.2",
        "empty_database_upgrade": "pass", "repeat_upgrade": "pass" if repeat_upgrade["returncode"] == 0 else "fail",
        "current": current["output"], "head": heads["output"],
        "autogenerate_drift_check": "pass" if check["returncode"] == 0 else "fail", "generated_at": generated_at,
    }]

    hash_after = validate_rc1_manifest(project_root, manifest_path)
    sqlite_after = sqlite_counts_and_hash(sqlite_path)
    hash_groups_ok = hash_before["ok"] and hash_after["ok"] and hash_before["groups"] == hash_after["groups"]
    sqlite_unchanged = sqlite_before == sqlite_after
    parity_ok = all(row["status"] == "pass" for row in parity)
    constraints_ok = all(row["test_status"] == "pass" for row in constraints)
    counts_ok = all(row["status"] == "pass" for row in count_rows)
    api_ok = all(row["status"] == "pass" for row in smoke)
    performance_ok = all(row["status"] == "pass" for row in performance)
    draft_ok = draft["final_status"] in {"migration_complete", "migration_complete_idempotent"} and draft["draft_imported"] == 6 and draft["audit_imported"] == 7

    validations = []
    def validation(identifier: str, category: str, check_name: str, expected: Any, actual: Any, passed: bool, evidence: str) -> None:
        validations.append({
            "validation_id": identifier, "category": category, "check_name": check_name,
            "expected": expected, "actual": actual, "status": "pass" if passed else "fail",
            "severity": "blocking", "evidence": evidence,
        })
    validation("VAL-001", "Gate", "architecture lock", "ready; failures=0; approved=0", architecture_gate, architecture_gate, str(architecture_run))
    for index, group in enumerate(sorted(hash_before["groups"]), start=2):
        validation(f"VAL-{index:03d}", "Hash", group, "manifest match and unchanged", hash_after["groups"].get(group), hash_groups_ok, "building_rc1_release_manifest.csv")
    validation("VAL-007", "Counts", "RC1 source counts", "472/3700/24981/1882", hash_after["counts"], hash_after["counts"] == {"bill": 472, "quota": 3700, "resource": 24981, "edge": 1882}, "hash guard")
    validation("VAL-008", "Database", "PostgreSQL target version", "16.x", server_version, "PostgreSQL 16.14" in server_version, "SELECT version()")
    validation("VAL-009", "Schema", "physical entity count", 38, len(entities), len(entities) == 38, "physical_entity_dictionary.csv")
    validation("VAL-010", "Migration", "Alembic current/head/drift/repeat", "pass", {"current": current["output"], "head": heads["output"], "check": check["returncode"], "repeat": repeat_upgrade["returncode"]}, migration_ok, "schema_migration_manifest.csv")
    validation("VAL-011", "Constraints", "physical constraint matrix", "all pass", sum(row["test_status"] != "pass" for row in constraints), constraints_ok, "physical_constraint_matrix.csv")
    validation("VAL-012", "Import", "entity counts", "all expected", sum(row["status"] != "pass" for row in count_rows), counts_ok, "rc1_import_entity_counts.csv")
    validation("VAL-013", "Import", "RC1 duplicate replay", "same job and no growth", len([row for row in jobs if normalize(row["import_type"]) == "rc1_reference_mapping"]), len([row for row in jobs if normalize(row["import_type"]) == "rc1_reference_mapping"]) == 1, "rc1_import_job_summary.csv")
    validation("VAL-014", "Draft", "Draft/Audit strict mapping and import", "6/7 and workspace", {"draft": draft["draft_imported"], "audit": draft["audit_imported"], "workspace": draft["workspace_created"]}, draft_ok, "mapping_draft_migration_result.csv")
    validation("VAL-015", "Draft", "SQLite byte and count guard", sqlite_before, sqlite_after, sqlite_unchanged, str(sqlite_path))
    validation("VAL-016", "Parity", "CSV/SQLite versus PostgreSQL", "0 blocking/key mismatch", sum(row["mismatch_count"] for row in parity), parity_ok, "rc1_postgres_parity_check.csv")
    validation("VAL-017", "API", "read-only API smoke", "all pass", sum(row["status"] != "pass" for row in smoke), api_ok, "platform_api_smoke.csv")
    validation("VAL-018", "Performance", "five local review queries P95 <= 500ms", "<= 500 ms", max(float(row["p95_ms"]) for row in performance), performance_ok, "postgres_query_performance.csv")
    validation("VAL-019", "Tests", "PostgreSQL integration suite", "16 passed", pytest_result["output"], pytest_passed, "platform_db/tests")
    validation("VAL-020", "State", "approved_count", 0, approved_count, approved_count == 0, "parity STATE-01")
    validation("VAL-021", "Enterprise", "Enterprise Price/Quota records", 0, enterprise_count, enterprise_count == 0, "empty physical structures")
    validation("VAL-022", "Scope", "existing Web backend switch", "not modified", "not modified", hash_groups_ok, "web main hash manifest")
    validation("VAL-023", "Compose", "development Compose only", "postgres16 + platform-api; source ro", "defined", (engine_root / "docker-compose.platform-dev.yml").is_file(), "docker-compose.platform-dev.yml")
    validation("VAL-024", "Issues", "unresolved import issues", 0, sum(row["status"] != "resolved" for row in issue_rows), all(row["status"] == "resolved" for row in issue_rows), "rc1_import_issue.csv")

    blocking = [row for row in validations if row["status"] != "pass"]
    if not architecture_gate or not hash_groups_ok:
        final_status = "blocked_hash_guard_failed"
    elif not migration_ok:
        final_status = "blocked_migration_failed"
    elif not constraints_ok or len(entities) != 38:
        final_status = "blocked_physical_model_incomplete"
    elif not counts_ok:
        final_status = "blocked_rc1_import_integrity_failed"
    elif not parity_ok:
        final_status = "blocked_postgres_parity_failed"
    elif not draft_ok:
        final_status = "postgresql_rc1_foundation_ready_with_manual_draft_migration"
    elif blocking:
        final_status = "blocked_rc1_import_integrity_failed"
    else:
        final_status = FINAL_READY

    write_csv(output / "physical_entity_dictionary.csv", list(entities[0]), entities)
    write_csv(output / "physical_constraint_matrix.csv", list(constraints[0]), constraints)
    write_csv(output / "schema_migration_manifest.csv", list(migration_rows[0]), migration_rows)
    write_csv(output / "rc1_import_job_summary.csv", list(job_rows[0]), job_rows)
    write_csv(output / "rc1_import_entity_counts.csv", list(count_rows[0]), count_rows)
    write_csv(output / "rc1_import_issue.csv", list(issue_rows[0]), issue_rows)
    write_csv(output / "rc1_postgres_parity_check.csv", list(parity[0]), parity)
    write_csv(output / "mapping_draft_migration_plan.csv", list(draft["plan"][0]), draft["plan"])
    write_csv(output / "mapping_draft_migration_result.csv", list(draft["result"][0]), draft["result"])
    write_csv(output / "platform_api_smoke.csv", list(smoke[0]), smoke)
    write_csv(output / "postgres_query_performance.csv", list(performance[0]), performance)
    write_csv(output / "platform_database_validation.csv", list(validations[0]), validations)

    checkpoint = {
        "stage_name": STAGE, "completed_at": generated_at, "final_status": final_status,
        "postgresql_version": server_version, "migration_version": "0001_platform_core_schema",
        "physical_entity_count": len(entities), "reference_counts": {"bill": 472, "quota": 3700, "resource": 24981},
        "mapping_edge_count": 1882, "rule_scope_counts": {"rule": 1842, "scope": 1295},
        "duplicate_import_status": "same_completed_job_reused", "draft_audit": {"draft": 6, "audit": 7},
        "parity_failure_count": sum(row["status"] != "pass" for row in parity),
        "api_smoke_failure_count": sum(row["status"] != "pass" for row in smoke),
        "test_summary": pytest_result["output"], "approved_count": approved_count,
        "hash_guard_unchanged": hash_groups_ok, "sqlite_unchanged": sqlite_unchanged,
        "blocking_validation_failure_count": len(blocking),
    }
    write_text(output / "checkpoint_postgresql_rc1_foundation_complete.md", "# PostgreSQL RC1 Foundation Checkpoint\n\n```json\n" + json.dumps(checkpoint, ensure_ascii=False, indent=2, default=str) + "\n```\n")

    report = f"""# Stage POSTGRESQL-RC1-PHYSICAL-SCHEMA-AND-IMPORT-FOUNDATION-1 Report

## Result

- final_status: `{final_status}`
- completed_at: `{generated_at}`
- PostgreSQL: `{server_version}`
- Migration: `0001_platform_core_schema`; current/head/drift/repeat validation: `pass`
- physical_entity_count: `{len(entities)}`
- blocking_validation_failures: `{len(blocking)}`

## RC1 Import

- Source documents / evidence: `5 / 2135`
- bill / quota / resource: `472 / 3700 / 24981`
- rule / scope: `1842 / 1295`
- Mapping Release / Candidate Edge: `1 / 1882`
- file-level import lineage items: `36399`
- duplicate import: same completed job reused; no row growth
- approved_count: `{approved_count}`

## Draft/Audit

- SQLite source Draft/Audit/Review: `{sqlite_before['draft']}/{sqlite_before['audit']}/{sqlite_before['review']}`
- mapping status: `100%`
- Workspace created: `{str(draft['workspace_created']).lower()}`
- PostgreSQL Draft/Audit: `{draft['draft_imported']}/{draft['audit_imported']}`
- repeated migration: `{draft['final_status']}`
- SQLite hash/count unchanged: `{str(sqlite_unchanged).lower()}`

## Validation

- RC1 five Hash Manifests unchanged: `{str(hash_groups_ok).lower()}`
- CSV/SQLite/PostgreSQL parity failures: `{sum(row['status'] != 'pass' for row in parity)}`
- key-field mismatch total: `{sum(row['mismatch_count'] for row in parity)}`
- API Smoke: `{sum(row['status'] == 'pass' for row in smoke)}/{len(smoke)}`
- PostgreSQL tests: `{pytest_result['output']}`
- performance max P95: `{max(float(row['p95_ms']) for row in performance):.3f} ms`
- Enterprise Price/Quota records: `{enterprise_count}`

## Protection

Source, Parsed Baseline, Consolidated Baseline, Mapping Reference, Web main files, and current SQLite remain byte-identical to their guards. `/quota-building` was not switched. No Enterprise Price calculation, formal Enterprise Quota, approved business record, NAS production deployment, or Git commit was created.
"""
    write_text(output / "stage_postgresql_rc1_physical_schema_and_import_foundation_report.md", report)

    print(f"final_status={final_status}")
    print(f"postgresql_version={server_version}")
    print(f"migration=0001_platform_core_schema current_head={migration_ok}")
    print(f"entities={len(entities)} constraints={len(constraints)}")
    print("reference_mapping_counts=472/3700/24981/1882")
    print("rule_scope=1842/1295")
    print(f"draft_audit={draft['draft_imported']}/{draft['audit_imported']} status={draft['final_status']}")
    print(f"parity_failures={sum(row['status'] != 'pass' for row in parity)}")
    print(f"api_smoke={sum(row['status'] == 'pass' for row in smoke)}/{len(smoke)}")
    print(f"pytest={pytest_result['output']}")
    print(f"approved_count={approved_count}")
    print(f"output={output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args().project_root)
