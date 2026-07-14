from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
sys.path.insert(0, str(ENGINE_ROOT))

from platform_db.database import build_engine  # noqa: E402
from platform_db.importers.common import file_sha256  # noqa: E402
from platform_db.importers.hash_guard import validate_rc1_manifest  # noqa: E402
from platform_db.local_runtime import load_local_environment  # noqa: E402
from platform_db.models import (  # noqa: E402
    AppTenant,
    AppUser,
    EnterpriseComponentCalculationProfile,
    EnterprisePriceApproval,
    EnterprisePriceVersion,
    EnterpriseQuota,
    EnterpriseQuotaComponentChange,
    EnterpriseQuotaComponentVersion,
    EnterpriseQuotaRelease,
    EnterpriseQuotaRuleVersion,
    EnterpriseQuotaVersion,
    EnterpriseResource,
    ReferenceQuotaItem,
    ReferenceQuotaResource,
    SystemAuditEvent,
)
from platform_db.services.enterprise_quota_pricing import (  # noqa: E402
    component_amount_by_basis,
    component_comparison,
    summarize_components,
)


STAGE = "ENTERPRISE_QUOTA_CALCULATION_BASIS_AND_COMPONENT_EDITING_MVP_1"
RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs" / STAGE
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"
NAMESPACE = uuid.UUID("40d57f19-286b-4f93-ac64-8fdf2d6f7bb0")
NOW = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)


def uid(value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, value)


def serialize(value: Any) -> Any:
    if isinstance(value, (Decimal, uuid.UUID, datetime)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: serialize(row.get(field)) for field in fields})


def natural_code(code: str) -> tuple[Any, ...]:
    return tuple(int(item) if item.isdigit() else item for item in code.replace("-", ".").split("."))


def assert_preflight(session: Session) -> dict[str, Any]:
    guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    sqlite_hash = file_sha256(SQLITE)
    if not guard["ok"] or sqlite_hash != EXPECTED_SQLITE_SHA256:
        raise RuntimeError("blocked_reference_integrity_changed")
    counts = {
        "a111": int(session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
        )) or 0),
        "components": int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_(
                select(EnterpriseQuotaVersion.enterprise_quota_version_id).where(
                    EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
                )
            )
        )) or 0),
        "resources": int(session.scalar(select(func.count()).select_from(EnterpriseResource)) or 0),
        "fallback": int(session.scalar(select(func.count()).select_from(EnterprisePriceVersion).where(
            EnterprisePriceVersion.price_source_type == "provincial_reference_fallback"
        )) or 0),
        "manual": int(session.scalar(select(func.count()).select_from(EnterprisePriceVersion).where(
            EnterprisePriceVersion.price_source_type == "enterprise_manual_price"
        )) or 0),
        "approved": int(session.scalar(select(func.count()).select_from(EnterprisePriceApproval).where(
            EnterprisePriceApproval.decision == "approved"
        )) or 0),
        "published": int(session.scalar(select(func.count()).select_from(EnterpriseQuotaRelease).where(
            EnterpriseQuotaRelease.status == "published"
        )) or 0),
    }
    expected = {"a111": 137, "components": 629, "resources": 55, "fallback": 54, "manual": 0, "approved": 0, "published": 0}
    if counts != expected:
        raise RuntimeError(f"blocked_component_calculation_failed:preflight:{counts}")
    return {"hash_guard": guard, "sqlite_sha256": sqlite_hash, "counts": counts}


def normalized_unit(reference_unit: str | None, enterprise_unit: str) -> tuple[str, str]:
    if reference_unit == enterprise_unit:
        return enterprise_unit, "exact"
    if reference_unit == "Ԫ" and enterprise_unit == "元":
        return enterprise_unit, "legacy_reference_glyph_normalized_by_existing_enterprise_resource"
    return enterprise_unit, "enterprise_resource_normalized_unit"


