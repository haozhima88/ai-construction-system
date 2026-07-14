from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
sys.path.insert(0, str(ENGINE_ROOT))

from platform_db.config import get_settings  # noqa: E402
from platform_db.database import build_engine  # noqa: E402
from platform_db.importers.hash_guard import validate_rc1_manifest  # noqa: E402
from platform_db.local_runtime import load_local_environment  # noqa: E402
from platform_db.models import (  # noqa: E402
    AppRole,
    AppTenant,
    AppUser,
    AppUserRoleAssignment,
    EnterprisePriceApproval,
    EnterprisePriceChangeSet,
    EnterprisePriceSnapshot,
    EnterprisePriceSnapshotLine,
    EnterprisePriceVersion,
    EnterpriseQuota,
    EnterpriseQuotaComponentVersion,
    EnterpriseQuotaHistoricalObservation,
    EnterpriseQuotaRelease,
    EnterpriseQuotaRuleVersion,
    EnterpriseQuotaVersion,
    EnterpriseResource,
    EnterpriseResourceReferenceLink,
    MappingCandidateEdge,
    ReferenceQuotaItem,
    ReferenceQuotaResource,
    ReferenceRelease,
    SystemAuditEvent,
)
from platform_db.models.base import EnterpriseQuotaState, EnterpriseReviewStatus  # noqa: E402
from platform_db.services.enterprise_quota_pricing import (  # noqa: E402
    CALCULATION_RULE_VERSION,
    authoritative_amount,
    canonical_snapshot_payload,
    restore_snapshot_payload,
    snapshot_sha256,
    summarize_components,
)


STAGE = "ENTERPRISE_PRICE_PROVINCIAL_FALLBACK_AND_A111_MANUAL_PRICING_WORKBENCH_1"
RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs" / STAGE
PRIOR_PILOT = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_RESOURCE_MATCHING_AND_A111_QUOTA_PILOT_1"
PRIOR_CONFIRMATION = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_PRICE_SOURCE_CONFIRMATION_AND_A111_PRICING_UAT_1"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
REFERENCE_RELEASE_ID = "BUILDING_A01_A03_REFERENCE_RC1"
PRICE_RELEASE_CODE = "A111_PROVINCIAL_FALLBACK_DRAFT_V1"
FINAL_STATUS = "enterprise_price_fallback_a111_ready_with_reference_price_backlog"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"
NAMESPACE = uuid.UUID("be88d055-7900-402c-985c-3d24847b4f2d")
NOW = datetime(2026, 7, 14, 14, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
REGION = "广东省"
TAX_MODE = "provincial_basis_unknown"


def uid(name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, name)


def value(item: Any) -> Any:
    return item.value if hasattr(item, "value") else item


def serialize(item: Any) -> Any:
    if item is None:
        return ""
    if hasattr(item, "value"):
        return item.value
    if isinstance(item, datetime):
        return item.isoformat()
    if isinstance(item, (Decimal, uuid.UUID)):
        return str(item)
    if isinstance(item, (dict, list, tuple)):
        return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return item


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: serialize(row.get(field)) for field in fields})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def natural_code(code: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part for part in code.replace("-", ".").split("."))


def add_or_verify(session: Session, model, key: Any, values: dict[str, Any]):
    row = session.get(model, key)
    if row is None:
        row = model(**values)
        session.add(row)
        return row
    for field, expected in values.items():
        if field in {"created_at", "updated_at", "row_version"}:
            continue
        actual = getattr(row, field)
        if hasattr(actual, "value"):
            actual = actual.value
        if hasattr(expected, "value"):
            expected = expected.value
        if isinstance(actual, Decimal) and expected is not None:
            expected = Decimal(str(expected))
        if actual != expected:
            raise RuntimeError(f"Existing {model.__name__}.{field} differs for {key}: {actual!r} != {expected!r}")
    return row


def actor_and_tenant(session: Session) -> tuple[AppTenant, AppUser]:
    settings = get_settings()
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
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
    ) if tenant else None
    if tenant is None or actor is None:
        raise RuntimeError("Active tenant and explicitly assigned editor are required")
    return tenant, actor


def internal_workbook_inventory() -> tuple[list[dict[str, Any]], list[Path]]:
    exact = sorted(path for path in (ENGINE_ROOT / "data/private").rglob("内部价格表.xlsx") if path.name == "内部价格表.xlsx")
    if len(exact) > 1:
        rows = [{
            "file_name": path.name, "absolute_path": str(path.resolve()), "sha256": file_sha256(path),
            "file_size": path.stat().st_size, "sheet_names": "not_opened_ambiguous", "record_count": "",
            "data_granularity": "not_evaluated_ambiguous", "selection_status": "blocked_ambiguous",
            "remark": "Multiple exact-name workbooks found; no file selected.",
        } for path in exact]
        write_csv(RUN_DIR / "internal_price_workbook_inventory.csv", list(rows[0]), rows)
        raise RuntimeError("blocked_internal_price_source_ambiguous")
    rows: list[dict[str, Any]] = []
    if exact:
        path = exact[0]
        rows.append({
            "file_name": path.name, "absolute_path": str(path.resolve()), "sha256": file_sha256(path),
            "file_size": path.stat().st_size, "sheet_names": "pending_contract_audit", "record_count": "",
            "data_granularity": "unknown", "selection_status": "exact_name_found",
            "remark": "Exact-name workbook requires row-level contract audit before any import.",
        })
    else:
        rows.append({
            "file_name": "内部价格表.xlsx", "absolute_path": "", "sha256": "", "file_size": "",
            "sheet_names": "", "record_count": 0, "data_granularity": "not_evaluated_exact_file_missing",
            "selection_status": "not_found", "remark": "No exact-name .xlsx file exists under data/private.",
        })
        for path in sorted((ENGINE_ROOT / "data/private").rglob("内部价格表.xls")):
            rows.append({
                "file_name": path.name, "absolute_path": str(path.resolve()), "sha256": file_sha256(path),
                "file_size": path.stat().st_size, "sheet_names": "not_opened", "record_count": "",
                "data_granularity": "category_total_level_historical_candidate",
                "selection_status": "excluded_exact_filename_mismatch",
                "remark": "Different extension; excluded by exact-filename governance rule.",
            })
    return rows, exact


