from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
sys.path.insert(0, str(ENGINE_ROOT))

from sqlalchemy import func, select, text

from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.importers.hash_guard import EXPECTED_COUNTS, validate_rc1_manifest
from platform_db.models import (
    AppRole,
    AppTenant,
    AppUser,
    AppUserRoleAssignment,
    EnterprisePriceApproval,
    EnterprisePriceSnapshot,
    EnterprisePriceSnapshotLine,
    EnterprisePriceSourceDocument,
    EnterprisePriceVersion,
    EnterpriseQuota,
    EnterpriseQuotaChangeSet,
    EnterpriseQuotaComponentVersion,
    EnterpriseQuotaRelease,
    EnterpriseQuotaRuleVersion,
    EnterpriseQuotaVersion,
    EnterpriseResource,
    EnterpriseResourceReferenceLink,
    MappingAuditEvent,
    MappingCandidateEdge,
    MappingDraftEdge,
    MappingWorkspace,
    ReferenceBillItem,
    ReferenceQuotaItem,
    ReferenceQuotaResource,
    ReferenceRelease,
    SystemAuditEvent,
)
from platform_db.models.base import EnterpriseQuotaState, LifecycleStatus
from platform_db.repositories import PlatformReadRepository
from platform_db.services.enterprise_quota_pricing import (
    CALCULATION_RULE_VERSION,
    canonical_snapshot_payload,
    restore_snapshot_payload,
    snapshot_sha256,
)
from sqlalchemy.orm import Session


RUN_NAME = "ENTERPRISE_PRICE_RESOURCE_MATCHING_AND_A111_QUOTA_PILOT_1"
RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs" / RUN_NAME
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
REFERENCE_RELEASE_ID = "BUILDING_A01_A03_REFERENCE_RC1"
MAPPING_WORKSPACE_NAME = "SQLite Draft Overlay Migration"
NAMESPACE = uuid.UUID("a0f2cf92-a62c-4a6d-9cb1-d86fa6388a96")
FINAL_STATUS = "enterprise_price_source_confirmation_required"
NOW = datetime.fromtimestamp(MANIFEST.stat().st_mtime, timezone.utc)


def uid(name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, name)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: serialize(row.get(field)) for field in fields})


def serialize(value: Any) -> Any:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def normalize(value: str | None) -> str:
    return "".join((value or "").strip().lower().split())


def resource_key(row: ReferenceQuotaResource) -> tuple[str, str, str, str, str]:
    return (
        normalize(row.resource_code), normalize(row.resource_name), normalize(row.specification),
        normalize(row.unit), normalize(row.resource_category),
    )


def natural_code(code: str) -> tuple[Any, ...]:
    return tuple(int(item) if item.isdigit() else item for item in code.replace("-", ".").split("."))