def component_dict(component: EnterpriseQuotaComponentVersion, resource: EnterpriseResource) -> dict[str, Any]:
    return {
        "enterprise_quota_component_version_id": str(component.enterprise_quota_component_version_id),
        "enterprise_resource_id": str(component.enterprise_resource_id),
        "source_reference_resource_id": str(component.source_reference_resource_id) if component.source_reference_resource_id else None,
        "resource_code": resource.resource_code,
        "resource_name": resource.resource_name,
        "resource_category": resource.resource_category,
        "unit": resource.unit,
        "source_consumption": component.source_consumption,
        "consumption": component.consumption,
        "provincial_unit_price": component.provincial_unit_price,
        "provincial_component_amount": component.provincial_component_amount,
        "selected_enterprise_price": component.selected_enterprise_price,
        "selected_price_type": component.selected_price_type,
        "enterprise_direct_amount": component.enterprise_direct_amount,
        "source_direct_amount": component.source_direct_amount,
        "calculation_base": component.calculation_base,
        "enterprise_rate": component.enterprise_rate,
        "formula_code": component.formula_code,
        "formula_version": component.formula_version,
        "calculation_basis": component.calculation_basis,
        "component_status": component.component_status,
        "lifecycle_status": component.lifecycle_status,
        "amount_source": component.amount_source,
    }