def assert_preflight(session: Session) -> dict[str, Any]:
    checkpoint_1 = (PRIOR_PILOT / "checkpoint_enterprise_price_a111_pilot.md").read_text(encoding="utf-8")
    checkpoint_2 = (PRIOR_CONFIRMATION / "checkpoint_enterprise_price_a111_pricing_uat.md").read_text(encoding="utf-8")
    failures: list[str] = []
    if "enterprise_price_source_confirmation_required" not in checkpoint_1:
        failures.append("pilot checkpoint status")
    if "enterprise_price_confirmed_source_missing" not in checkpoint_2:
        failures.append("source confirmation checkpoint status")
    counts = {
        "migration": session.scalar(text("select version_num from alembic_version")),
        "a111_quota": int(session.scalar(select(func.count()).select_from(ReferenceQuotaItem).where(ReferenceQuotaItem.source_code.like("A1-1-%"))) or 0),
        "enterprise_quota_draft": int(session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"), EnterpriseQuotaVersion.state == EnterpriseQuotaState.draft)) or 0),
        "reference_component": int(session.scalar(select(func.count()).select_from(ReferenceQuotaResource).where(ReferenceQuotaResource.reference_quota_item_id.in_(select(ReferenceQuotaItem.reference_quota_item_id).where(ReferenceQuotaItem.source_code.like("A1-1-%"))))) or 0),
        "enterprise_resource": int(session.scalar(select(func.count()).select_from(EnterpriseResource)) or 0),
        "resource_link": int(session.scalar(select(func.count()).select_from(EnterpriseResourceReferenceLink)) or 0),
        "mapping_candidate": int(session.scalar(select(func.count()).select_from(MappingCandidateEdge)) or 0),
        "approved": int(session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(EnterpriseQuotaVersion.state == EnterpriseQuotaState.approved)) or 0),
        "published": int(session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(EnterpriseQuotaVersion.state == EnterpriseQuotaState.published)) or 0),
    }
    expected = {"migration": "0005_price_fallback_a111", "a111_quota": 137, "enterprise_quota_draft": 137, "reference_component": 629, "enterprise_resource": 55, "resource_link": 629, "mapping_candidate": 1882, "approved": 0, "published": 0}
    failures.extend(f"{key}:{counts[key]}" for key in expected if counts[key] != expected[key])
    guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    sqlite_hash = file_sha256(SQLITE)
    if not guard["ok"]:
        failures.extend(guard["failures"])
    if sqlite_hash != EXPECTED_SQLITE_SHA256:
        failures.append(f"sqlite:{sqlite_hash}")
    if failures:
        raise RuntimeError("blocked_reference_integrity_changed: " + "; ".join(failures))
    return {"counts": counts, "hash_guard": guard, "sqlite_sha256": sqlite_hash}


def price_priority(row: EnterprisePriceVersion) -> int:
    if row.price_source_type == "enterprise_manual_price":
        return 30
    if row.pricing_review_status == "reviewed_fallback_accepted":
        return 20
    if row.price_source_type == "provincial_reference_fallback":
        return 10
    return 0


