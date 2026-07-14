from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from platform_db.models import (
    AppTenant, AppUser, MappingAuditEvent, MappingCandidateEdge, MappingDraftEdge,
    MappingWorkspace, PlatformImportJob, PlatformImportJobItem, ReferenceBillItem,
    ReferenceQuotaItem,
)

from .common import file_sha256, payload_sha256, stable_uuid
from .rc1 import MAPPING_RELEASE_ID, SYSTEM_USER_KEY


def _sqlite_rows(path: Path, table: str) -> list[dict[str, Any]]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]


def _json(value: str | None) -> dict[str, Any] | None:
    return json.loads(value) if value and value.strip() else None


def migrate_draft_overlay(engine: Engine, sqlite_path: Path, tenant_code: str) -> dict[str, Any]:
    drafts = _sqlite_rows(sqlite_path, "mapping_drafts")
    audits = _sqlite_rows(sqlite_path, "audit_log")
    reviews = _sqlite_rows(sqlite_path, "review_states")
    sqlite_sha = file_sha256(sqlite_path)
    idempotency_key = f"mapping-draft:{sqlite_sha}"
    plan: list[dict[str, Any]] = []

    with engine.begin() as connection:
        tenant_id = connection.scalar(select(AppTenant.tenant_id).where(AppTenant.tenant_code == tenant_code))
        user_id = connection.scalar(select(AppUser.app_user_id).where(
            AppUser.tenant_id == tenant_id, AppUser.login_name == SYSTEM_USER_KEY,
        ))
        if not tenant_id or not user_id:
            raise RuntimeError("RC1 tenant/system user must exist before Draft migration")
        bill_map = dict(connection.execute(
            select(ReferenceBillItem.bill_code_9, ReferenceBillItem.reference_bill_item_id)
        ).tuples().all())
        quota_map = dict(connection.execute(
            select(ReferenceQuotaItem.quota_uid, ReferenceQuotaItem.reference_quota_item_id)
        ).tuples().all())
        edge_map = dict(connection.execute(
            select(MappingCandidateEdge.source_key, MappingCandidateEdge.mapping_candidate_edge_id)
        ).tuples().all())

        draft_key_map: dict[str, uuid.UUID] = {}
        for row in drafts:
            checks = {
                "source_bill": row["source_bill_code_9"] in bill_map,
                "target_bill": not row["target_bill_code_9"] or row["target_bill_code_9"] in bill_map,
                "quota": row["quota_uid"] in quota_map,
                "mapping_edge": row["source_edge_id"] in edge_map,
            }
            target_id = stable_uuid("mapping_draft_edge", row["draft_id"])
            draft_key_map[row["draft_id"]] = target_id
            plan.append({
                "source_type": "draft", "source_key": row["draft_id"],
                "bill_mapping_status": "mapped" if checks["source_bill"] and checks["target_bill"] else "unmapped",
                "quota_mapping_status": "mapped" if checks["quota"] else "unmapped",
                "edge_mapping_status": "mapped" if checks["mapping_edge"] else "unmapped",
                "audit_order_status": "not_applicable", "target_id": str(target_id),
                "overall_status": "ready" if all(checks.values()) else "manual_migration_required",
                "remark": "" if all(checks.values()) else json.dumps(checks, ensure_ascii=False),
            })

        audit_times = [datetime.fromisoformat(row["created_at"]) for row in audits]
        audit_order_ok = audit_times == sorted(audit_times) and len({row["audit_id"] for row in audits}) == len(audits)
        for row in audits:
            draft_ok = not row["draft_id"] or row["draft_id"] in draft_key_map
            bill_ok = not row["bill_code_9"] or row["bill_code_9"] in bill_map
            quota_ok = not row["quota_uid"] or row["quota_uid"] in quota_map
            ready = draft_ok and bill_ok and quota_ok and audit_order_ok
            plan.append({
                "source_type": "audit", "source_key": row["audit_id"],
                "bill_mapping_status": "mapped" if bill_ok else "unmapped",
                "quota_mapping_status": "mapped" if quota_ok else "unmapped",
                "edge_mapping_status": "not_applicable", "audit_order_status": "complete" if audit_order_ok else "incomplete",
                "target_id": str(stable_uuid("mapping_audit_event", row["audit_id"])),
                "overall_status": "ready" if ready else "manual_migration_required",
                "remark": "" if ready else "Draft/Audit key or ordering mismatch",
            })

        ready = all(row["overall_status"] == "ready" for row in plan)
        if not ready:
            return {
                "final_status": "manual_migration_required", "plan": plan, "result": [],
                "draft_source_count": len(drafts), "audit_source_count": len(audits),
                "review_source_count": len(reviews), "workspace_created": False,
                "draft_imported": 0, "audit_imported": 0, "sqlite_sha256": sqlite_sha,
            }

        workspace_id = stable_uuid("mapping_workspace", f"{tenant_code}:{MAPPING_RELEASE_ID}:sqlite-overlay")
        connection.execute(pg_insert(MappingWorkspace).values(
            mapping_workspace_id=workspace_id, tenant_id=tenant_id, mapping_release_id=MAPPING_RELEASE_ID,
            workspace_name="SQLite Draft Overlay Migration", workspace_status="active", created_by=user_id,
        ).on_conflict_do_nothing())

        existing_job = connection.execute(select(PlatformImportJob).where(
            PlatformImportJob.tenant_id == tenant_id,
            PlatformImportJob.idempotency_key == idempotency_key,
            PlatformImportJob.status == "completed",
        )).mappings().first()
        if existing_job:
            return {
                "final_status": "migration_complete_idempotent", "plan": plan, "result": [
                    {"entity": "mapping_workspace", "source_count": 1, "imported_count": 1, "status": "unchanged"},
                    {"entity": "mapping_draft_edge", "source_count": len(drafts), "imported_count": len(drafts), "status": "unchanged"},
                    {"entity": "mapping_audit_event", "source_count": len(audits), "imported_count": len(audits), "status": "unchanged"},
                ], "draft_source_count": len(drafts), "audit_source_count": len(audits),
                "review_source_count": len(reviews), "workspace_created": True,
                "draft_imported": len(drafts), "audit_imported": len(audits), "sqlite_sha256": sqlite_sha,
            }

        job_id = stable_uuid("platform_import_job", idempotency_key)
        connection.execute(insert(PlatformImportJob).values(
            import_job_id=job_id, tenant_id=tenant_id, import_type="mapping_draft_overlay",
            source_release_id=MAPPING_RELEASE_ID, idempotency_key=idempotency_key, status="running",
            started_at=datetime.now(timezone.utc), record_count=len(drafts) + len(audits), success_count=0,
            failure_count=0, manifest_sha256=sqlite_sha, created_by=user_id,
        ))
        import_items: list[dict[str, Any]] = []
        for row in drafts:
            target_id = draft_key_map[row["draft_id"]]
            connection.execute(pg_insert(MappingDraftEdge).values(
                mapping_draft_edge_id=target_id, tenant_id=tenant_id, mapping_workspace_id=workspace_id,
                mapping_release_id=MAPPING_RELEASE_ID, mapping_candidate_edge_id=edge_map[row["source_edge_id"]],
                target_bill_item_id=bill_map.get(row["target_bill_code_9"]), source_draft_key=row["draft_id"],
                action_type=row["action_type"], relation_type=row["relation_type"],
                draft_status=row["draft_status"], review_status="not_reviewed",
                operation_reason=row["operation_reason"] or None, revision_no=1,
                source_payload=row, created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]), created_by=user_id,
            ).on_conflict_do_nothing())
            import_items.append({
                "import_job_item_id": stable_uuid("import_job_item", f"{job_id}:draft:{row['draft_id']}"),
                "import_job_id": job_id, "source_entity": "mapping_drafts", "source_key": row["draft_id"],
                "target_entity": "mapping_draft_edge", "target_id": target_id, "status": "imported",
                "payload_sha256": payload_sha256(row), "created_by": user_id,
            })
        for row in audits:
            target_id = stable_uuid("mapping_audit_event", row["audit_id"])
            connection.execute(pg_insert(MappingAuditEvent).values(
                mapping_audit_event_id=target_id, tenant_id=tenant_id, mapping_workspace_id=workspace_id,
                mapping_draft_edge_id=draft_key_map.get(row["draft_id"]), actor_user_id=user_id,
                source_audit_key=row["audit_id"], event_type=row["event_type"], event_at=row["created_at"],
                before_payload=_json(row["before_json"]), after_payload=_json(row["after_json"]),
                created_at=datetime.fromisoformat(row["created_at"]), created_by=user_id,
            ).on_conflict_do_nothing())
            import_items.append({
                "import_job_item_id": stable_uuid("import_job_item", f"{job_id}:audit:{row['audit_id']}"),
                "import_job_id": job_id, "source_entity": "audit_log", "source_key": row["audit_id"],
                "target_entity": "mapping_audit_event", "target_id": target_id, "status": "imported",
                "payload_sha256": payload_sha256(row), "created_by": user_id,
            })
        connection.execute(insert(PlatformImportJobItem), import_items)
        connection.execute(update(PlatformImportJob).where(PlatformImportJob.import_job_id == job_id).values(
            status="completed", completed_at=datetime.now(timezone.utc), success_count=len(import_items), updated_by=user_id,
        ))
        result = [
            {"entity": "mapping_workspace", "source_count": 1, "imported_count": 1, "status": "imported"},
            {"entity": "mapping_draft_edge", "source_count": len(drafts), "imported_count": len(drafts), "status": "imported"},
            {"entity": "mapping_audit_event", "source_count": len(audits), "imported_count": len(audits), "status": "imported"},
        ]
        return {
            "final_status": "migration_complete", "plan": plan, "result": result,
            "draft_source_count": len(drafts), "audit_source_count": len(audits),
            "review_source_count": len(reviews), "workspace_created": True,
            "draft_imported": len(drafts), "audit_imported": len(audits), "sqlite_sha256": sqlite_sha,
        }