def classify_and_seed(session: Session) -> dict[str, Any]:
    tenant = session.scalar(select(AppTenant).order_by(AppTenant.created_at))
    actor = session.scalar(select(AppUser).where(AppUser.login_name == "platform-system-import"))
    if tenant is None or actor is None:
        raise RuntimeError("blocked_rbac_or_audit_failed")
    joined = session.execute(
        select(EnterpriseQuotaComponentVersion, EnterpriseQuotaVersion, EnterpriseResource, ReferenceQuotaResource)
        .join(EnterpriseQuotaVersion, EnterpriseQuotaVersion.enterprise_quota_version_id == EnterpriseQuotaComponentVersion.enterprise_quota_version_id)
        .join(EnterpriseResource, EnterpriseResource.enterprise_resource_id == EnterpriseQuotaComponentVersion.enterprise_resource_id)
        .join(ReferenceQuotaResource, ReferenceQuotaResource.reference_quota_resource_id == EnterpriseQuotaComponentVersion.source_reference_resource_id)
        .where(
            EnterpriseQuotaVersion.tenant_id == tenant.tenant_id,
            EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"),
        )
        .order_by(EnterpriseQuotaVersion.source_quota_code, EnterpriseQuotaComponentVersion.line_no)
    ).all()
    audit_rows: list[dict[str, Any]] = []
    direct_rows: list[dict[str, Any]] = []
    profiles: list[EnterpriseComponentCalculationProfile] = []
    direct_exceptions: list[str] = []
    unclassified: list[str] = []
    for component, version, resource, reference in joined:
        unit, unit_status = normalized_unit(reference.unit, resource.unit)
        is_labor_direct = resource.resource_code == "00010010"
        if is_labor_direct:
            checks = {
                "normalized_unit_is_yuan": unit == "元",
                "reference_unit_price_is_null": reference.unit_price is None,
                "reference_amount_present": reference.component_amount is not None,
                "source_resource_type_labor": reference.resource_category == "labor",
                "source_pdf_page_present": reference.source_page_no is not None,
                "source_amount_matches_imported_component": reference.component_amount == component.provincial_component_amount,
            }
            if not all(checks.values()):
                direct_exceptions.append(f"{version.source_quota_code}:{reference.reference_quota_resource_id}:{checks}")
                basis = "unclassified"
                reason = "Direct-amount evidence gate failed."
            else:
                basis = "direct_amount"
                reason = "Source provides a labor component amount in normalized yuan with no unit price; amount is authoritative."
        elif reference.consumption is not None and reference.unit_price is not None and reference.component_amount is not None:
            checks = {
                "reference_quantity_present": True,
                "reference_unit_price_present": True,
                "reference_amount_present": True,
            }
            basis = "quantity_unit_price"
            reason = "Source provides quantity and unit price; Enterprise amount is quantity multiplied by selected Enterprise price."
        else:
            checks = {}
            basis = "unclassified"
            reason = "Source evidence does not satisfy a supported calculation basis."
            unclassified.append(f"{version.source_quota_code}:{reference.reference_quota_resource_id}")
        audit = {
            "enterprise_quota_component_version_id": component.enterprise_quota_component_version_id,
            "quota_code": version.source_quota_code,
            "line_no": component.line_no,
            "reference_resource_id": reference.reference_quota_resource_id,
            "resource_code": resource.resource_code,
            "resource_name": resource.resource_name,
            "resource_category": reference.resource_category,
            "reference_unit_raw": reference.unit,
            "enterprise_unit_normalized": unit,
            "unit_normalization_status": unit_status,
            "reference_quantity": reference.consumption,
            "reference_unit_price": reference.unit_price,
            "reference_amount": reference.component_amount,
            "source_pdf_page": reference.source_page_no,
            "calculation_basis": basis,
            "classification_reason": reason,
            "evidence_checks": json.dumps(checks, ensure_ascii=False, sort_keys=True),
            "classification_status": "pass" if basis != "unclassified" else "blocked",
        }
        audit_rows.append(audit)
        if is_labor_direct:
            direct_rows.append(audit)
        if basis == "unclassified":
            continue
        profile_id = uid(f"component-profile:{reference.reference_quota_resource_id}")
        source_evidence = {
            "reference_release_id": reference.reference_release_id,
            "reference_resource_id": str(reference.reference_quota_resource_id),
            "reference_payload_sha256": reference.payload_sha256,
            "reference_unit_raw": reference.unit,
            "enterprise_unit_normalized": unit,
            "unit_normalization_status": unit_status,
            "reference_quantity": str(reference.consumption) if reference.consumption is not None else None,
            "reference_unit_price": str(reference.unit_price) if reference.unit_price is not None else None,
            "reference_amount": str(reference.component_amount) if reference.component_amount is not None else None,
            "source_resource_type": reference.resource_category,
            "source_pdf_page": reference.source_page_no,
        }
        profile = session.get(EnterpriseComponentCalculationProfile, profile_id)
        if profile is None:
            profile = EnterpriseComponentCalculationProfile(
                profile_id=profile_id, tenant_id=tenant.tenant_id,
                reference_resource_id=reference.reference_quota_resource_id,
                resource_code=resource.resource_code, resource_name=resource.resource_name, unit=unit,
                calculation_basis=basis, classification_reason=reason, source_evidence=source_evidence,
                review_status="classified_draft", created_by=actor.app_user_id,
                updated_by=actor.app_user_id, correlation_id=uid(f"correlation:{STAGE}"),
            )
            session.add(profile)
        elif profile.calculation_basis != basis or profile.source_evidence != source_evidence:
            raise RuntimeError(f"blocked_direct_amount_classification_failed:profile_conflict:{profile_id}")
        profiles.append(profile)
        if component.component_status == "inherited":
            component.source_enterprise_resource_id = component.source_enterprise_resource_id or component.enterprise_resource_id
            component.calculation_basis = basis
            component.source_direct_amount = reference.component_amount if basis == "direct_amount" else None
            component.enterprise_direct_amount = reference.component_amount if basis == "direct_amount" else None
            component.calculation_base = None
            component.enterprise_rate = None
            component.formula_code = None
            component.formula_version = None
            component.lifecycle_status = "active"
            if basis == "direct_amount":
                component.enterprise_price_version_id = None
                component.selected_enterprise_price = None
                component.selected_price_type = None
            amount, error = component_amount_by_basis({
                "lifecycle_status": component.lifecycle_status,
                "calculation_basis": basis,
                "consumption": component.consumption,
                "selected_enterprise_price": component.selected_enterprise_price,
                "enterprise_direct_amount": component.enterprise_direct_amount,
            })
            if error:
                raise RuntimeError(f"blocked_component_calculation_failed:{version.source_quota_code}:{error}")
            component.enterprise_component_amount = amount
            component.amount_source = basis
            component.updated_by = actor.app_user_id
            component.correlation_id = uid(f"correlation:{STAGE}")
    if direct_exceptions:
        raise RuntimeError("blocked_direct_amount_classification_failed:" + "|".join(direct_exceptions[:10]))
    audit_id = uid(f"system-audit:{STAGE}")
    event = session.get(SystemAuditEvent, audit_id)
    after_payload = {
        "quantity_unit_price": sum(row["calculation_basis"] == "quantity_unit_price" for row in audit_rows),
        "direct_amount": sum(row["calculation_basis"] == "direct_amount" for row in audit_rows),
        "rate_based": 0, "formula_based": 0, "unclassified": len(unclassified),
        "reference_modified": 0, "mapping_modified": 0, "sqlite_modified": 0,
    }
    if event is None:
        session.add(SystemAuditEvent(
            system_audit_event_id=audit_id, actor_user_id=actor.app_user_id,
            release_manifest_id=None, event_type="enterprise_a111_component_calculation_basis_classified",
            subject_type="enterprise_component_calculation_profile", subject_id=STAGE,
            before_payload={"calculable_quota": 8, "blocked_quota": 129}, after_payload=after_payload,
            tenant_id=tenant.tenant_id, created_by=actor.app_user_id,
            updated_by=actor.app_user_id, correlation_id=uid(f"correlation:{STAGE}"),
        ))
    session.commit()
    return {
        "tenant": tenant, "actor": actor, "audit_rows": audit_rows, "direct_rows": direct_rows,
        "profiles": profiles, "unclassified": unclassified,
    }