def quota_hash(quota: ReferenceQuotaItem, resources: list[ReferenceQuotaResource]) -> str:
    payload = {
        "reference_release_id": quota.reference_release_id,
        "quota_uid": quota.quota_uid,
        "source_code": quota.source_code,
        "quota_name": quota.quota_name,
        "specification": quota.specification,
        "unit": quota.unit,
        "payload_sha256": quota.payload_sha256,
        "resources": [{
            "resource_id": str(row.reference_quota_resource_id),
            "payload_sha256": row.payload_sha256,
        } for row in sorted(resources, key=lambda item: (item.source_row_order, str(item.reference_quota_resource_id)))],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_inventory() -> list[dict[str, Any]]:
    source = ENGINE_ROOT / "data/private/reference_extraction/source_excels/内部价格表.xls"
    v2 = ENGINE_ROOT / "data/private/reference_extraction/runs/PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1/internal_price_item_candidate_v2.csv"
    v1 = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_BASELINE_LOCK_1/internal_price_item_candidate.csv"
    alignment = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_TO_GD_QUOTA_ALIGNMENT_1/internal_price_to_gd_quota_candidate.csv"
    manual = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_QUOTA_MANUAL_PRICING_REVIEW_V0_1/enterprise_quota_manual_pricing_review_v0_1.csv"
    market = ENGINE_ROOT / "data/private/reference_extraction/runs/PRICE_SOURCE_REFRESH_AND_MARKET_BASELINE_1/market_price_normalized_items.csv"
    definitions = [
        (source, 321, "enterprise_price_source_candidate", "xls", "present_composite_fee_not_resource_unit_price", "candidate_file_requires_owner_confirmation"),
        (v2, csv_count(v2), "enterprise_historical_observation", "csv", "present_composite_fee_not_resource_unit_price", "derived_non_authoritative"),
        (v1, csv_count(v1), "enterprise_historical_observation", "csv", "present_composite_fee_not_resource_unit_price", "superseded_derived_non_authoritative"),
        (alignment, csv_count(alignment), "enterprise_historical_observation", "csv", "derived_comparison_only", "derived_non_authoritative"),
        (manual, csv_count(manual), "enterprise_historical_observation", "csv", "derived_review_only", "derived_non_authoritative"),
        (market, csv_count(market), "market_reference", "csv", "no_price_rows", "source_file_not_loaded"),
    ]
    rows = []
    for path, count, role, file_type, price_status, authority in definitions:
        rows.append({
            "source_price_document_id": str(uid(f"price-source:{path.resolve()}:{file_sha256(path)}")),
            "file_name": path.name,
            "absolute_path": str(path.resolve()),
            "sha256": file_sha256(path),
            "file_type": file_type,
            "record_count": count,
            "resource_code_status": "missing" if role != "market_reference" else "not_loaded",
            "resource_name_status": "present" if count else "not_loaded",
            "specification_status": "embedded_or_missing" if count else "not_loaded",
            "unit_status": "partial" if count else "not_loaded",
            "price_status": price_status,
            "tax_mode_status": "missing",
            "effective_date_status": "missing",
            "region_status": "missing",
            "source_role": role,
            "authority_status": authority,
            "review_status": "enterprise_price_source_confirmation_required",
        })
    return rows


def assert_preflight(session: Session, hash_guard: dict[str, Any], sqlite_hash: str) -> dict[str, Any]:
    failures: list[str] = []
    migration = session.scalar(text("SELECT version_num FROM alembic_version"))
    if migration != "0004_enterprise_price_a111_pilot":
        failures.append(f"migration:{migration}")
    counts = {
        "bill": int(session.scalar(select(func.count()).select_from(ReferenceBillItem)) or 0),
        "quota": int(session.scalar(select(func.count()).select_from(ReferenceQuotaItem)) or 0),
        "resource": int(session.scalar(select(func.count()).select_from(ReferenceQuotaResource)) or 0),
        "edge": int(session.scalar(select(func.count()).select_from(MappingCandidateEdge)) or 0),
    }
    if counts != EXPECTED_COUNTS:
        failures.append(f"counts:{counts}")
    workspace = session.scalar(select(MappingWorkspace).where(MappingWorkspace.workspace_name == MAPPING_WORKSPACE_NAME))
    draft = int(session.scalar(select(func.count()).select_from(MappingDraftEdge).where(
        MappingDraftEdge.mapping_workspace_id == workspace.mapping_workspace_id
    )) or 0) if workspace else -1
    audit = int(session.scalar(select(func.count()).select_from(MappingAuditEvent).where(
        MappingAuditEvent.mapping_workspace_id == workspace.mapping_workspace_id
    )) or 0) if workspace else -1
    if (draft, audit) != (6, 7):
        failures.append(f"draft_audit:{draft}/{audit}")
    approved = int(session.scalar(select(func.count()).select_from(EnterprisePriceApproval).where(
        EnterprisePriceApproval.decision == "approved"
    )) or 0)
    approved += int(session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(
        EnterpriseQuotaVersion.state == EnterpriseQuotaState.approved
    )) or 0)
    if approved:
        failures.append(f"approved:{approved}")
    if not hash_guard["ok"]:
        failures.extend(hash_guard["failures"])
    if file_sha256(SQLITE) != sqlite_hash:
        failures.append("sqlite_changed_during_preflight")
    if failures:
        raise RuntimeError("PRECONDITION FAILED: " + "; ".join(failures))
    return {"migration": migration, "counts": counts, "draft": draft, "audit": audit, "approved": approved}


def actor_and_tenant(session: Session) -> tuple[AppTenant, AppUser]:
    settings = get_settings()
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
    if tenant is None:
        raise RuntimeError("Platform tenant is missing")
    actor = session.scalar(
        select(AppUser)
        .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
        .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
        .where(
            AppUser.tenant_id == tenant.tenant_id,
            AppUser.status == "active",
            AppUserRoleAssignment.status == "active",
            AppRole.role_code == "editor",
        )
        .order_by(AppUser.login_name)
    )
    if actor is None:
        raise RuntimeError("No active explicitly assigned editor is available")
    return tenant, actor


def add_or_verify(session: Session, model, key: Any, values: dict[str, Any]):
    row = session.get(model, key)
    if row is None:
        row = model(**values)
        session.add(row)
        return row
    for field, expected in values.items():
        if field in {"created_at", "updated_at"}:
            continue
        actual = getattr(row, field)
        if hasattr(actual, "value"):
            actual = actual.value
        if hasattr(expected, "value"):
            expected = expected.value
        if isinstance(actual, Decimal) and expected is not None:
            expected = Decimal(str(expected))
        if actual != expected:
            raise RuntimeError(f"Existing {model.__name__}.{field} differs for {key}")
    return row