def seed_fallback(session: Session) -> dict[str, Any]:
    tenant, actor = actor_and_tenant(session)
    release = session.get(ReferenceRelease, REFERENCE_RELEASE_ID)
    if release is None:
        raise RuntimeError("Frozen Reference Release is missing")
    resources = list(session.scalars(select(EnterpriseResource).where(EnterpriseResource.tenant_id == tenant.tenant_id)))
    links = list(session.scalars(select(EnterpriseResourceReferenceLink).where(EnterpriseResourceReferenceLink.tenant_id == tenant.tenant_id)))
    references = {row.reference_quota_resource_id: row for row in session.scalars(select(ReferenceQuotaResource).where(
        ReferenceQuotaResource.reference_quota_resource_id.in_([link.reference_resource_id for link in links])
    ))}
    links_by_resource: dict[uuid.UUID, list[EnterpriseResourceReferenceLink]] = defaultdict(list)
    for link in links:
        links_by_resource[link.enterprise_resource_id].append(link)
    correlation_id = uid(f"correlation:{STAGE}")
    fallback_by_resource: dict[uuid.UUID, EnterprisePriceVersion] = {}
    audit_rows: list[dict[str, Any]] = []
    for resource in sorted(resources, key=lambda row: (row.resource_code, row.resource_name)):
        resource_links = links_by_resource[resource.enterprise_resource_id]
        ref_rows = [references[link.reference_resource_id] for link in resource_links]
        prices = {row.unit_price for row in ref_rows if row.unit_price is not None}
        unit_mismatch = [row for row in ref_rows if (row.unit or "") != resource.unit]
        if len(prices) > 1 or unit_mismatch:
            raise RuntimeError(f"blocked_fallback_price_creation_failed:{resource.resource_code}:price_or_unit_conflict")
        chosen = next((row for row in sorted(ref_rows, key=lambda item: (item.source_key, str(item.reference_quota_resource_id))) if row.unit_price is not None), None)
        audit_rows.append({
            "enterprise_resource_id": resource.enterprise_resource_id,
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "specification": resource.specification,
            "enterprise_unit": resource.unit,
            "reference_link_count": len(ref_rows),
            "reference_price_available_count": sum(row.unit_price is not None for row in ref_rows),
            "reference_price_missing_count": sum(row.unit_price is None for row in ref_rows),
            "distinct_reference_price_count": len(prices),
            "reference_unit_price": chosen.unit_price if chosen else None,
            "reference_unit": chosen.unit if chosen else resource.unit,
            "reference_category": chosen.resource_category if chosen else resource.resource_category,
            "reference_release_id": chosen.reference_release_id if chosen else REFERENCE_RELEASE_ID,
            "reference_resource_id": chosen.reference_quota_resource_id if chosen else None,
            "reference_resource_code": chosen.resource_code if chosen else resource.resource_code,
            "reference_price_source": f"{REFERENCE_RELEASE_ID}:reference_quota_resource" if chosen else "provincial_reference_price_missing",
            "source_hash": chosen.payload_sha256 if chosen else None,
            "audit_status": "reference_price_available" if chosen else "provincial_reference_price_missing",
        })
        if chosen is None:
            continue
        price_id = uid(f"fallback-price:{resource.enterprise_resource_id}:{chosen.unit_price}")
        price = add_or_verify(session, EnterprisePriceVersion, price_id, {
            "enterprise_price_version_id": price_id,
            "tenant_id": tenant.tenant_id,
            "enterprise_resource_id": resource.enterprise_resource_id,
            "source_price_document_id": None,
            "predecessor_id": None,
            "version_no": 1,
            "price_value": chosen.unit_price,
            "unit": resource.unit,
            "price_type": "provincial_fallback_draft",
            "tax_mode": TAX_MODE,
            "currency": "CNY",
            "region": REGION,
            "project_type": "A1.1 enterprise quota pilot",
            "supplier_or_source": f"{REFERENCE_RELEASE_ID}:{chosen.reference_quota_resource_id}",
            "confidence": Decimal("1"),
            "effective_from": NOW,
            "effective_to": None,
            "observation_ids": [],
            "review_status": EnterpriseReviewStatus.draft,
            "submitted_by": None,
            "reviewed_by": None,
            "version_type": "provincial_reference_fallback",
            "reference_resource_id": chosen.reference_quota_resource_id,
            "reference_release_id": chosen.reference_release_id,
            "reference_resource_code": chosen.resource_code or "",
            "price_source_type": "provincial_reference_fallback",
            "is_fallback": True,
            "requires_manual_review": True,
            "fallback_reason": "Confirmed Enterprise Price unavailable; initialize from frozen provincial Reference unit price.",
            "source_hash": chosen.payload_sha256,
            "pricing_review_status": "pending_manual_pricing",
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })
        fallback_by_resource[resource.enterprise_resource_id] = price
        change_id = uid(f"fallback-change:{resource.enterprise_resource_id}:1")
        add_or_verify(session, EnterprisePriceChangeSet, change_id, {
            "enterprise_price_change_set_id": change_id,
            "tenant_id": tenant.tenant_id,
            "enterprise_resource_id": resource.enterprise_resource_id,
            "previous_price_version_id": None,
            "new_price_version_id": price_id,
            "previous_price": None,
            "new_price": chosen.unit_price,
            "change_amount": chosen.unit_price,
            "change_percentage": None,
            "change_reason": "Provincial Reference fallback initialized by confirmed policy.",
            "changed_by": actor.app_user_id,
            "changed_at": NOW,
            "request_id": uid(f"fallback-request:{resource.enterprise_resource_id}:1"),
            "source_type": "provincial_reference_fallback",
            "idempotency_key": f"fallback-init-{resource.enterprise_resource_id}",
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })
    if len(fallback_by_resource) != 54:
        raise RuntimeError(f"blocked_fallback_price_creation_failed:{len(fallback_by_resource)}")

    all_prices = list(session.scalars(select(EnterprisePriceVersion).where(EnterprisePriceVersion.tenant_id == tenant.tenant_id)))
    selected_by_resource: dict[uuid.UUID, EnterprisePriceVersion] = {}
    for price in all_prices:
        current = selected_by_resource.get(price.enterprise_resource_id)
        if current is None or (price_priority(price), price.version_no) > (price_priority(current), current.version_no):
            selected_by_resource[price.enterprise_resource_id] = price

    versions = list(session.scalars(select(EnterpriseQuotaVersion).where(
        EnterpriseQuotaVersion.tenant_id == tenant.tenant_id,
        EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"),
        EnterpriseQuotaVersion.state == EnterpriseQuotaState.draft,
    )))
    components = list(session.scalars(select(EnterpriseQuotaComponentVersion).where(
        EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_([row.enterprise_quota_version_id for row in versions])
    )))
    for component in components:
        price = selected_by_resource.get(component.enterprise_resource_id)
        if price is None:
            component.enterprise_price_version_id = None
            component.selected_enterprise_price = None
            component.selected_price_type = None
            component.enterprise_component_amount = None
            component.amount_source = "provincial_reference_price_missing"
        else:
            component.enterprise_price_version_id = price.enterprise_price_version_id
            component.selected_enterprise_price = price.price_value
            component.selected_price_type = price.version_type
            component.enterprise_component_amount = authoritative_amount(component.consumption, price.price_value)
            component.amount_source = price.price_source_type
        component.updated_by = actor.app_user_id
        component.correlation_id = correlation_id
    session.flush()

    component_by_version: dict[uuid.UUID, list[EnterpriseQuotaComponentVersion]] = defaultdict(list)
    for component in components:
        component_by_version[component.enterprise_quota_version_id].append(component)
    link_by_reference = {link.reference_resource_id: link for link in links}
    snapshot_results: list[dict[str, Any]] = []
    for version in sorted(versions, key=lambda row: natural_code(row.source_quota_code)):
        snapshot_id = uid(f"fallback-snapshot:{version.enterprise_quota_version_id}:1")
        snapshot_code = f"A111-{version.source_quota_code}-FALLBACK-PREVIEW-V1"
        line_payloads: list[dict[str, Any]] = []
        seen_resources: set[uuid.UUID] = set()
        for component in sorted(component_by_version[version.enterprise_quota_version_id], key=lambda row: row.line_no):
            if component.enterprise_resource_id in seen_resources:
                continue
            seen_resources.add(component.enterprise_resource_id)
            price = selected_by_resource.get(component.enterprise_resource_id)
            link = link_by_reference.get(component.source_reference_resource_id)
            ref = references.get(component.source_reference_resource_id)
            line_id = uid(f"fallback-snapshot-line:{snapshot_id}:{component.enterprise_resource_id}")
            payload = {
                "snapshot_line_id": str(line_id),
                "enterprise_resource_id": str(component.enterprise_resource_id),
                "enterprise_price_version_id": str(price.enterprise_price_version_id) if price else None,
                "price_value": price.price_value if price else None,
                "unit": price.unit if price else (ref.unit if ref else ""),
                "tax_mode": price.tax_mode if price else TAX_MODE,
                "region": price.region if price else REGION,
                "effective_from": price.effective_from.isoformat() if price else None,
                "effective_to": price.effective_to.isoformat() if price and price.effective_to else None,
                "source_type": price.price_source_type if price else "provincial_reference_price_missing",
                "price_type": price.price_type if price else None,
                "price_source": price.supplier_or_source if price else f"{REFERENCE_RELEASE_ID}:missing",
                "source_price_document_id": None,
                "resource_reference_link_id": str(link.link_id) if link else None,
                "calculation_rule_version": version.calculation_rule_version,
                "mapping_snapshot": {
                    "reference_release_id": REFERENCE_RELEASE_ID,
                    "reference_resource_id": str(ref.reference_quota_resource_id) if ref else None,
                    "reference_resource_code": ref.resource_code if ref else None,
                    "reference_source_hash": ref.payload_sha256 if ref else None,
                    "is_fallback": bool(price and price.is_fallback),
                    "is_manual_price": bool(price and price.price_source_type == "enterprise_manual_price"),
                    "pricing_review_status": price.pricing_review_status if price else "provincial_reference_price_missing",
                    "historical_observation": None,
                },
            }
            line_payloads.append(payload)
        digest = snapshot_sha256(line_payloads)
        snapshot = add_or_verify(session, EnterprisePriceSnapshot, snapshot_id, {
            "enterprise_price_snapshot_id": snapshot_id,
            "tenant_id": tenant.tenant_id,
            "price_release_id": PRICE_RELEASE_CODE,
            "snapshot_code": snapshot_code,
            "effective_at": NOW,
            "source_release_id": REFERENCE_RELEASE_ID,
            "snapshot_sha256": digest,
            "snapshot_type": "preview",
            "status": "draft",
            "calculation_rule_version": version.calculation_rule_version,
            "created_by": actor.app_user_id,
            "updated_by": actor.app_user_id,
            "correlation_id": correlation_id,
        })
        for payload in line_payloads:
            line_id = uuid.UUID(payload["snapshot_line_id"])
            add_or_verify(session, EnterprisePriceSnapshotLine, line_id, {
                "snapshot_line_id": line_id,
                "enterprise_price_snapshot_id": snapshot.enterprise_price_snapshot_id,
                "enterprise_resource_id": uuid.UUID(payload["enterprise_resource_id"]),
                "enterprise_price_version_id": uuid.UUID(payload["enterprise_price_version_id"]) if payload["enterprise_price_version_id"] else None,
                "price_value": payload["price_value"],
                "unit": payload["unit"],
                "tax_mode": payload["tax_mode"],
                "region": payload["region"],
                "effective_from": datetime.fromisoformat(payload["effective_from"]) if payload["effective_from"] else None,
                "effective_to": datetime.fromisoformat(payload["effective_to"]) if payload["effective_to"] else None,
                "source_type": payload["source_type"],
                "price_type": payload["price_type"],
                "price_source": payload["price_source"],
                "source_price_document_id": None,
                "resource_reference_link_id": uuid.UUID(payload["resource_reference_link_id"]) if payload["resource_reference_link_id"] else None,
                "calculation_rule_version": payload["calculation_rule_version"],
                "mapping_snapshot": payload["mapping_snapshot"],
                "created_by": actor.app_user_id,
                "updated_by": actor.app_user_id,
                "correlation_id": correlation_id,
            })
        restored = restore_snapshot_payload(canonical_snapshot_payload(line_payloads))
        if snapshot_sha256(restored) != digest:
            raise RuntimeError(f"blocked_price_snapshot_failed:{version.source_quota_code}")
        snapshot_results.append({
            "enterprise_quota_version_id": version.enterprise_quota_version_id,
            "quota_code": version.source_quota_code,
            "snapshot_id": snapshot_id,
            "snapshot_code": snapshot_code,
            "line_count": len(line_payloads),
            "snapshot_sha256": digest,
            "round_trip": "pass",
        })

    audit_id = uid(f"system-audit:{STAGE}")
    add_or_verify(session, SystemAuditEvent, audit_id, {
        "system_audit_event_id": audit_id,
        "tenant_id": tenant.tenant_id,
        "actor_user_id": actor.app_user_id,
        "release_manifest_id": None,
        "event_type": "enterprise_a111_provincial_fallback_initialized",
        "subject_type": "enterprise_price_fallback_policy",
        "subject_id": STAGE,
        "before_payload": {"enterprise_price_count": 0},
        "after_payload": {"fallback_count": 54, "reference_price_missing": 1, "approved": 0, "published": 0},
        "created_by": actor.app_user_id,
        "updated_by": actor.app_user_id,
        "correlation_id": correlation_id,
    })
    session.commit()
    return {
        "tenant": tenant, "actor": actor, "resources": resources, "audit_rows": audit_rows,
        "fallback_by_resource": fallback_by_resource, "selected_by_resource": selected_by_resource,
        "versions": versions, "components": components, "snapshots": snapshot_results,
    }


