from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import String, cast, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from platform_db.config import Settings, get_settings
from platform_db.models import (
    AppRole, AppTenant, AppUser, AppUserRoleAssignment, MappingCandidateEdge, MappingRelease,
    PlatformImportJob, PlatformImportJobItem, ReferenceBillItem, ReferenceQuotaItem,
    ReferenceQuotaResource, ReferenceRelease, ReferenceRuleBlock, ReferenceScopeLink,
    ReleaseArtifact, ReleaseManifest, SourceDocument, SourcePageEvidence, StandardFamily,
)

from .common import as_decimal, as_float, as_int, chunks, file_sha256, payload_sha256, read_csv, stable_uuid
from .hash_guard import validate_rc1_manifest


REFERENCE_RELEASE_ID = "BUILDING_A01_A03_REFERENCE_RC1"
MAPPING_RELEASE_ID = "BUILDING_A01_A03_MAPPING_RC1"
SYSTEM_USER_KEY = "platform-system-import"


@dataclass(frozen=True)
class Rc1ImportResult:
    import_job_id: uuid.UUID
    duplicate_run: bool
    entity_counts: dict[str, int]
    imported_item_count: int
    approved_count: int
    manifest_sha256: str


def _insert_many(connection: Connection, table, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys = set().union(*(row.keys() for row in rows))
    normalized = [{key: row.get(key) for key in keys} for row in rows]
    for batch in chunks(normalized):
        connection.execute(pg_insert(table).values(batch).on_conflict_do_nothing())


def _count(connection: Connection, table) -> int:
    return int(connection.scalar(select(func.count()).select_from(table)) or 0)


def _bootstrap(connection: Connection, tenant_code: str) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id = stable_uuid("app_tenant", tenant_code)
    user_id = stable_uuid("app_user", SYSTEM_USER_KEY)
    connection.execute(pg_insert(AppTenant).values(
        tenant_id=tenant_id, tenant_code=tenant_code, tenant_name="Platform Development Tenant", status="active",
    ).on_conflict_do_nothing())
    connection.execute(pg_insert(AppUser).values(
        app_user_id=user_id, tenant_id=tenant_id, login_name=SYSTEM_USER_KEY,
        login_name_normalized=SYSTEM_USER_KEY, display_name="Platform System Import", status="active",
        is_service_account=True, must_change_password=False,
    ).on_conflict_do_nothing())
    for role_code in ("viewer", "reviewer", "editor", "approver", "administrator"):
        role_id = stable_uuid("app_role", role_code)
        connection.execute(pg_insert(AppRole).values(
            app_role_id=role_id, role_code=role_code, role_name=role_code.title(),
            policy_version=1, status="active",
        ).on_conflict_do_nothing())
    administrator_id = stable_uuid("app_role", "administrator")
    connection.execute(pg_insert(AppUserRoleAssignment).values(
        assignment_id=stable_uuid("role_assignment", f"{tenant_code}:{SYSTEM_USER_KEY}:administrator"),
        tenant_id=tenant_id, app_user_id=user_id, app_role_id=administrator_id,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc), assigned_by=user_id,
        status="active", created_by=user_id,
    ).on_conflict_do_nothing())
    return tenant_id, user_id


def _job_item(job_id: uuid.UUID, source_entity: str, source_key: str, target_entity: str,
              target_id: uuid.UUID | None, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "import_job_item_id": stable_uuid("import_job_item", f"{job_id}:{source_entity}:{source_key}"),
        "import_job_id": job_id, "source_entity": source_entity, "source_key": source_key,
        "target_entity": target_entity, "target_id": target_id, "status": "imported",
        "payload_sha256": payload_sha256(row),
    }