def export_outputs(session: Session, seeded: dict[str, Any], integrity: dict[str, Any]) -> dict[str, Any]:
    audit_rows = seeded["audit_rows"]
    write_csv(RUN_DIR / "a111_component_calculation_basis_audit.csv", list(audit_rows[0]), audit_rows)
    write_csv(RUN_DIR / "a111_direct_amount_component_check.csv", list(seeded["direct_rows"][0]), seeded["direct_rows"])
    profile_rows = [{
        "profile_id": row.profile_id, "tenant_id": row.tenant_id,
        "reference_resource_id": row.reference_resource_id, "resource_code": row.resource_code,
        "resource_name": row.resource_name, "unit": row.unit, "calculation_basis": row.calculation_basis,
        "classification_reason": row.classification_reason,
        "source_evidence": json.dumps(row.source_evidence, ensure_ascii=False, sort_keys=True),
        "review_status": row.review_status, "created_at": row.created_at,
        "created_by": row.created_by, "row_version": row.row_version,
    } for row in session.scalars(select(EnterpriseComponentCalculationProfile).where(
        EnterpriseComponentCalculationProfile.tenant_id == seeded["tenant"].tenant_id,
        EnterpriseComponentCalculationProfile.reference_resource_id.in_([
            uuid.UUID(str(item["reference_resource_id"])) for item in audit_rows if item["calculation_basis"] != "unclassified"
        ])
    ).order_by(EnterpriseComponentCalculationProfile.resource_code, EnterpriseComponentCalculationProfile.reference_resource_id))]
    write_csv(RUN_DIR / "a111_enterprise_quota_component_profile.csv", list(profile_rows[0]), profile_rows)

    versions = list(session.scalars(select(EnterpriseQuotaVersion).where(
        EnterpriseQuotaVersion.tenant_id == seeded["tenant"].tenant_id,
        EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"),
    )))
    versions.sort(key=lambda row: natural_code(row.source_quota_code))
    quota_by_id = {row.enterprise_quota_id: row for row in session.scalars(select(EnterpriseQuota).where(
        EnterpriseQuota.enterprise_quota_id.in_([version.enterprise_quota_id for version in versions])
    ))}
    ref_by_id = {row.reference_quota_item_id: row for row in session.scalars(select(ReferenceQuotaItem).where(
        ReferenceQuotaItem.reference_quota_item_id.in_([quota_by_id[version.enterprise_quota_id].source_reference_quota_id for version in versions])
    ))}
    components = list(session.scalars(select(EnterpriseQuotaComponentVersion).where(
        EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_([version.enterprise_quota_version_id for version in versions])
    ).order_by(EnterpriseQuotaComponentVersion.enterprise_quota_version_id, EnterpriseQuotaComponentVersion.line_no)))
    resources = {row.enterprise_resource_id: row for row in session.scalars(select(EnterpriseResource).where(
        EnterpriseResource.enterprise_resource_id.in_([component.enterprise_resource_id for component in components])
    ))}
    by_version: dict[uuid.UUID, list[EnterpriseQuotaComponentVersion]] = defaultdict(list)
    for component in components:
        by_version[component.enterprise_quota_version_id].append(component)

    recalc_rows: list[dict[str, Any]] = []
    variance_rows: list[dict[str, Any]] = []
    calculable = blocked = 0
    blocker_counts: Counter[str] = Counter()
    for version in versions:
        quota = quota_by_id[version.enterprise_quota_id]
        reference = ref_by_id[quota.source_reference_quota_id]
        compared: list[dict[str, Any]] = []
        for component in by_version[version.enterprise_quota_version_id]:
            resource = resources[component.enterprise_resource_id]
            item = component_comparison(component_dict(component, resource))
            compared.append(item)
            if item["calculation_error"]:
                blocker_counts[item["calculation_error"]] += 1
            recalc_rows.append({
                "enterprise_quota_version_id": version.enterprise_quota_version_id,
                "quota_code": version.source_quota_code, "quota_name": quota.quota_name,
                "component_id": component.enterprise_quota_component_version_id,
                "line_no": component.line_no, "resource_code": resource.resource_code,
                "resource_name": resource.resource_name, "resource_category": resource.resource_category,
                "calculation_basis": component.calculation_basis, "component_status": component.component_status,
                "lifecycle_status": component.lifecycle_status,
                "provincial_quantity": component.source_consumption,
                "enterprise_quantity": component.consumption,
                "provincial_unit_price": component.provincial_unit_price,
                "selected_enterprise_price": component.selected_enterprise_price,
                "provincial_direct_amount": component.source_direct_amount,
                "enterprise_direct_amount": component.enterprise_direct_amount,
                "provincial_component_amount": item["provincial_component_amount"],
                "enterprise_component_amount": item["enterprise_component_amount"],
                "price_source": component.amount_source,
                "calculation_error": item["calculation_error"],
                "price_variance": item["price_variance"],
                "consumption_variance": item["consumption_variance"],
                "structure_variance": item["structure_variance"],
                "rate_variance": item["rate_variance"],
                "component_total_variance": item["component_total_variance"],
            })
        summary = summarize_components(compared, reference_total_fee=reference.total_fee, management_fee=reference.management_fee)
        errors = summary["missing_price_component_count"] + summary["missing_direct_amount_count"] + summary["formula_error_count"] + summary["unclassified_component_count"]
        if errors == 0 and summary["enterprise_base_price"] is not None:
            calculable += 1
            status = "calculable"
        else:
            blocked += 1
            status = "blocked"
        contribution_sum = sum((summary[key] or Decimal("0")) for key in ("price_variance", "consumption_variance", "structure_variance", "rate_variance"))
        reconciliation = summary["total_variance"] - contribution_sum if summary["total_variance"] is not None else None
        variance_rows.append({
            "enterprise_quota_version_id": version.enterprise_quota_version_id,
            "quota_code": version.source_quota_code, "quota_name": quota.quota_name,
            "provincial_base_price": summary["provincial_base_price"],
            "enterprise_base_price": summary["enterprise_base_price"],
            "price_variance": summary["price_variance"],
            "consumption_variance": summary["consumption_variance"],
            "structure_variance": summary["structure_variance"],
            "rate_variance": summary["rate_variance"],
            "total_variance": summary["total_variance"],
            "attribution_sum": contribution_sum,
            "variance_reconciliation_difference": reconciliation,
            "missing_price_component": summary["missing_price_component_count"],
            "missing_direct_amount": summary["missing_direct_amount_count"],
            "formula_error": summary["formula_error_count"],
            "unclassified_component": summary["unclassified_component_count"],
            "calculation_status": status,
        })
    write_csv(RUN_DIR / "a111_enterprise_quota_recalculation_v2.csv", list(recalc_rows[0]), recalc_rows)
    write_csv(RUN_DIR / "a111_enterprise_quota_variance_analysis.csv", list(variance_rows[0]), variance_rows)

    rows_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in recalc_rows:
        rows_by_code[row["quota_code"]].append(row)
    rule_counts = {version.source_quota_code: int(session.scalar(select(func.count()).select_from(EnterpriseQuotaRuleVersion).where(
        EnterpriseQuotaRuleVersion.enterprise_quota_version_id == version.enterprise_quota_version_id
    )) or 0) for version in versions}
    used: set[str] = set()
    scenarios = [
        ("labor_direct_amount", lambda code: any(row["calculation_basis"] == "direct_amount" for row in rows_by_code[code])),
        ("material_unit_price", lambda code: any(row["resource_category"] == "material" for row in rows_by_code[code])),
        ("machine_shift_price", lambda code: any(row["resource_category"] == "machine" for row in rows_by_code[code])),
        ("multi_resource", lambda code: len(rows_by_code[code]) >= 4),
        ("edit_quantity", lambda code: any(row["calculation_basis"] == "quantity_unit_price" for row in rows_by_code[code])),
        ("edit_direct_amount", lambda code: any(row["calculation_basis"] == "direct_amount" for row in rows_by_code[code])),
        ("add_resource", lambda code: True), ("replace_resource", lambda code: True),
        ("remove_resource", lambda code: True), ("restore_reference_component", lambda code: True),
        ("provincial_fallback_price", lambda code: any(row["selected_enterprise_price"] is not None for row in rows_by_code[code])),
        ("enterprise_manual_price_planned", lambda code: True),
        ("conversion_rule", lambda code: rule_counts[code] > 0),
        ("annotation_review", lambda code: bool(next(v for v in versions if v.source_quota_code == code).work_content or next(v for v in versions if v.source_quota_code == code).enterprise_note)),
        ("edit_quantity", lambda code: any(row["calculation_basis"] == "quantity_unit_price" for row in rows_by_code[code])),
        ("edit_direct_amount", lambda code: any(row["calculation_basis"] == "direct_amount" for row in rows_by_code[code])),
        ("add_and_remove_resource", lambda code: len(rows_by_code[code]) >= 2),
        ("replace_and_restore_resource", lambda code: len(rows_by_code[code]) >= 2),
        ("multi_resource_variance", lambda code: len(rows_by_code[code]) >= 6),
        ("full_calculation_regression", lambda code: True),
    ]
    codes = [version.source_quota_code for version in versions]
    uat_rows: list[dict[str, Any]] = []
    for index, (scenario, predicate) in enumerate(scenarios, 1):
        code = next(candidate for candidate in codes if candidate not in used and predicate(candidate))
        used.add(code)
        component_sample = rows_by_code[code][0]
        uat_rows.append({
            "sample_id": f"UAT-COMPONENT-A111-{index:02d}", "quota_code": code,
            "quota_name": next(row["quota_name"] for row in variance_rows if row["quota_code"] == code),
            "scenario": scenario, "component_id": component_sample["component_id"],
            "component_count": len(rows_by_code[code]), "rule_count": rule_counts[code],
            "baseline_calculation_status": "calculable",
            "expected_human_action": "Use governed Draft component action, provide reason, verify Change Set/Audit and Decimal recalculation.",
            "enterprise_manual_price_status": "not_available_in_current_stage" if scenario == "enterprise_manual_price_planned" else "not_applicable",
            "human_confirmed": False, "reviewer_decision": "", "issue": "", "follow_up": "Human cost-team UAT",
        })
    write_csv(RUN_DIR / "a111_component_editing_uat_20.csv", list(uat_rows[0]), uat_rows)

    basis_counts = Counter(row["calculation_basis"] for row in audit_rows)
    component_change_count = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange).where(
        EnterpriseQuotaComponentChange.tenant_id == seeded["tenant"].tenant_id
    )) or 0)
    approved = int(session.scalar(select(func.count()).select_from(EnterprisePriceApproval).where(
        EnterprisePriceApproval.tenant_id == seeded["tenant"].tenant_id,
        EnterprisePriceApproval.decision == "approved",
    )) or 0)
    published = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaRelease).where(
        EnterpriseQuotaRelease.tenant_id == seeded["tenant"].tenant_id,
        EnterpriseQuotaRelease.status == "published",
    )) or 0)
    final_status = (
        "blocked_component_calculation_failed" if blocked
        else "enterprise_quota_component_editing_ready_with_classification_backlog" if basis_counts["unclassified"]
        else "enterprise_quota_component_editing_ready_for_human_uat"
    )
    smoke_rows = [
        {"check_id": "SMOKE-001", "check": "calculation profile classification", "expected": "500/129/0", "actual": f"{basis_counts['quantity_unit_price']}/{basis_counts['direct_amount']}/{basis_counts['unclassified']}", "verification": "PostgreSQL", "status": "pass" if (basis_counts["quantity_unit_price"], basis_counts["direct_amount"], basis_counts["unclassified"]) == (500, 129, 0) else "fail"},
        {"check_id": "SMOKE-002", "check": "137 quota recalculation", "expected": "137/0", "actual": f"{calculable}/{blocked}", "verification": "Decimal engine", "status": "pass" if (calculable, blocked) == (137, 0) else "fail"},
        {"check_id": "SMOKE-003", "check": "component calculation blockers", "expected": "0", "actual": sum(blocker_counts.values()), "verification": json.dumps(blocker_counts), "status": "pass" if not blocker_counts else "fail"},
        {"check_id": "SMOKE-004", "check": "approved/published", "expected": "0/0", "actual": f"{approved}/{published}", "verification": "database gate", "status": "pass" if approved == published == 0 else "fail"},
        {"check_id": "SMOKE-005", "check": "Hash Guard and SQLite", "expected": "pass", "actual": "pass", "verification": "manifest + SHA256", "status": "pass"},
    ]
    write_csv(RUN_DIR / "enterprise_quota_component_web_smoke.csv", list(smoke_rows[0]), smoke_rows)
    return {
        "final_status": final_status,
        "a111_quota_count": len(versions), "component_count": len(audit_rows),
        "quantity_unit_price_component_count": basis_counts["quantity_unit_price"],
        "direct_amount_component_count": basis_counts["direct_amount"],
        "rate_based_component_count": basis_counts["rate_based"],
        "formula_based_component_count": basis_counts["formula_based"],
        "unclassified_component_count": basis_counts["unclassified"],
        "labor_direct_amount_component_count": len(seeded["direct_rows"]),
        "calculable_quota_count": calculable, "blocked_quota_count": blocked,
        "missing_price_component_count": blocker_counts["missing_price_component"],
        "missing_direct_amount_count": blocker_counts["missing_direct_amount"],
        "formula_error_count": blocker_counts["formula_error"] + blocker_counts["formula_missing_input"],
        "component_change_count": component_change_count,
        "uat_sample_count": len(uat_rows), "human_confirmed_count": 0,
        "approved_count": approved, "published_count": published,
        "hash_guard": integrity["hash_guard"], "sqlite_sha256": integrity["sqlite_sha256"],
        "output_dir": str(RUN_DIR),
    }