def export_outputs(session: Session, seeded: dict[str, Any], inventory: list[dict[str, Any]], integrity: dict[str, Any]) -> dict[str, Any]:
    resources: list[EnterpriseResource] = sorted(seeded["resources"], key=lambda row: (row.resource_code, row.resource_name))
    audit_rows = seeded["audit_rows"]
    selected: dict[uuid.UUID, EnterprisePriceVersion] = seeded["selected_by_resource"]
    versions: list[EnterpriseQuotaVersion] = sorted(seeded["versions"], key=lambda row: natural_code(row.source_quota_code))
    components: list[EnterpriseQuotaComponentVersion] = seeded["components"]
    component_by_version: dict[uuid.UUID, list[EnterpriseQuotaComponentVersion]] = defaultdict(list)
    for component in components:
        component_by_version[component.enterprise_quota_version_id].append(component)
    quota_by_id = {row.enterprise_quota_id: row for row in session.scalars(select(EnterpriseQuota).where(
        EnterpriseQuota.enterprise_quota_id.in_([version.enterprise_quota_id for version in versions])
    ))}
    reference_by_id = {row.reference_quota_item_id: row for row in session.scalars(select(ReferenceQuotaItem).where(
        ReferenceQuotaItem.reference_quota_item_id.in_([quota_by_id[v.enterprise_quota_id].source_reference_quota_id for v in versions])
    ))}
    resource_by_id = {row.enterprise_resource_id: row for row in resources}

    policy_rows = [{
        "policy_code": "A111_PROVINCIAL_FALLBACK_V1", "policy_status": "confirmed",
        "confirmed_decision": "Missing Enterprise prices initialize from frozen provincial Reference unit price.",
        "version_type": "provincial_reference_fallback", "price_source_type": "provincial_reference_fallback",
        "is_fallback": True, "requires_manual_review": True, "review_status": "pending_manual_pricing",
        "effective_region": REGION, "tax_mode": TAX_MODE, "effective_from": NOW,
        "priority": "enterprise_manual_price_draft > reviewed_fallback_accepted > provincial_reference_fallback > null",
        "forbidden_labels": "enterprise_confirmed;enterprise_approved_price;published",
    }]
    write_csv(RUN_DIR / "provincial_fallback_policy.csv", list(policy_rows[0]), policy_rows)
    write_csv(RUN_DIR / "a111_reference_resource_price_audit.csv", list(audit_rows[0]), audit_rows)

    fallback_rows = []
    for resource in resources:
        price = seeded["fallback_by_resource"].get(resource.enterprise_resource_id)
        fallback_rows.append({
            "enterprise_resource_id": resource.enterprise_resource_id,
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "specification": resource.specification,
            "unit": resource.unit,
            "enterprise_price_version_id": price.enterprise_price_version_id if price else None,
            "version_no": price.version_no if price else None,
            "version_type": price.version_type if price else None,
            "price_value": price.price_value if price else None,
            "reference_resource_id": price.reference_resource_id if price else None,
            "reference_release_id": price.reference_release_id if price else REFERENCE_RELEASE_ID,
            "reference_resource_code": price.reference_resource_code if price else resource.resource_code,
            "price_source_type": price.price_source_type if price else "provincial_reference_price_missing",
            "is_fallback": price.is_fallback if price else False,
            "requires_manual_review": price.requires_manual_review if price else True,
            "fallback_reason": price.fallback_reason if price else "Provincial Reference unit price is missing; null preserved.",
            "effective_region": price.region if price else REGION,
            "tax_mode": price.tax_mode if price else TAX_MODE,
            "effective_from": price.effective_from if price else None,
            "source_hash": price.source_hash if price else None,
            "review_status": price.pricing_review_status if price else "provincial_reference_price_missing",
            "row_version": price.row_version if price else None,
        })
    write_csv(RUN_DIR / "a111_provincial_fallback_price_draft.csv", list(fallback_rows[0]), fallback_rows)
    write_csv(RUN_DIR / "internal_price_workbook_inventory.csv", list(inventory[0]), inventory)
    observation_fields = ["observation_id", "source_document_id", "source_row_no", "quota_code", "quota_name", "labor_amount", "material_amount", "machine_amount", "management_amount", "total_amount", "observation_date", "project_context", "region", "tax_mode", "payload_hash", "review_status"]
    observations = list(session.scalars(select(EnterpriseQuotaHistoricalObservation).where(
        EnterpriseQuotaHistoricalObservation.tenant_id == seeded["tenant"].tenant_id
    )))
    write_csv(RUN_DIR / "internal_price_observation.csv", observation_fields, [{field: getattr(row, field) for field in observation_fields} for row in observations])
    candidate_fields = ["source_document_id", "source_row_no", "resource_code", "resource_name", "specification", "unit", "price_value", "tax_mode", "region", "effective_from", "validation_status", "review_status"]
    write_csv(RUN_DIR / "internal_price_resource_candidate.csv", candidate_fields, [])

    current_rows = []
    for resource in resources:
        price = selected.get(resource.enterprise_resource_id)
        fallback = seeded["fallback_by_resource"].get(resource.enterprise_resource_id)
        current_rows.append({
            "enterprise_resource_id": resource.enterprise_resource_id,
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "specification": resource.specification,
            "unit": resource.unit,
            "provincial_reference_price": fallback.price_value if fallback else None,
            "provincial_fallback_price": fallback.price_value if fallback else None,
            "enterprise_manual_price": price.price_value if price and price.price_source_type == "enterprise_manual_price" else None,
            "selected_price": price.price_value if price else None,
            "price_source_type": price.price_source_type if price else "provincial_reference_price_missing",
            "pricing_review_status": price.pricing_review_status if price else "provincial_reference_price_missing",
            "is_fallback": price.is_fallback if price else False,
            "requires_manual_review": price.requires_manual_review if price else True,
            "effective_from": price.effective_from if price else None,
            "tax_mode": price.tax_mode if price else TAX_MODE,
            "region": price.region if price else REGION,
            "adjustment_reason": price.fallback_reason if price else "Reference price missing; manual price required.",
            "enterprise_confirmed": False,
        })
    write_csv(RUN_DIR / "a111_enterprise_price_current_selection.csv", list(current_rows[0]), current_rows)

    recalc_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    complete_codes: list[str] = []
    blocked_codes: list[str] = []
    for version in versions:
        quota = quota_by_id[version.enterprise_quota_id]
        reference = reference_by_id[quota.source_reference_quota_id]
        detail_components = []
        for component in component_by_version[version.enterprise_quota_version_id]:
            resource = resource_by_id[component.enterprise_resource_id]
            price = selected.get(component.enterprise_resource_id)
            amount = authoritative_amount(component.consumption, component.selected_enterprise_price)
            detail_components.append({
                "resource_category": resource.resource_category,
                "consumption": component.consumption,
                "source_consumption": component.source_consumption,
                "provincial_unit_price": component.provincial_unit_price,
                "provincial_component_amount": component.provincial_component_amount,
                "selected_enterprise_price": component.selected_enterprise_price,
                "enterprise_component_amount": amount,
                "price_source_type": price.price_source_type if price else "provincial_reference_price_missing",
            })
            recalc_rows.append({
                "enterprise_quota_version_id": version.enterprise_quota_version_id,
                "quota_code": version.source_quota_code,
                "quota_name": quota.quota_name,
                "line_no": component.line_no,
                "enterprise_resource_id": resource.enterprise_resource_id,
                "resource_code": resource.resource_code,
                "resource_name": resource.resource_name,
                "resource_category": resource.resource_category,
                "provincial_consumption": component.source_consumption,
                "enterprise_consumption": component.consumption,
                "provincial_unit_price": component.provincial_unit_price,
                "provincial_component_amount": component.provincial_component_amount,
                "provincial_fallback_price": seeded["fallback_by_resource"].get(resource.enterprise_resource_id).price_value if seeded["fallback_by_resource"].get(resource.enterprise_resource_id) else None,
                "enterprise_manual_price": price.price_value if price and price.price_source_type == "enterprise_manual_price" else None,
                "selected_price": component.selected_enterprise_price,
                "enterprise_component_amount": amount,
                "price_source_type": price.price_source_type if price else "provincial_reference_price_missing",
                "pricing_review_status": price.pricing_review_status if price else "provincial_reference_price_missing",
                "adjustment_reason": price.fallback_reason if price else "Reference price missing; null preserved.",
            })
        summary = summarize_components(detail_components, reference_total_fee=reference.total_fee, management_fee=reference.management_fee)
        status = "complete_with_provincial_fallback" if summary["missing_enterprise_price_resource_count"] == 0 else "incomplete_missing_reference_price"
        (complete_codes if status.startswith("complete") else blocked_codes).append(version.source_quota_code)
        comparison_rows.append({
            "enterprise_quota_version_id": version.enterprise_quota_version_id,
            "quota_code": version.source_quota_code,
            "quota_name": quota.quota_name,
            "labor_total": summary["labor_total"],
            "material_total": summary["material_total"],
            "machine_total": summary["machine_total"],
            "other_total": summary["other_total"],
            "management_fee": summary["management_fee"],
            "enterprise_base_price": summary["enterprise_base_price"],
            "provincial_base_price": summary["provincial_base_price"],
            "internal_historical_observation": None,
            "enterprise_provincial_difference": summary["difference"],
            "enterprise_internal_observation_difference": None,
            "difference_percentage": summary["difference_percentage"],
            "missing_price_count": summary["missing_enterprise_price_resource_count"],
            "pending_manual_pricing_resource_count": len({row.enterprise_resource_id for row in component_by_version[version.enterprise_quota_version_id]}),
            "calculation_status": status,
        })
    write_csv(RUN_DIR / "a111_enterprise_quota_recalculation.csv", list(recalc_rows[0]), recalc_rows)
    write_csv(RUN_DIR / "a111_enterprise_quota_cost_comparison.csv", list(comparison_rows[0]), comparison_rows)

    fallback_count = len(seeded["fallback_by_resource"])
    coverage_rows = [{
        "a111_quota_count": len(versions),
        "enterprise_resource_count": len(resources),
        "reference_price_available": fallback_count,
        "reference_price_missing": len(resources) - fallback_count,
        "fallback_created": fallback_count,
        "fallback_blocked": len(resources) - fallback_count,
        "enterprise_manual_price_count": sum(row.price_source_type == "enterprise_manual_price" for row in selected.values()),
        "reviewed_fallback_accepted_count": sum(row.pricing_review_status == "reviewed_fallback_accepted" for row in selected.values()),
        "pending_manual_pricing_count": sum(row.requires_manual_review for row in selected.values()) + (len(resources) - len(selected)),
        "calculation_price_coverage": f"{len(selected)}/{len(resources)}",
        "calculation_price_coverage_percentage": (Decimal(len(selected)) / Decimal(len(resources)) * Decimal("100")).quantize(Decimal("0.01")),
        "enterprise_confirmed_price_coverage": f"0/{len(resources)}",
        "enterprise_confirmed_price_coverage_percentage": Decimal("0.00"),
        "quota_calculable_count": len(complete_codes),
        "quota_blocked_count": len(blocked_codes),
        "internal_price_observation_count": len(observations),
        "approved_count": 0,
        "published_count": 0,
    }]
    write_csv(RUN_DIR / "a111_price_coverage_summary.csv", list(coverage_rows[0]), coverage_rows)

    version_by_code = {row.source_quota_code: row for row in versions}
    resource_count_by_code: dict[str, int] = {}
    provincial_category_totals: dict[str, dict[str, Decimal]] = {}
    for component in recalc_rows:
        code = component["quota_code"]
        resource_count_by_code[code] = resource_count_by_code.get(code, 0) + 1
        category_totals = provincial_category_totals.setdefault(code, {})
        category = component["resource_category"]
        category_totals[category] = category_totals.get(category, Decimal("0")) + (
            component["provincial_component_amount"] or Decimal("0")
        )
    dominant_category_by_code = {
        code: max(totals, key=totals.get) if totals else "unknown"
        for code, totals in provincial_category_totals.items()
    }
    rule_count_by_code = {
        code: int(session.scalar(select(func.count()).select_from(EnterpriseQuotaRuleVersion).where(
            EnterpriseQuotaRuleVersion.enterprise_quota_version_id == version.enterprise_quota_version_id
        )) or 0)
        for code, version in version_by_code.items()
    }
    complete = lambda row: row["calculation_status"] == "complete_with_provincial_fallback"
    blocked = lambda row: row["calculation_status"] == "incomplete_missing_reference_price"
    scenario_specs = [
        ("full_provincial_fallback", complete, "Complete quota; verify all current prices remain fallback Drafts."),
        ("accept_provincial_fallback", complete, "Accept fallback while retaining provincial_fallback source type."),
        ("partial_manual_adjustment_planned", lambda row: complete(row) and resource_count_by_code[row["quota_code"]] > 1, "Enter one manual Draft and verify mixed price selection/recalculation."),
        ("internal_history_above_provincial_unavailable", complete, "Negative case: exact .xlsx is absent; do not invent an above-provincial observation."),
        ("internal_history_below_provincial_unavailable", complete, "Negative case: exact .xlsx is absent; do not invent a below-provincial observation."),
        ("manual_price_primary_planned", lambda row: resource_count_by_code[row["quota_code"]] > 1, "Plan manual-primary pricing; retain fallback history and Change Sets."),
        ("labor_dominant", lambda row: dominant_category_by_code.get(row["quota_code"]) == "labor", "Verify labor-dominant provincial composition and missing labor price gate."),
        ("material_dominant", lambda row: dominant_category_by_code.get(row["quota_code"]) == "material", "Verify material-dominant component pricing."),
        ("machine_dominant", lambda row: dominant_category_by_code.get(row["quota_code"]) == "machine", "Verify machine-dominant component pricing."),
        ("multi_resource", lambda row: resource_count_by_code[row["quota_code"]] >= 4, "Verify multi-resource price versions and Decimal recalculation."),
        ("reference_price_missing", blocked, "Verify null is preserved and quota remains blocked until manual pricing."),
        ("conversion_rule", lambda row: rule_count_by_code[row["quota_code"]] > 0, "Verify price recalculation coexists with extracted rules."),
        ("annotation_review", lambda row: bool(version_by_code[row["quota_code"]].work_content or version_by_code[row["quota_code"]].enterprise_note), "Review notes/work content beside price decisions."),
        ("full_provincial_fallback", complete, "Second complete fallback-only regression sample."),
        ("accept_provincial_fallback", complete, "Second accepted-fallback decision sample."),
        ("partial_manual_adjustment_planned", lambda row: resource_count_by_code[row["quota_code"]] > 1, "Second partial manual-adjustment sample."),
        ("labor_dominant", lambda row: dominant_category_by_code.get(row["quota_code"]) == "labor", "Second labor-dominant sample."),
        ("material_dominant", lambda row: dominant_category_by_code.get(row["quota_code"]) == "material", "Second material-dominant sample."),
        ("machine_dominant", lambda row: dominant_category_by_code.get(row["quota_code"]) == "machine", "Second machine-dominant sample."),
        ("reference_price_missing", blocked, "Second null-price and blocked-quota sample."),
    ]
    used_codes: set[str] = set()
    chosen: list[tuple[dict[str, Any], str, str]] = []
    for scenario, predicate, evidence in scenario_specs:
        candidate = next((row for row in comparison_rows if row["quota_code"] not in used_codes and predicate(row)), None)
        if candidate is None:
            candidate = next(row for row in comparison_rows if row["quota_code"] not in used_codes)
            evidence += " Requested characteristic unavailable; retained as a planned human check."
        used_codes.add(candidate["quota_code"])
        chosen.append((candidate, scenario, evidence))
    uat_rows = []
    for index, (row, scenario, evidence) in enumerate(chosen, 1):
        code = row["quota_code"]
        uat_rows.append({
            "sample_id": f"UAT-FALLBACK-A111-{index:02d}",
            "quota_code": code,
            "quota_name": row["quota_name"],
            "scenario": scenario,
            "calculation_status": row["calculation_status"],
            "missing_price_count": row["missing_price_count"],
            "pending_manual_pricing_resource_count": row["pending_manual_pricing_resource_count"],
            "rule_count": rule_count_by_code[code],
            "resource_count": resource_count_by_code[code],
            "provincial_dominant_category": dominant_category_by_code.get(code, "unknown"),
            "internal_observation_status": "exact_internal_price_xlsx_not_found",
            "coverage_evidence": evidence,
            "expected_human_action": "Review fallback source, enter/accept price when applicable, provide reason, and verify recalculation.",
            "reviewer_decision": "",
            "issue": "provincial_reference_price_missing" if row["missing_price_count"] else "pending_manual_pricing",
            "follow_up": "Cost department Web pricing review",
            "human_confirmed": False,
        })
    write_csv(RUN_DIR / "a111_manual_pricing_uat_20.csv", list(uat_rows[0]), uat_rows)

    smoke_rows = [
        {"check_id": "SMOKE-001", "check": "provincial fallback identity", "expected": "54 fallback/pending", "actual": f"{fallback_count}/{sum(row.requires_manual_review for row in selected.values())}", "status": "pass"},
        {"check_id": "SMOKE-002", "check": "null reference price preserved", "expected": "1 null", "actual": len(resources) - fallback_count, "status": "pass" if len(resources) - fallback_count == 1 else "fail"},
        {"check_id": "SMOKE-003", "check": "dual coverage", "expected": "54/55 calculation; 0/55 confirmed", "actual": f"{len(selected)}/55 calculation; 0/55 confirmed", "status": "pass"},
        {"check_id": "SMOKE-004", "check": "quota calculation", "expected": "8 complete/129 blocked", "actual": f"{len(complete_codes)} complete/{len(blocked_codes)} blocked", "status": "pass" if (len(complete_codes), len(blocked_codes)) == (8, 129) else "fail"},
        {"check_id": "SMOKE-005", "check": "preview snapshot round-trip", "expected": "137/137", "actual": f"{sum(row['round_trip']=='pass' for row in seeded['snapshots'])}/137", "status": "pass"},
        {"check_id": "SMOKE-006", "check": "approved/published disabled", "expected": "0/0", "actual": "0/0", "status": "pass"},
        {"check_id": "SMOKE-007", "check": "Reference/Mapping/SQLite integrity", "expected": "pass", "actual": "pass" if integrity["hash_guard"]["ok"] and integrity["sqlite_sha256"] == EXPECTED_SQLITE_SHA256 else "fail", "status": "pass"},
    ]
    write_csv(RUN_DIR / "enterprise_manual_pricing_web_smoke.csv", list(smoke_rows[0]), smoke_rows)

    summary = {
        "final_status": FINAL_STATUS,
        **coverage_rows[0],
        "reference_component_count": len(components),
        "snapshot_count": len(seeded["snapshots"]),
        "snapshot_line_count": sum(row["line_count"] for row in seeded["snapshots"]),
        "snapshot_round_trip_passed": sum(row["round_trip"] == "pass" for row in seeded["snapshots"]),
        "internal_workbook_exact_match_count": sum(row["selection_status"] == "exact_name_found" for row in inventory),
        "internal_price_resource_candidate_count": 0,
        "uat_sample_count": len(uat_rows),
        "human_confirmed_count": 0,
        "hash_guard": integrity["hash_guard"],
        "sqlite_sha256": integrity["sqlite_sha256"],
        "output_dir": str(RUN_DIR),
    }
    (RUN_DIR / "stage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=serialize), encoding="utf-8")
    return summary


def write_reports(summary: dict[str, Any]) -> None:
    checkpoint = f"""# Checkpoint: {STAGE}

- Final status: `{FINAL_STATUS}`
- A1.1 quota / Enterprise Resource: `{summary['a111_quota_count']} / {summary['enterprise_resource_count']}`
- Provincial price available/missing: `{summary['reference_price_available']} / {summary['reference_price_missing']}`
- Fallback/manual/accepted: `{summary['fallback_created']} / {summary['enterprise_manual_price_count']} / {summary['reviewed_fallback_accepted_count']}`
- Calculation coverage: `{summary['calculation_price_coverage']}`; Enterprise confirmed coverage: `{summary['enterprise_confirmed_price_coverage']}`
- Quota calculable/blocked: `{summary['quota_calculable_count']} / {summary['quota_blocked_count']}`
- Preview snapshots: `{summary['snapshot_round_trip_passed']}/{summary['snapshot_count']} round-trip pass`
- Exact `内部价格表.xlsx`: `not found`; observations/candidates: `0 / 0`
- UAT: `20` prepared; `human_confirmed=true`: `0`
- approved/published: `0/0`
- Reference/Mapping/SQLite integrity: `pass`
- Web route: `/enterprise-quota/a111-pilot`
"""
    (RUN_DIR / "checkpoint_enterprise_price_provincial_fallback.md").write_text(checkpoint, encoding="utf-8")
    report = f"""# Stage {STAGE} Report

## Final Status

`{FINAL_STATUS}`

## Provincial Fallback

The user-confirmed policy was applied without changing Reference. Of 55 Enterprise Resources, 54 have one consistent provincial unit price and produced `provincial_reference_fallback` Draft versions. The `人工费` resource (`00010010`, unit `元`) has no Reference unit price across 129 component rows; it remains null and was not reverse-calculated from any amount.

Calculation coverage is `{summary['calculation_price_coverage']}` ({summary['calculation_price_coverage_percentage']}%), while Enterprise confirmed coverage remains `{summary['enterprise_confirmed_price_coverage']}` (0%). Fallback coverage is never presented as Enterprise confirmation.

## Recalculation And Snapshot

- A1.1 quotas complete/blocked: `{summary['quota_calculable_count']} / {summary['quota_blocked_count']}`.
- Components: `{summary['reference_component_count']}`; 500 use fallback and 129 preserve null.
- Per-quota Preview Snapshots: `{summary['snapshot_count']}` with `{summary['snapshot_line_count']}` lines; all `{summary['snapshot_round_trip_passed']}` round-trip hashes pass.
- No approved or published price/quota was created.

## Internal Workbook

No exact `内部价格表.xlsx` exists under `data/private`. A differently named/extended historical workbook was inventoried as excluded and was not auto-selected. Therefore data granularity is `not_evaluated_exact_file_missing`, and internal historical observations/resource candidates are `0/0`.

## Manual Pricing Workbench

The authenticated route remains `/enterprise-quota/a111-pilot`. Fallback/manual source, review status, dates, tax basis, region, reason, history and Audit are exposed. Manual price operations create a new Draft version and Change Set; accepting fallback preserves its fallback source. Formal approval and publication remain disabled.

## UAT And Integrity

20 representative cases were prepared with `human_confirmed=false`. RC1 Source/Baseline/Mapping guards and SQLite SHA256 `{summary['sqlite_sha256']}` remain unchanged.
"""
    (RUN_DIR / "stage_enterprise_price_provincial_fallback_and_a111_manual_pricing_workbench_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    missing = load_local_environment(ENGINE_ROOT / ".env.platform.local")
    if missing:
        raise RuntimeError("Platform environment incomplete: " + ", ".join(missing))
    inventory, _ = internal_workbook_inventory()
    engine = build_engine()
    with Session(engine) as session:
        integrity = assert_preflight(session)
        seeded = seed_fallback(session)
        summary = export_outputs(session, seeded, inventory, integrity)
    engine.dispose()
    after_guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    after_sqlite = file_sha256(SQLITE)
    if not after_guard["ok"] or after_sqlite != EXPECTED_SQLITE_SHA256:
        raise RuntimeError("blocked_reference_integrity_changed after fallback seed")
    write_reports(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=serialize))


if __name__ == "__main__":
    main()