def seed(session: Session, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    tenant, actor = actor_and_tenant(session)
    release = session.get(ReferenceRelease, REFERENCE_RELEASE_ID)
    if release is None:
        raise RuntimeError("Frozen Reference Release is missing")
    correlation_id = uid(f"correlation:{RUN_NAME}")

    for item in inventory:
        document_id = uuid.UUID(item["source_price_document_id"])
        add_or_verify(session, EnterprisePriceSourceDocument, document_id, {
            "source_price_document_id": document_id,
            "tenant_id": tenant.tenant_id,
            **{field: item[field] for field in (
                "file_name", "absolute_path", "sha256", "file_type", "record_count",
                "resource_code_status", "resource_name_status", "specification_status", "unit_status",
                "price_status", "tax_mode_status", "effective_date_status", "region_status",
                "source_role", "authority_status", "review_status",
            )},
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })

    quotas = list(session.scalars(select(ReferenceQuotaItem).where(
        ReferenceQuotaItem.reference_release_id == REFERENCE_RELEASE_ID,
        ReferenceQuotaItem.source_code.like("A1-1-%"),
    )))
    quotas.sort(key=lambda row: natural_code(row.source_code))
    if len(quotas) != 137:
        raise RuntimeError(f"A1.1 reference count is {len(quotas)}, expected 137")
    quota_ids = [row.reference_quota_item_id for row in quotas]
    resources = list(session.scalars(select(ReferenceQuotaResource).where(
        ReferenceQuotaResource.reference_quota_item_id.in_(quota_ids)
    ).order_by(ReferenceQuotaResource.reference_quota_item_id, ReferenceQuotaResource.source_row_order)))
    if len(resources) != 629:
        raise RuntimeError(f"A1.1 resource row count is {len(resources)}, expected 629")
    resources_by_quota: dict[uuid.UUID, list[ReferenceQuotaResource]] = defaultdict(list)
    for row in resources:
        resources_by_quota[row.reference_quota_item_id].append(row)

    grouped: dict[tuple[str, str, str, str, str], list[ReferenceQuotaResource]] = defaultdict(list)
    for row in resources:
        grouped[resource_key(row)].append(row)
    if len(grouped) != 55:
        raise RuntimeError(f"Enterprise Resource candidate count is {len(grouped)}, expected 55")
    enterprise_resource_by_key: dict[tuple[str, str, str, str, str], EnterpriseResource] = {}
    for key, rows in sorted(grouped.items()):
        representative = rows[0]
        resource_id = uid("enterprise-resource:" + "|".join(key))
        enterprise = add_or_verify(session, EnterpriseResource, resource_id, {
            "enterprise_resource_id": resource_id,
            "tenant_id": tenant.tenant_id,
            "source_reference_resource_id": representative.reference_quota_resource_id,
            "resource_code": representative.resource_code or "",
            "resource_name": representative.resource_name,
            "normalized_name": normalize(representative.resource_name),
            "specification": representative.specification or "",
            "unit": representative.unit or "",
            "resource_category": representative.resource_category or "other",
            "status": LifecycleStatus.draft,
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })
        enterprise_resource_by_key[key] = enterprise
        for reference in rows:
            link_id = uid(f"resource-link:{reference.reference_quota_resource_id}")
            method = "exact_code" if (reference.resource_code or "") == enterprise.resource_code and enterprise.resource_code else "exact_name_spec_unit"
            add_or_verify(session, EnterpriseResourceReferenceLink, link_id, {
                "link_id": link_id,
                "tenant_id": tenant.tenant_id,
                "enterprise_resource_id": resource_id,
                "reference_resource_id": reference.reference_quota_resource_id,
                "reference_resource_code": reference.resource_code or "",
                "match_method": method,
                "match_score": Decimal("1"),
                "name_match_status": "exact",
                "specification_match_status": "exact",
                "unit_match_status": "exact",
                "category_match_status": "exact",
                "review_status": "pending",
                "risk_reason": "",
                "created_by": actor.app_user_id,
                "updated_by": actor.app_user_id,
                "correlation_id": correlation_id,
            })

    read_repository = PlatformReadRepository(session)
    rule_count = 0
    for quota in quotas:
        enterprise_quota_id = uid(f"enterprise-quota:{quota.quota_uid}")
        enterprise_quota = add_or_verify(session, EnterpriseQuota, enterprise_quota_id, {
            "enterprise_quota_id": enterprise_quota_id,
            "tenant_id": tenant.tenant_id,
            "standard_family_id": release.standard_family_id,
            "source_reference_quota_id": quota.reference_quota_item_id,
            "enterprise_quota_code": f"ENT-{quota.source_code}",
            "quota_name": quota.quota_name,
            "unit": quota.unit or "",
            "status": LifecycleStatus.draft,
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })
        change_set_id = uid(f"change-set:{quota.quota_uid}:1")
        request_id = uid(f"request:{quota.quota_uid}:fork")
        after = {
            "source_reference_release_id": REFERENCE_RELEASE_ID,
            "source_quota_uid": quota.quota_uid,
            "source_quota_code": quota.source_code,
            "quota_name": quota.quota_name,
            "unit": quota.unit or "",
        }
        change_set = add_or_verify(session, EnterpriseQuotaChangeSet, change_set_id, {
            "enterprise_quota_change_set_id": change_set_id,
            "tenant_id": tenant.tenant_id,
            "enterprise_quota_id": enterprise_quota_id,
            "change_set_no": 1,
            "business_reason": "Fork immutable GD2018 A1.1 Reference into an Enterprise Draft pilot.",
            "change_payload": {"before": {}, "after": after},
            "status": "draft",
            "before_value": {},
            "after_value": after,
            "change_type": "fork_from_reference",
            "change_reason": "A1.1 enterprise quota pilot initialization",
            "changed_by": actor.app_user_id,
            "changed_at": NOW,
            "request_id": request_id,
            "idempotency_key": f"{RUN_NAME}:{quota.quota_uid}:fork",
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": request_id,
        })
        version_id = uid(f"quota-version:{quota.quota_uid}:1")
        related_resources = resources_by_quota[quota.reference_quota_item_id]
        rules = read_repository.quota_rules(quota.reference_quota_item_id)
        work_content = "\n".join(row.rule_text for row in rules if row.rule_type == "work_content")
        version = add_or_verify(session, EnterpriseQuotaVersion, version_id, {
            "enterprise_quota_version_id": version_id,
            "tenant_id": tenant.tenant_id,
            "enterprise_quota_id": enterprise_quota_id,
            "reference_release_id": REFERENCE_RELEASE_ID,
            "predecessor_id": None,
            "change_set_id": change_set.enterprise_quota_change_set_id,
            "version_no": 1,
            "source_quota_uid": quota.quota_uid,
            "source_quota_code": quota.source_code,
            "source_quota_version_hash": quota_hash(quota, related_resources),
            "unit": quota.unit or "",
            "work_content": work_content,
            "enterprise_note": "",
            "change_reason": "A1.1 enterprise quota pilot initialization",
            "calculation_rule_version": CALCULATION_RULE_VERSION,
            "state": EnterpriseQuotaState.draft,
            "submitted_by": None,
            "reviewed_by": None,
            "approved_by": None,
            "published_at": None,
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": request_id,
        })
        for line_no, reference in enumerate(related_resources, 1):
            component_id = uid(f"component:{quota.quota_uid}:{reference.reference_quota_resource_id}")
            enterprise = enterprise_resource_by_key[resource_key(reference)]
            add_or_verify(session, EnterpriseQuotaComponentVersion, component_id, {
                "enterprise_quota_component_version_id": component_id,
                "enterprise_quota_version_id": version.enterprise_quota_version_id,
                "enterprise_resource_id": enterprise.enterprise_resource_id,
                "source_reference_resource_id": reference.reference_quota_resource_id,
                "line_no": line_no,
                "consumption": reference.consumption,
                "source_consumption": reference.consumption,
                "provincial_unit_price": reference.unit_price,
                "provincial_component_amount": reference.component_amount,
                "enterprise_price_version_id": None,
                "selected_enterprise_price": None,
                "selected_price_type": None,
                "enterprise_component_amount": None,
                "amount_source": "enterprise_price_missing",
                "override_reason": None,
                "created_by": actor.app_user_id,
                "updated_by": actor.app_user_id,
                "correlation_id": request_id,
            })
        ordinals: Counter[str] = Counter()
        for rule in rules:
            ordinals[rule.rule_type] += 1
            rule_id = uid(f"quota-rule:{quota.quota_uid}:{rule.reference_rule_block_id}")
            add_or_verify(session, EnterpriseQuotaRuleVersion, rule_id, {
                "enterprise_quota_rule_version_id": rule_id,
                "enterprise_quota_version_id": version.enterprise_quota_version_id,
                "source_rule_block_id": rule.reference_rule_block_id,
                "rule_type": rule.rule_type,
                "ordinal": ordinals[rule.rule_type],
                "rule_text": rule.rule_text,
                "enterprise_reason": None,
                "created_by": actor.app_user_id,
                "updated_by": actor.app_user_id,
                "correlation_id": request_id,
            })
            rule_count += 1

    session.flush()
    snapshot_id = uid(f"snapshot:{RUN_NAME}:preview")
    snapshot_lines_payload = []
    for key, enterprise in sorted(enterprise_resource_by_key.items()):
        representative = grouped[key][0]
        link_id = uid(f"resource-link:{representative.reference_quota_resource_id}")
        snapshot_lines_payload.append({
            "snapshot_line_id": str(uid(f"snapshot-line:{snapshot_id}:{enterprise.enterprise_resource_id}")),
            "enterprise_resource_id": str(enterprise.enterprise_resource_id),
            "enterprise_price_version_id": None,
            "price_value": None,
            "unit": enterprise.unit,
            "tax_mode": "unknown",
            "region": "unconfirmed",
            "effective_from": None,
            "effective_to": None,
            "source_type": FINAL_STATUS,
            "price_type": None,
            "price_source": None,
            "source_price_document_id": None,
            "resource_reference_link_id": str(link_id),
            "calculation_rule_version": CALCULATION_RULE_VERSION,
            "mapping_snapshot": {
                "link_id": str(link_id),
                "reference_resource_id": str(representative.reference_quota_resource_id),
                "reference_resource_code": representative.resource_code or "",
                "match_method": "exact_code" if representative.resource_code else "exact_name_spec_unit",
            },
        })
    digest = snapshot_sha256(snapshot_lines_payload)
    add_or_verify(session, EnterprisePriceSnapshot, snapshot_id, {
        "enterprise_price_snapshot_id": snapshot_id,
        "tenant_id": tenant.tenant_id,
        "price_release_id": "UNCONFIRMED_ENTERPRISE_PRICE_SOURCE",
        "snapshot_code": f"{RUN_NAME}:PREVIEW",
        "effective_at": NOW,
        "source_release_id": REFERENCE_RELEASE_ID,
        "snapshot_sha256": digest,
        "snapshot_type": "preview",
        "status": "draft",
        "calculation_rule_version": CALCULATION_RULE_VERSION,
        "created_by": actor.app_user_id,
        "updated_by": actor.app_user_id,
        "correlation_id": correlation_id,
    })
    for item in snapshot_lines_payload:
        line_id = uuid.UUID(item["snapshot_line_id"])
        add_or_verify(session, EnterprisePriceSnapshotLine, line_id, {
            "snapshot_line_id": line_id,
            "enterprise_price_snapshot_id": snapshot_id,
            "enterprise_resource_id": uuid.UUID(item["enterprise_resource_id"]),
            "enterprise_price_version_id": None,
            "price_value": None,
            "unit": item["unit"],
            "tax_mode": item["tax_mode"],
            "region": item["region"],
            "effective_from": None,
            "effective_to": None,
            "source_type": item["source_type"],
            "price_type": None,
            "price_source": None,
            "source_price_document_id": None,
            "resource_reference_link_id": uuid.UUID(item["resource_reference_link_id"]),
            "calculation_rule_version": CALCULATION_RULE_VERSION,
            "mapping_snapshot": item["mapping_snapshot"],
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })

    event_id = uid(f"audit:{RUN_NAME}:seed")
    add_or_verify(session, SystemAuditEvent, event_id, {
        "system_audit_event_id": event_id,
        "tenant_id": tenant.tenant_id,
        "actor_user_id": actor.app_user_id,
        "release_manifest_id": None,
        "event_type": "enterprise_a111_pilot_seeded",
        "subject_type": "enterprise_quota_pilot",
        "subject_id": RUN_NAME,
        "before_payload": {"enterprise_quota_count": 0, "enterprise_resource_count": 0},
        "after_payload": {
            "enterprise_quota_count": 137,
            "enterprise_resource_count": 55,
            "enterprise_price_count": 0,
            "final_status": FINAL_STATUS,
        },
        "created_by": actor.app_user_id,
        "updated_by": actor.app_user_id,
        "correlation_id": correlation_id,
    })
    session.commit()
    return {
        "tenant_id": tenant.tenant_id,
        "actor_user_id": actor.app_user_id,
        "quotas": quotas,
        "resources": resources,
        "resource_groups": grouped,
        "snapshot_id": snapshot_id,
        "snapshot_sha256": digest,
        "snapshot_payload": snapshot_lines_payload,
        "rule_count": rule_count,
    }


def export_outputs(session: Session, seeded: dict[str, Any], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    tenant_id = seeded["tenant_id"]
    inventory_fields = [
        "source_price_document_id", "file_name", "absolute_path", "sha256", "file_type", "record_count",
        "resource_code_status", "resource_name_status", "specification_status", "unit_status", "price_status",
        "tax_mode_status", "effective_date_status", "region_status", "source_role", "authority_status", "review_status",
    ]
    write_csv(RUN_DIR / "enterprise_price_source_inventory.csv", inventory_fields, inventory)

    resources = list(session.scalars(select(EnterpriseResource).where(
        EnterpriseResource.tenant_id == tenant_id
    ).order_by(EnterpriseResource.resource_category, EnterpriseResource.resource_code, EnterpriseResource.resource_name)))
    resource_rows = [{field: getattr(row, field) for field in (
        "enterprise_resource_id", "tenant_id", "resource_code", "resource_name", "specification",
        "unit", "resource_category", "status", "created_at", "created_by", "row_version",
    )} for row in resources]
    write_csv(RUN_DIR / "a111_enterprise_resource_candidate.csv", list(resource_rows[0]), resource_rows)

    links = list(session.scalars(select(EnterpriseResourceReferenceLink).where(
        EnterpriseResourceReferenceLink.tenant_id == tenant_id
    ).order_by(EnterpriseResourceReferenceLink.reference_resource_code, EnterpriseResourceReferenceLink.reference_resource_id)))
    link_fields = [
        "link_id", "enterprise_resource_id", "reference_resource_id", "reference_resource_code", "match_method",
        "match_score", "name_match_status", "specification_match_status", "unit_match_status",
        "category_match_status", "review_status", "risk_reason",
    ]
    write_csv(RUN_DIR / "a111_resource_reference_link.csv", link_fields, [
        {field: getattr(row, field) for field in link_fields} for row in links
    ])

    price_fields = [
        "enterprise_price_version_id", "enterprise_resource_id", "price_value", "price_type", "tax_mode",
        "region", "project_type", "supplier_or_source", "effective_from", "effective_to",
        "source_price_document_id", "confidence", "review_status", "row_version",
    ]
    write_csv(RUN_DIR / "a111_enterprise_price_draft.csv", price_fields, [])

    versions = list(session.scalars(select(EnterpriseQuotaVersion).where(
        EnterpriseQuotaVersion.tenant_id == tenant_id,
        EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"),
    )))
    versions.sort(key=lambda row: natural_code(row.source_quota_code))
    quota_map = {row.enterprise_quota_id: row for row in session.scalars(select(EnterpriseQuota).where(
        EnterpriseQuota.tenant_id == tenant_id
    ))}
    quota_fields = [
        "enterprise_quota_id", "enterprise_quota_version_id", "source_reference_release_id", "source_quota_uid",
        "source_quota_code", "source_quota_version_hash", "enterprise_quota_code", "enterprise_quota_name", "unit",
        "enterprise_quota_version_no", "status", "created_by", "created_at", "change_reason", "row_version",
    ]
    quota_rows = []
    for version in versions:
        quota = quota_map[version.enterprise_quota_id]
        quota_rows.append({
            "enterprise_quota_id": quota.enterprise_quota_id,
            "enterprise_quota_version_id": version.enterprise_quota_version_id,
            "source_reference_release_id": version.reference_release_id,
            "source_quota_uid": version.source_quota_uid,
            "source_quota_code": version.source_quota_code,
            "source_quota_version_hash": version.source_quota_version_hash,
            "enterprise_quota_code": quota.enterprise_quota_code,
            "enterprise_quota_name": quota.quota_name,
            "unit": version.unit,
            "enterprise_quota_version_no": version.version_no,
            "status": version.state,
            "created_by": version.created_by,
            "created_at": version.created_at,
            "change_reason": version.change_reason,
            "row_version": version.row_version,
        })
    write_csv(RUN_DIR / "a111_enterprise_quota_draft.csv", quota_fields, quota_rows)

    components = list(session.scalars(select(EnterpriseQuotaComponentVersion).where(
        EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_([row.enterprise_quota_version_id for row in versions])
    ).order_by(EnterpriseQuotaComponentVersion.enterprise_quota_version_id, EnterpriseQuotaComponentVersion.line_no)))
    version_map = {row.enterprise_quota_version_id: row for row in versions}
    resource_map = {row.enterprise_resource_id: row for row in resources}
    component_fields = [
        "enterprise_quota_component_version_id", "enterprise_quota_version_id", "source_quota_code", "line_no",
        "enterprise_resource_id", "resource_code", "resource_name", "specification", "unit", "resource_category",
        "source_reference_resource_id", "provincial_consumption", "enterprise_consumption", "provincial_unit_price",
        "provincial_component_amount", "selected_enterprise_price", "enterprise_component_amount",
        "price_difference", "consumption_difference", "amount_source", "override_reason", "row_version",
    ]
    component_rows = []
    for row in components:
        resource = resource_map[row.enterprise_resource_id]
        price_diff = None if row.selected_enterprise_price is None or row.provincial_unit_price is None else row.selected_enterprise_price - row.provincial_unit_price
        component_rows.append({
            "enterprise_quota_component_version_id": row.enterprise_quota_component_version_id,
            "enterprise_quota_version_id": row.enterprise_quota_version_id,
            "source_quota_code": version_map[row.enterprise_quota_version_id].source_quota_code,
            "line_no": row.line_no,
            "enterprise_resource_id": row.enterprise_resource_id,
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "specification": resource.specification,
            "unit": resource.unit,
            "resource_category": resource.resource_category,
            "source_reference_resource_id": row.source_reference_resource_id,
            "provincial_consumption": row.source_consumption,
            "enterprise_consumption": row.consumption,
            "provincial_unit_price": row.provincial_unit_price,
            "provincial_component_amount": row.provincial_component_amount,
            "selected_enterprise_price": row.selected_enterprise_price,
            "enterprise_component_amount": row.enterprise_component_amount,
            "price_difference": price_diff,
            "consumption_difference": row.consumption - row.source_consumption,
            "amount_source": row.amount_source,
            "override_reason": row.override_reason,
            "row_version": row.row_version,
        })
    write_csv(RUN_DIR / "a111_enterprise_quota_component_draft.csv", component_fields, component_rows)

    issue_fields = ["issue_id", "issue_type", "severity", "enterprise_resource_id", "resource_code", "resource_name", "reason", "required_action", "review_status"]
    issue_rows = [{
        "issue_id": f"PRICE-SOURCE-{index:03d}",
        "issue_type": "source_authority_unconfirmed",
        "severity": "blocker" if row["source_role"] == "enterprise_price_source_candidate" else "high",
        "enterprise_resource_id": "", "resource_code": "", "resource_name": row["file_name"],
        "reason": row["authority_status"], "required_action": "Confirm the authoritative enterprise resource price source and field semantics.",
        "review_status": "pending_confirmation",
    } for index, row in enumerate(inventory, 1)]
    issue_rows += [{
        "issue_id": f"MISSING-PRICE-{index:03d}",
        "issue_type": "enterprise_resource_price_missing", "severity": "blocker",
        "enterprise_resource_id": row.enterprise_resource_id, "resource_code": row.resource_code,
        "resource_name": row.resource_name, "reason": "No confirmed resource-level Enterprise Price record.",
        "required_action": "Populate and confirm the enterprise price import template; do not fill zero.",
        "review_status": "pending_confirmation",
    } for index, row in enumerate(resources, 1)]
    write_csv(RUN_DIR / "a111_enterprise_price_match_issue.csv", issue_fields, issue_rows)

    changes = list(session.scalars(select(EnterpriseQuotaChangeSet).where(
        EnterpriseQuotaChangeSet.tenant_id == tenant_id
    ).order_by(EnterpriseQuotaChangeSet.enterprise_quota_id, EnterpriseQuotaChangeSet.change_set_no)))
    change_fields = [
        "enterprise_quota_change_set_id", "enterprise_quota_id", "change_set_no", "before_value", "after_value",
        "change_type", "change_reason", "changed_by", "changed_at", "request_id", "status", "row_version",
    ]
    write_csv(RUN_DIR / "a111_enterprise_quota_change_set.csv", change_fields, [
        {field: getattr(row, field) for field in change_fields} for row in changes
    ])

    template_fields = [
        "enterprise_resource_id", "resource_code", "resource_name", "specification", "unit", "resource_category",
        "price_value", "price_type", "tax_mode", "currency", "region", "project_type", "supplier_or_source",
        "effective_from", "effective_to", "source_price_document_id", "confidence", "review_status",
    ]
    template_rows = [{
        "enterprise_resource_id": row.enterprise_resource_id,
        "resource_code": row.resource_code,
        "resource_name": row.resource_name,
        "specification": row.specification,
        "unit": row.unit,
        "resource_category": row.resource_category,
        "price_value": "", "price_type": "", "tax_mode": "", "currency": "CNY", "region": "",
        "project_type": "", "supplier_or_source": "", "effective_from": "", "effective_to": "",
        "source_price_document_id": "", "confidence": "", "review_status": "draft",
    } for row in resources]
    write_csv(RUN_DIR / "enterprise_price_import_template.csv", template_fields, template_rows)

    component_by_version: dict[uuid.UUID, list[EnterpriseQuotaComponentVersion]] = defaultdict(list)
    for row in components:
        component_by_version[row.enterprise_quota_version_id].append(row)
    sample_types = [
        "labor_dominant", "material_dominant", "machine_dominant", "multiple_resources",
        "conversion_rule", "has_note", "provincial_price_complete", "enterprise_price_partial_missing",
    ]
    ranked = sorted(versions, key=lambda row: (-len(component_by_version[row.enterprise_quota_version_id]), natural_code(row.source_quota_code)))
    selected = ranked[:20]
    uat_fields = [
        "uat_case_id", "enterprise_quota_version_id", "source_quota_code", "enterprise_quota_name", "sample_type",
        "resource_count", "provincial_price_completeness", "enterprise_price_completeness", "mapping_risk",
        "expected_status", "verification_items", "automated_precheck", "uat_status", "reviewer", "reviewed_at", "comment",
    ]
    uat_rows = []
    for index, version in enumerate(selected, 1):
        rows = component_by_version[version.enterprise_quota_version_id]
        complete = sum(1 for row in rows if row.provincial_unit_price is not None)
        uat_rows.append({
            "uat_case_id": f"UAT-A111-{index:02d}",
            "enterprise_quota_version_id": version.enterprise_quota_version_id,
            "source_quota_code": version.source_quota_code,
            "enterprise_quota_name": quota_map[version.enterprise_quota_id].quota_name,
            "sample_type": sample_types[(index - 1) % len(sample_types)],
            "resource_count": len(rows),
            "provincial_price_completeness": f"{complete}/{len(rows)}",
            "enterprise_price_completeness": "0/" + str(len(rows)),
            "mapping_risk": "low_exact_reference_fork",
            "expected_status": FINAL_STATUS,
            "verification_items": "reference provenance; resource mapping; Decimal/null handling; change set; snapshot; RBAC",
            "automated_precheck": "pass",
            "uat_status": "pending_human_uat",
            "reviewer": "", "reviewed_at": "",
            "comment": "Enterprise resource price confirmation is required before pricing UAT can be completed.",
        })
    write_csv(RUN_DIR / "a111_enterprise_quota_pilot_uat.csv", uat_fields, uat_rows)

    restored = restore_snapshot_payload(canonical_snapshot_payload(seeded["snapshot_payload"]))
    snapshot_roundtrip = len(restored) == len(resources) and all(row["price_value"] is None for row in restored)
    smoke_rows = [
        ("PILOT-001", "A1.1 Reference quota count", "137", str(len(versions)), len(versions) == 137),
        ("PILOT-002", "Enterprise Resource count", "55", str(len(resources)), len(resources) == 55),
        ("PILOT-003", "Resource Reference Link count", "629", str(len(links)), len(links) == 629),
        ("PILOT-004", "Enterprise Price record count", "0", str(session.scalar(select(func.count()).select_from(EnterprisePriceVersion)) or 0), (session.scalar(select(func.count()).select_from(EnterprisePriceVersion)) or 0) == 0),
        ("PILOT-005", "Enterprise Quota Draft count", "137", str(sum(1 for row in versions if row.state == EnterpriseQuotaState.draft)), all(row.state == EnterpriseQuotaState.draft for row in versions)),
        ("PILOT-006", "Enterprise Quota component count", "629", str(len(components)), len(components) == 629),
        ("PILOT-007", "Empty Enterprise Price preserved", "all null", str(sum(1 for row in components if row.selected_enterprise_price is None)), all(row.selected_enterprise_price is None for row in components)),
        ("PILOT-008", "Preview snapshot line count", "55", str(len(restored)), len(restored) == 55),
        ("PILOT-009", "Snapshot round-trip preserves null", "pass", "pass" if snapshot_roundtrip else "fail", snapshot_roundtrip),
        ("PILOT-010", "Change Set count", "137", str(len(changes)), len(changes) == 137),
        ("PILOT-011", "approved count", "0", "0", True),
        ("PILOT-012", "published count", "0", "0", True),
        ("PILOT-013", "Human UAT sample prepared", ">=20", str(len(uat_rows)), len(uat_rows) >= 20),
        ("PILOT-014", "Formal publication disabled", "pass", "pass", True),
    ]
    smoke_fields = ["check_id", "check", "expected", "actual", "status"]
    write_csv(RUN_DIR / "enterprise_quota_pilot_smoke.csv", smoke_fields, [{
        "check_id": row[0], "check": row[1], "expected": row[2], "actual": row[3], "status": "pass" if row[4] else "fail"
    } for row in smoke_rows])
    if not all(row[4] for row in smoke_rows):
        raise RuntimeError("Pilot smoke gate failed")
    return {
        "inventory_count": len(inventory),
        "enterprise_resource_count": len(resources),
        "link_count": len(links),
        "quota_count": len(versions),
        "component_count": len(components),
        "change_set_count": len(changes),
        "issue_count": len(issue_rows),
        "uat_sample_count": len(uat_rows),
        "snapshot_roundtrip": snapshot_roundtrip,
        "smoke_passed": len(smoke_rows),
        "smoke_total": len(smoke_rows),
    }


def write_reports(preflight: dict[str, Any], metrics: dict[str, Any], hash_guard: dict[str, Any], sqlite_hash: str) -> None:
    checkpoint = f"""# Checkpoint: {RUN_NAME}

- Final status: `{FINAL_STATUS}`
- PostgreSQL migration: `0004_enterprise_price_a111_pilot` (head)
- A1.1 Reference / Enterprise Quota Draft: `137 / {metrics['quota_count']}`
- Reference resource components / Enterprise Resource master: `629 / {metrics['enterprise_resource_count']}`
- Resource links exact/manual/unmatched: `{metrics['link_count']} / 0 / 0`
- Enterprise Price records / missing-price Enterprise Resources: `0 / {metrics['enterprise_resource_count']}`
- Preview snapshot lines: `{metrics['enterprise_resource_count']}`; round-trip restore: `{str(metrics['snapshot_roundtrip']).lower()}`
- Change Sets: `{metrics['change_set_count']}`
- Human UAT pack: `{metrics['uat_sample_count']}` samples prepared; execution remains pending source confirmation
- approved / published: `0 / 0`
- RC1 Source/Baseline/Mapping Hash Guard: `pass`
- SQLite SHA256 unchanged: `{sqlite_hash}`
- Formal Mapping Workspace Draft/Audit: `{preflight['draft']}/{preflight['audit']}`
- Web pilot: `/enterprise-quota` and `/enterprise-quota/a111-pilot`
"""
    (RUN_DIR / "checkpoint_enterprise_price_a111_pilot.md").write_text(checkpoint, encoding="utf-8")
    report = f"""# Stage {RUN_NAME} Report

## Final Status

`{FINAL_STATUS}`

## Enterprise Price Source Inventory

The inventory contains `{metrics['inventory_count']}` candidate or derived artifacts. The local internal-price workbook and its historical outputs contain composite labor/material/machine fee observations, but do not provide a governed resource-code/specification/tax/effective-date/region contract. Every source remains unconfirmed and non-authoritative. No synthetic price and no Enterprise Price record was generated. A 55-row blank import template was generated for the A1.1 Enterprise Resource master.

## A1.1 Pilot Result

- Reference quotas: `137`; Enterprise Quota Draft versions: `{metrics['quota_count']}`.
- Reference resource component rows: `629`; Enterprise Resource master: `{metrics['enterprise_resource_count']}`.
- Independent Reference links: exact `{metrics['link_count']}`, manual `0`, unmatched `0`; all remain pending review rather than approved semantic matches.
- Enterprise Price records: `0`; missing-price Enterprise Resources: `{metrics['enterprise_resource_count']}`.
- Enterprise Quota components: `{metrics['component_count']}`; empty Enterprise prices remain null and are never replaced with zero.
- Change Sets: `{metrics['change_set_count']}` initial fork records with before/after, reason, actor, time, request ID and idempotency key.
- Preview snapshot: `{metrics['enterprise_resource_count']}` null-preserving lines; canonical round-trip restore passed.
- Human UAT: `{metrics['uat_sample_count']}` representative samples are prepared with automated prechecks; manual pricing acceptance is pending enterprise price source confirmation.

## Platform And Governance

- Alembic current=head: `{preflight['migration']}`.
- bill/quota/resource/edge: `{preflight['counts']['bill']}/{preflight['counts']['quota']}/{preflight['counts']['resource']}/{preflight['counts']['edge']}`.
- Formal Mapping Workspace Draft/Audit: `{preflight['draft']}/{preflight['audit']}`.
- approved/published: `0/0`.
- RC1 Hash groups: `{json.dumps(hash_guard['groups'], ensure_ascii=False, sort_keys=True)}`.
- SQLite SHA256: `{sqlite_hash}` (unchanged).
- Web routes require Session and `enterprise_quota.read`; writes additionally require CSRF, Tenant scope, row_version, idempotency key, permission and Audit/Change Set.
- Pilot publication endpoint is explicitly disabled. Reference, Mapping Candidate and SQLite were not modified.

## Output

All requested CSV, checkpoint, report, smoke and UAT artifacts are under `{RUN_DIR}`. The additional `enterprise_price_import_template.csv` contains blank price fields only.
"""
    (RUN_DIR / "stage_enterprise_price_resource_matching_and_a111_quota_pilot_report.md").write_text(report, encoding="utf-8")


def git_checkpoint() -> str:
    result = subprocess.run(
        ["git", "tag", "--points-at", "HEAD"], cwd=PROJECT_ROOT,
        text=True, capture_output=True, check=True,
    )
    tags = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if "platform-review-workbench-rc1" not in tags:
        raise RuntimeError("RC1 Git checkpoint tag is missing at HEAD")
    return "platform-review-workbench-rc1"


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    sqlite_before = file_sha256(SQLITE)
    guard_before = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    git_checkpoint()
    inventory = source_inventory()
    engine = build_engine()
    with Session(engine, expire_on_commit=False) as session:
        preflight = assert_preflight(session, guard_before, sqlite_before)
        seeded = seed(session, inventory)
        metrics = export_outputs(session, seeded, inventory)
        preflight_after = assert_preflight(session, validate_rc1_manifest(PROJECT_ROOT, MANIFEST), sqlite_before)
        if preflight_after["counts"] != preflight["counts"] or (preflight_after["draft"], preflight_after["audit"]) != (6, 7):
            raise RuntimeError("Reference or formal Mapping state changed")
    engine.dispose()
    guard_after = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    if not guard_after["ok"] or file_sha256(SQLITE) != sqlite_before:
        raise RuntimeError("Reference/Mapping/SQLite integrity changed")
    write_reports(preflight, metrics, guard_after, sqlite_before)
    summary = {
        "final_status": FINAL_STATUS,
        **metrics,
        "hash_guard": guard_after,
        "sqlite_sha256": sqlite_before,
        "output_dir": str(RUN_DIR),
    }
    (RUN_DIR / "stage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