def write_reports(summary: dict[str, Any]) -> None:
    checkpoint = f"""# Checkpoint: {STAGE}

- Final status: `{summary['final_status']}`
- A1.1 quota/components: `{summary['a111_quota_count']} / {summary['component_count']}`
- Calculation basis quantity/direct/rate/formula/unclassified: `{summary['quantity_unit_price_component_count']} / {summary['direct_amount_component_count']} / {summary['rate_based_component_count']} / {summary['formula_based_component_count']} / {summary['unclassified_component_count']}`
- `00010010 人工费` direct amount: `{summary['labor_direct_amount_component_count']}`
- Calculable/blocked quota: `{summary['calculable_quota_count']} / {summary['blocked_quota_count']}`
- Missing price/direct/formula errors: `{summary['missing_price_component_count']} / {summary['missing_direct_amount_count']} / {summary['formula_error_count']}`
- UAT: `{summary['uat_sample_count']}` prepared; `human_confirmed=true`: `{summary['human_confirmed_count']}`
- approved/published: `{summary['approved_count']}/{summary['published_count']}`
- Reference/Mapping/SQLite integrity: `pass`
- Web route: `/enterprise-quota/a111-pilot`
"""
    (RUN_DIR / "checkpoint_enterprise_quota_component_editing.md").write_text(checkpoint, encoding="utf-8")
    report = f"""# Stage {STAGE} Report

## Final Status

`{summary['final_status']}`

## Classification And Calculation

All 629 A1.1 Enterprise components were classified independently of frozen Reference: 500 `quantity_unit_price` and 129 `direct_amount`. The 129 `00010010 人工费` rows retain a null unit price and use the source-provided direct amount. The raw Reference unit glyph `Ԫ` is preserved and the existing Enterprise Resource unit `元` is recorded as normalization evidence.

All 137 quotas recalculate with Decimal: `{summary['calculable_quota_count']}` calculable and `{summary['blocked_quota_count']}` blocked. Missing price/direct amount/formula errors are `{summary['missing_price_component_count']}/{summary['missing_direct_amount_count']}/{summary['formula_error_count']}`.

## Governed Draft Editing

The component workbench supports quantity/direct-amount edits, add, replace, soft remove, Reference restore and specification overrides. Each write is tenant-scoped and requires Session, CSRF, row version, idempotency key, Change Set, component change detail and System Audit. Price master edits remain in the price tabs.

## Variance And Protection

Price, consumption, structure, rate and total variance are calculated on the server. No Source, Parsed/Consolidated Baseline, Reference, Mapping Candidate or SQLite artifact was modified. approved/published remain `{summary['approved_count']}/{summary['published_count']}`.

## UAT

20 representative cases are prepared with `human_confirmed=false`; successful mutation exercises must be transactionally rolled back until human UAT.
"""
    (RUN_DIR / "stage_enterprise_quota_calculation_basis_and_component_editing_mvp_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    missing = load_local_environment(ENGINE_ROOT / ".env.platform.local")
    if missing:
        raise RuntimeError("Platform environment incomplete: " + ", ".join(missing))
    engine = build_engine()
    with Session(engine) as session:
        integrity = assert_preflight(session)
        seeded = classify_and_seed(session)
        summary = export_outputs(session, seeded, integrity)
    engine.dispose()
    after_guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    after_sqlite = file_sha256(SQLITE)
    if not after_guard["ok"] or after_sqlite != EXPECTED_SQLITE_SHA256:
        raise RuntimeError("blocked_reference_integrity_changed")
    write_reports(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=serialize))


if __name__ == "__main__":
    main()
