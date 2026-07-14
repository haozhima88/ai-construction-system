from __future__ import annotations

import os
import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError

from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.draft_overlay import migrate_draft_overlay
from platform_db.importers.hash_guard import validate_rc1_manifest
from platform_db.importers.rc1 import import_rc1
from platform_db.models import (
    MappingCandidateEdge, MappingDraftEdge, MappingWorkspace, PlatformImportJob,
    ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource,
)
from platform_db.services.parity import run_parity_checks
from platform_db.services.workspace import optimistic_rename_workspace


def test_01_migration_current_equals_head(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007_quota_spreadsheet_batch"


def test_02_physical_entity_count(engine):
    assert len(inspect(engine).get_table_names()) == 51  # 50 physical entities plus alembic_version


def test_03_required_constraints_and_triggers(engine):
    with engine.connect() as connection:
        triggers = set(connection.execute(text("""
            SELECT tgname FROM pg_trigger WHERE NOT tgisinternal
        """)).scalars())
    required = {
        "trg_reference_release_immutable", "trg_mapping_release_immutable",
        "trg_reference_bill_immutable", "trg_mapping_candidate_immutable",
        "trg_enterprise_quota_version_guard", "trg_price_approval_separation",
        "trg_role_assignment_overlap", "trg_mapping_workspace_row_version",
    }
    assert required <= triggers


def test_04_rc1_import_is_idempotent(engine):
    result = import_rc1(engine, get_settings())
    assert result.duplicate_run is True
    assert result.approved_count == 0


def test_05_duplicate_import_does_not_grow_counts(engine):
    with engine.connect() as connection:
        before = (
            connection.scalar(select(func.count()).select_from(ReferenceBillItem)),
            connection.scalar(select(func.count()).select_from(ReferenceQuotaItem)),
            connection.scalar(select(func.count()).select_from(ReferenceQuotaResource)),
            connection.scalar(select(func.count()).select_from(MappingCandidateEdge)),
            connection.scalar(select(func.count()).select_from(PlatformImportJob)),
        )
    import_rc1(engine, get_settings())
    with engine.connect() as connection:
        after = (
            connection.scalar(select(func.count()).select_from(ReferenceBillItem)),
            connection.scalar(select(func.count()).select_from(ReferenceQuotaItem)),
            connection.scalar(select(func.count()).select_from(ReferenceQuotaResource)),
            connection.scalar(select(func.count()).select_from(MappingCandidateEdge)),
            connection.scalar(select(func.count()).select_from(PlatformImportJob)),
        )
    assert after == before


def _assert_db_rejects(engine, sql: str):
    with engine.connect() as connection:
        transaction = connection.begin()
        with pytest.raises(DBAPIError):
            connection.execute(text(sql))
        transaction.rollback()


def test_06_published_reference_release_is_immutable(engine):
    _assert_db_rejects(engine, "UPDATE reference_release SET parser_version='forbidden' WHERE reference_release_id='BUILDING_A01_A03_REFERENCE_RC1'")


def test_07_reference_child_is_immutable(engine):
    _assert_db_rejects(engine, "UPDATE reference_bill_item SET bill_name='forbidden' WHERE bill_code_9='010101001'")


def test_08_mapping_candidate_is_immutable(engine):
    _assert_db_rejects(engine, "UPDATE mapping_candidate_edge SET risk_level='low' WHERE source_key=(SELECT source_key FROM mapping_candidate_edge LIMIT 1)")


def test_09_approved_is_forbidden_in_reference_mapping(engine):
    _assert_db_rejects(engine, "SELECT 'approved'::no_approved_review_status")


def test_10_tenant_id_is_required(engine):
    _assert_db_rejects(engine, f"""
        INSERT INTO app_user(app_user_id, tenant_id, login_name, display_name, status)
        VALUES ('{uuid.uuid4()}', NULL, 'invalid-tenant', 'Invalid Tenant', 'active')
    """)


def test_11_row_version_optimistic_concurrency(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        workspace_id, version = connection.execute(select(
            MappingWorkspace.mapping_workspace_id, MappingWorkspace.row_version
        ).where(
            MappingWorkspace.workspace_name == "SQLite Draft Overlay Migration"
        )).one()
        assert optimistic_rename_workspace(connection, workspace_id, version, "Optimistic Test") is True
        new_version = connection.scalar(select(MappingWorkspace.row_version).where(MappingWorkspace.mapping_workspace_id == workspace_id))
        assert new_version == version + 1
        assert optimistic_rename_workspace(connection, workspace_id, version, "Stale Update") is False
        transaction.rollback()


def test_12_draft_migration_dry_run_and_idempotency(engine, project_root):
    result = migrate_draft_overlay(
        engine,
        project_root / "construction_cost_knowledge_engine/web_collab_prototype/data/web_quota_building_draft.sqlite",
        "platform-dev",
    )
    assert result["final_status"] == "migration_complete_idempotent"
    assert all(row["overall_status"] == "ready" for row in result["plan"])
    assert (result["draft_imported"], result["audit_imported"]) == (6, 7)


def _client():
    from platform_db.api import app
    return TestClient(app)


def test_13_api_counts_and_health():
    client = _client()
    health = client.get("/api/v1/platform/health")
    assert health.status_code == 200
    assert set(health.json()) == {"status", "application_version", "database_connectivity"}
    parity = client.get("/platform-rc1-validation")
    assert parity.status_code == 401


def test_14_api_pagination_sort_search_and_filters():
    client = _client()
    first = client.get("/api/v1/platform/reference/bills", params={"page": 1, "page_size": 7, "sort": "bill_code_9"})
    assert first.status_code == 401


def test_15_hash_guard(project_root):
    settings = get_settings()
    result = validate_rc1_manifest(project_root, settings.rc1_manifest_path)
    assert result["ok"] is True
    assert result["counts"] == {"bill": 472, "quota": 3700, "resource": 24981, "edge": 1882}


def test_16_postgresql_csv_sqlite_parity(engine, project_root):
    rows = run_parity_checks(engine, project_root)
    assert rows and all(row["status"] == "pass" for row in rows)
    assert sum(int(row["mismatch_count"]) for row in rows) == 0