def import_rc1(engine: Engine, settings: Settings | None = None) -> Rc1ImportResult:
    settings = settings or get_settings()
    guard = validate_rc1_manifest(settings.project_root, settings.rc1_manifest_path)
    if not guard["ok"]:
        raise RuntimeError(f"RC1 hash/count guard failed: {guard['failures']}")
    manifest_sha = file_sha256(settings.rc1_manifest_path)
    idempotency_key = f"rc1:{manifest_sha}"
    runs = settings.project_root / "construction_cost_knowledge_engine/data/private/reference_extraction/runs"

    with engine.begin() as connection:
        tenant_id, user_id = _bootstrap(connection, settings.tenant_code)
        existing = connection.execute(select(PlatformImportJob).where(
            PlatformImportJob.tenant_id == tenant_id,
            PlatformImportJob.idempotency_key == idempotency_key,
            PlatformImportJob.status == "completed",
        )).mappings().first()
        if existing:
            return Rc1ImportResult(
                import_job_id=existing["import_job_id"], duplicate_run=True,
                entity_counts=_entity_counts(connection), imported_item_count=existing["success_count"],
                approved_count=_approved_count(connection), manifest_sha256=manifest_sha,
            )

        job_id = stable_uuid("platform_import_job", idempotency_key)
        connection.execute(insert(PlatformImportJob).values(
            import_job_id=job_id, tenant_id=tenant_id, import_type="rc1_reference_mapping",
            source_release_id=REFERENCE_RELEASE_ID, idempotency_key=idempotency_key,
            status="running", started_at=datetime.now(timezone.utc), manifest_sha256=manifest_sha,
            record_count=0, success_count=0, failure_count=0, created_by=user_id,
        ))
        items: list[dict[str, Any]] = []

        family_specs = [
            ("GB50854-2024", "GB/T 50854-2024", "2024", "gb50854_dual_source_v1"),
            ("GD2018-BUILDING-A", "GD2018 Building A01-A03", "2018", "gd2018_building_a_v2"),
            ("BUILDING-RC1", "Building Reference Composite RC1", "RC1", "building_composite_v1"),
        ]
        family_ids: dict[str, uuid.UUID] = {}
        family_rows = []
        for code, name, edition, adapter in family_specs:
            family_id = stable_uuid("standard_family", code)
            family_ids[code] = family_id
            family_rows.append({
                "standard_family_id": family_id, "family_code": code, "family_name": name,
                "edition": edition, "adapter_id": adapter, "status": "active", "created_by": user_id,
            })
        _insert_many(connection, StandardFamily, family_rows)

        role_registry = read_csv(runs / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1/gb50854_source_role_registry.csv")
        source_rows: list[dict[str, Any]] = []
        source_ids: dict[str, uuid.UUID] = {}
        for raw in role_registry:
            if raw["object_type"] != "source_document":
                continue
            source_id = stable_uuid("source_document", raw["source_id"])
            source_ids[raw["source_id"]] = source_id
            normalized = {
                "source_document_id": source_id, "standard_family_id": family_ids["GB50854-2024"],
                "source_key": raw["source_id"], "document_name": raw["display_name"],
                "actual_path": raw["actual_path"], "sha256": raw["sha256"].lower(),
                "file_size_bytes": int(raw["file_size_bytes"]), "page_count": as_int(raw["page_count"]),
                "source_role": raw["source_role"], "authority_status": raw["authority_status"],
                "readable_status": raw["readable_status"], "review_status": "pending", "created_by": user_id,
            }
            normalized["payload_sha256"] = payload_sha256(raw)
            source_rows.append(normalized)
            items.append(_job_item(job_id, "source_document", raw["source_id"], "source_document", source_id, raw))

        gd_docs = read_csv(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_source_documents.csv")
        for raw in gd_docs:
            source_key = raw["source_document_id"]
            source_id = stable_uuid("source_document", source_key)
            source_ids[source_key] = source_id
            path = Path(raw["source_file"])
            normalized = {
                "source_document_id": source_id, "standard_family_id": family_ids["GD2018-BUILDING-A"],
                "source_key": source_key, "document_name": path.name, "actual_path": str(path),
                "sha256": raw["source_sha256"].lower(), "file_size_bytes": path.stat().st_size,
                "page_count": int(raw["page_count"]), "source_role": "authority_source",
                "authority_status": "official_provincial_standard_evidence", "readable_status": "readable",
                "review_status": "pending", "created_by": user_id, "payload_sha256": payload_sha256(raw),
            }
            source_rows.append(normalized)
            items.append(_job_item(job_id, "source_document", source_key, "source_document", source_id, raw))
        _insert_many(connection, SourceDocument, source_rows)

        manifest = read_csv(settings.rc1_manifest_path)
        first_manifest = manifest[0]
        release_manifest_id = stable_uuid("release_manifest", "BUILDING_RC1")
        connection.execute(pg_insert(ReleaseManifest).values(
            release_manifest_id=release_manifest_id, manifest_code="BUILDING_RC1",
            application_version=first_manifest["application_version"], database_schema_version="0001_platform_core_schema",
            reference_release_id=REFERENCE_RELEASE_ID, mapping_release_id=MAPPING_RELEASE_ID,
            enterprise_price_release_id=None, enterprise_quota_release_id=None,
            source_hash_manifest=first_manifest["source_hash_manifest"], manifest_sha256=manifest_sha,
            docker_image_tag=first_manifest["docker_image_tag"],
            generated_at=datetime.fromisoformat(first_manifest["generated_at"]), status="frozen", created_by=user_id,
        ).on_conflict_do_nothing())
        artifact_rows = []
        for raw in manifest:
            source_key = raw["manifest_entry_id"]
            artifact_id = stable_uuid("release_artifact", source_key)
            artifact_rows.append({
                "release_artifact_id": artifact_id, "release_manifest_id": release_manifest_id,
                "artifact_group": raw["artifact_group"], "artifact_role": raw["artifact_role"],
                "artifact_id": raw["artifact_id"], "artifact_path": raw["artifact_path"],
                "sha256": raw["sha256"], "file_size_bytes": int(raw["file_size_bytes"] or 0),
                "record_count": as_int(raw["record_count"]), "immutable": raw["immutable"] == "yes",
                "status": raw["status"], "created_by": user_id,
            })
            items.append(_job_item(job_id, "release_artifact", source_key, "release_artifact", artifact_id, raw))
        _insert_many(connection, ReleaseArtifact, artifact_rows)

        group_hash = {row["artifact_group"]: row["sha256"] for row in manifest if row["artifact_path"].startswith("manifest://")}
        connection.execute(pg_insert(ReferenceRelease).values(
            reference_release_id=REFERENCE_RELEASE_ID, standard_family_id=family_ids["BUILDING-RC1"],
            semantic_version="RC1", release_status="published",
            source_hash_manifest=group_hash["source_hash_manifest"],
            parser_version=first_manifest["parser_version"], created_by=user_id,
        ).on_conflict_do_nothing())

        docx_id = source_ids["GB50854_EXTRACTION_PROXY_DOCX_2024"]
        authority_pdf_id = source_ids["GB50854_AUTHORITY_PDF_2024"]
        bill_raw = read_csv(runs / "GB50854_2024_stageB_docx_full/bill_item_reference_all_candidate.csv")
        bill_rows = []
        bill_ids: dict[str, uuid.UUID] = {}
        bill_code_ids: dict[str, uuid.UUID] = {}
        for raw in bill_raw:
            source_key = raw["bill_reference_id"]
            row_id = stable_uuid("reference_bill_item", source_key)
            bill_ids[source_key] = row_id
            bill_code_ids[raw["bill_code_9"]] = row_id
            bill_rows.append({
                "reference_bill_item_id": row_id, "reference_release_id": REFERENCE_RELEASE_ID,
                "source_document_id": docx_id, "source_key": source_key, "bill_code_9": raw["bill_code_9"],
                "bill_name": raw["bill_name"], "appendix_code": raw["appendix_code"],
                "appendix_name": raw["appendix_name"], "section_code": raw["section_code"],
                "section_name": raw["section_name"], "unit": raw["unit"],
                "project_feature_raw": raw["project_feature_raw"] or None,
                "quantity_calculation_rule": raw["quantity_calculation_rule"] or None,
                "work_content_raw": raw["work_content_raw"] or None,
                "source_heading_path": raw["source_heading_path"],
                "source_table_index": as_int(raw["source_table_index"]), "review_status": "pending",
                "payload_sha256": payload_sha256(raw), "created_by": user_id,
            })
            items.append(_job_item(job_id, "bill_item", source_key, "reference_bill_item", row_id, raw))
        _insert_many(connection, ReferenceBillItem, bill_rows)

        quota_price = {row["quota_uid"]: row for row in read_csv(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_quota_price_snapshots.csv")}
        quota_raw = read_csv(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_quota_items.csv")
        quota_rows = []
        quota_ids: dict[str, uuid.UUID] = {}
        for raw in quota_raw:
            source_key = raw["quota_uid"]
            row_id = stable_uuid("reference_quota_item", source_key)
            quota_ids[source_key] = row_id
            price = quota_price[source_key]
            quota_rows.append({
                "reference_quota_item_id": row_id, "reference_release_id": REFERENCE_RELEASE_ID,
                "source_document_id": source_ids[raw["source_document_id"]], "source_key": source_key,
                "quota_uid": source_key, "volume_code": raw["volume_code"], "source_code": raw["source_code"],
                "quota_name": raw["raw_name"], "specification": raw["specification"] or None,
                "unit": raw["unit_normalized"] or raw["unit_raw"] or None, "chapter_code": raw["chapter_code"] or None,
                "section_code": raw["section_code"] or None, "pdf_page_no": as_int(raw["pdf_page_no"]),
                "labor_fee": as_decimal(price["labor_fee"]), "material_fee": as_decimal(price["material_fee"]),
                "machine_fee": as_decimal(price["machine_fee"]), "management_fee": as_decimal(price["management_fee"]),
                "total_fee": as_decimal(price["total_fee"]), "source_role": "authority_source",
                "review_status": "pending", "parse_confidence": as_float(raw["parse_confidence"]),
                "payload_sha256": payload_sha256({"quota": raw, "price": price}), "created_by": user_id,
            })
            items.append(_job_item(job_id, "quota_item", source_key, "reference_quota_item", row_id, raw))
        _insert_many(connection, ReferenceQuotaItem, quota_rows)

        resource_raw = read_csv(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_resource_components.csv")
        resource_rows = []
        for raw in resource_raw:
            source_key = raw["resource_component_id"]
            row_id = stable_uuid("reference_quota_resource", source_key)
            resource_rows.append({
                "reference_quota_resource_id": row_id, "reference_release_id": REFERENCE_RELEASE_ID,
                "reference_quota_item_id": quota_ids[raw["quota_uid"]],
                "source_document_id": source_ids[raw["source_document_id"]], "source_key": source_key,
                "resource_category": raw["resource_category"], "resource_code": raw["resource_code"] or None,
                "resource_name": raw["resource_name"], "specification": raw["specification"] or None,
                "unit": raw["unit"] or None, "consumption": as_decimal(raw["consumption"]),
                "unit_price": as_decimal(raw["unit_price"]), "component_amount": as_decimal(raw["component_amount"]),
                "source_page_no": as_int(raw["source_page_no"]), "source_row_order": as_int(raw["source_row_order"]),
                "review_status": "pending", "payload_sha256": payload_sha256(raw), "created_by": user_id,
            })
            items.append(_job_item(job_id, "resource_component", source_key, "reference_quota_resource", row_id, raw))
        _insert_many(connection, ReferenceQuotaResource, resource_rows)

        evidence_rows = []
        page_raw = read_csv(runs / "GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/gd_building_source_pages.csv")
        for raw in page_raw:
            source_key = f"{raw['source_document_id']}:{raw['pdf_page_no']}"
            row_id = stable_uuid("source_page_evidence", source_key)
            evidence_rows.append({
                "source_page_evidence_id": row_id, "source_document_id": source_ids[raw["source_document_id"]],
                "source_key": source_key, "page_no": as_int(raw["pdf_page_no"]),
                "printed_page_no": raw["printed_page_no"] or None, "evidence_type": "source_page",
                "source_locator": f"pdf_page:{raw['pdf_page_no']}", "evidence_status": raw["parse_status"],
                "evidence_payload": raw, "payload_sha256": payload_sha256(raw), "created_by": user_id,
            })
            items.append(_job_item(job_id, "source_page", source_key, "source_page_evidence", row_id, raw))
        samples = {row["bill_reference_id"]: row for row in read_csv(runs / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1/gb50854_authority_sample_review.csv")}
        backlog_raw = read_csv(runs / "GB50854_DUAL_SOURCE_EVIDENCE_LOCK_1/gb50854_evidence_link_backlog.csv")
        for raw in backlog_raw:
            sample = samples.get(raw["bill_reference_id"], {})
            page_no = as_int(sample.get("authority_pdf_page_no") or raw["authority_pdf_page_no"])
            source_key = raw["backlog_id"]
            row_id = stable_uuid("source_page_evidence", source_key)
            evidence_rows.append({
                "source_page_evidence_id": row_id, "source_document_id": authority_pdf_id,
                "source_key": source_key, "page_no": page_no, "evidence_type": "bill_authority_evidence",
                "source_locator": raw["source_heading_path"],
                "evidence_status": sample.get("authority_verification_status") or raw["authority_verification_status"],
                "evidence_payload": {"backlog": raw, "sample": sample or None},
                "payload_sha256": payload_sha256({"backlog": raw, "sample": sample or None}), "created_by": user_id,
            })
            items.append(_job_item(job_id, "authority_evidence", source_key, "source_page_evidence", row_id, raw))
        _insert_many(connection, SourcePageEvidence, evidence_rows)

        rule_rows: list[dict[str, Any]] = []
        rule_ids: dict[str, uuid.UUID] = {}
        def add_rule(raw: dict[str, str], source_key: str, rule_type: str, source_doc_key: str,
                     text: str, locator: str, code: str | None = None, title: str | None = None,
                     page_no: int | None = None) -> None:
            row_id = stable_uuid("reference_rule_block", source_key)
            rule_ids[source_key] = row_id
            rule_rows.append({
                "reference_rule_block_id": row_id, "reference_release_id": REFERENCE_RELEASE_ID,
                "source_document_id": source_ids[source_doc_key], "source_key": source_key,
                "rule_type": rule_type, "rule_code": code, "rule_title": title, "rule_text": text,
                "pdf_page_no": page_no, "source_locator": locator, "review_status": "pending",
                "payload_sha256": payload_sha256(raw), "created_by": user_id,
            })
            items.append(_job_item(job_id, "rule_block", source_key, "reference_rule_block", row_id, raw))

        for raw in read_csv(runs / "GB50854_2024_stageB_docx_full/bill_context_rules_all.csv"):
            add_rule(raw, raw["rule_id"], "bill_context", "GB50854_EXTRACTION_PROXY_DOCX_2024",
                     raw["rule_text"], raw["source_heading_path"], raw["rule_code"] or None)
        gd_rule_specs = [
            ("gd_building_work_content_blocks.csv", "work_content", "work_content_block_id", "content_text", "section_code", "", ""),
            ("gd_building_quantity_rule_blocks.csv", "quantity_rule", "quantity_rule_block_id", "rule_text", "table_reference", "rule_number", "rule_title"),
            ("gd_building_conversion_rules.csv", "conversion", "conversion_rule_id", "source_text_raw", "section_code", "", "conversion_condition"),
            ("gd_building_note_clauses.csv", "note", "note_clause_id", "clause_text", "section_code", "", "clause_type"),
        ]
        for filename, rule_type, id_field, text_field, locator_field, code_field, title_field in gd_rule_specs:
            for raw in read_csv(runs / f"GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/{filename}"):
                add_rule(raw, raw[id_field], rule_type, raw["source_document_id"], raw[text_field],
                         raw.get(locator_field, "") or f"pdf_page:{raw['pdf_page_no']}",
                         raw.get(code_field) or None if code_field else None,
                         raw.get(title_field) or None if title_field else None, as_int(raw["pdf_page_no"]))
        _insert_many(connection, ReferenceRuleBlock, rule_rows)

        scope_rows = []
        for filename, block_field in (
            ("gd_building_work_content_scope_links.csv", "work_content_block_id"),
            ("gd_building_quantity_rule_scope_links.csv", "quantity_rule_block_id"),
        ):
            for raw in read_csv(runs / f"GD2018_BUILDING_A01_A03_CONSOLIDATED_BASELINE_1/{filename}"):
                source_key = raw["scope_link_id"]
                row_id = stable_uuid("reference_scope_link", source_key)
                scope_rows.append({
                    "reference_scope_link_id": row_id, "reference_release_id": REFERENCE_RELEASE_ID,
                    "reference_rule_block_id": rule_ids[raw[block_field]],
                    "reference_quota_item_id": quota_ids.get(raw["quota_uid"]), "source_key": source_key,
                    "scope_type": raw["scope_type"], "scope_start_code": raw["scope_start_code"] or None,
                    "scope_end_code": raw["scope_end_code"] or None,
                    "scope_confidence": as_float(raw["scope_confidence"]), "scope_status": raw["scope_status"],
                    "review_status": "pending", "payload_sha256": payload_sha256(raw), "created_by": user_id,
                })
                items.append(_job_item(job_id, "scope_link", source_key, "reference_scope_link", row_id, raw))
        _insert_many(connection, ReferenceScopeLink, scope_rows)

        connection.execute(pg_insert(MappingRelease).values(
            mapping_release_id=MAPPING_RELEASE_ID, reference_release_id=REFERENCE_RELEASE_ID,
            semantic_version="RC1", release_status="published",
            mapping_hash_manifest=group_hash["mapping_reference_hash_manifest"],
            generator_version=first_manifest["parser_version"], created_by=user_id,
        ).on_conflict_do_nothing())
        edge_rows = []
        edge_raw = read_csv(runs / "MAP_GB50854_TO_GD2018_BUILDING_A_FULL_1/building_bill_to_quota_edges.csv")
        for raw in edge_raw:
            source_key = raw["mapping_edge_id"]
            row_id = stable_uuid("mapping_candidate_edge", source_key)
            edge_rows.append({
                "mapping_candidate_edge_id": row_id, "mapping_release_id": MAPPING_RELEASE_ID,
                "reference_release_id": REFERENCE_RELEASE_ID,
                "reference_bill_item_id": bill_ids[raw["bill_reference_id"]],
                "reference_quota_item_id": quota_ids[raw["quota_uid"]], "source_key": source_key,
                "mapping_role": raw["mapping_role"], "routing_class": raw["routing_class"],
                "semantic_score": as_float(raw["semantic_score"]),
                "source_evidence_status": raw["source_evidence_status"], "risk_level": raw["risk_level"],
                "risk_reason": raw["risk_reason"] or None, "ai_mapping_explanation": raw["ai_mapping_explanation"] or None,
                "candidate_rank": int(raw["candidate_rank"]), "review_status": "pending",
                "payload_sha256": payload_sha256(raw), "created_by": user_id,
            })
            items.append(_job_item(job_id, "mapping_edge", source_key, "mapping_candidate_edge", row_id, raw))
        _insert_many(connection, MappingCandidateEdge, edge_rows)

        _insert_many(connection, PlatformImportJobItem, items)
        connection.execute(update(PlatformImportJob).where(PlatformImportJob.import_job_id == job_id).values(
            status="completed", completed_at=datetime.now(timezone.utc), record_count=len(items),
            success_count=len(items), failure_count=0, updated_by=user_id,
        ))
        return Rc1ImportResult(
            import_job_id=job_id, duplicate_run=False, entity_counts=_entity_counts(connection),
            imported_item_count=len(items), approved_count=_approved_count(connection), manifest_sha256=manifest_sha,
        )


def _entity_counts(connection: Connection) -> dict[str, int]:
    tables = {
        "source_document": SourceDocument, "source_page_evidence": SourcePageEvidence,
        "reference_bill_item": ReferenceBillItem, "reference_quota_item": ReferenceQuotaItem,
        "reference_quota_resource": ReferenceQuotaResource, "reference_rule_block": ReferenceRuleBlock,
        "reference_scope_link": ReferenceScopeLink, "mapping_candidate_edge": MappingCandidateEdge,
        "release_artifact": ReleaseArtifact, "platform_import_job_item": PlatformImportJobItem,
    }
    return {name: _count(connection, table) for name, table in tables.items()}


def _approved_count(connection: Connection) -> int:
    total = 0
    for table in (ReferenceBillItem, ReferenceQuotaItem, ReferenceQuotaResource, ReferenceRuleBlock,
                  ReferenceScopeLink, MappingCandidateEdge):
        total += int(connection.scalar(
            select(func.count()).select_from(table).where(cast(table.review_status, String) == "approved")
        ) or 0)
    return total
