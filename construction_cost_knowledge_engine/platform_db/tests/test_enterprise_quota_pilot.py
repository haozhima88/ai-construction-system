from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from platform_db.api import app
from platform_db.models import (
    AppRole,
    AppUser,
    AppUserRoleAssignment,
    EnterpriseQuotaChangeSet,
    EnterpriseQuotaComponentChange,
    EnterpriseQuotaComponentVersion,
    EnterpriseQuotaVersion,
    EnterpriseComponentCalculationProfile,
    EnterprisePriceChangeSet,
    EnterprisePriceSourceDocument,
    EnterprisePriceVersion,
    EnterpriseResource,
    EnterpriseResourceReferenceLink,
    SystemAuditEvent,
)
from platform_db.repositories import (
    EnterpriseQuotaBatchConflict,
    EnterpriseQuotaFieldValidation,
    EnterpriseQuotaRepository,
    EnterpriseQuotaValidation,
)
from platform_db.services.enterprise_quota_pricing import (
    authoritative_amount,
    canonical_snapshot_payload,
    component_amount_by_basis,
    restore_snapshot_payload,
    snapshot_sha256,
    summarize_components,
)


WEB = Path(__file__).resolve().parents[1] / "web"


def test_pilot_01_decimal_amount_is_authoritative():
    assert authoritative_amount("0.1", "0.2") == Decimal("0.020000")
    assert authoritative_amount("2.50000000", "3.333333") == Decimal("8.333333")


def test_pilot_02_missing_price_remains_null():
    assert authoritative_amount("7", None) is None
    summary = summarize_components([{
        "resource_category": "material",
        "source_consumption": "1",
        "consumption": "1",
        "provincial_unit_price": "2",
        "provincial_component_amount": "2",
        "selected_enterprise_price": None,
    }], reference_total_fee="2", management_fee="0")
    assert summary["enterprise_base_price"] is None
    assert summary["difference"] is None
    assert summary["missing_enterprise_price_resource_count"] == 1


def test_pilot_03_snapshot_round_trip_restores_historical_price():
    historical = [{
        "snapshot_line_id": "line-1",
        "enterprise_resource_id": "resource-1",
        "price_value": Decimal("12.345600"),
        "unit": "mock-unit",
        "tax_mode": "excluded",
        "region": "mock-region",
        "mapping_snapshot": {"match_method": "exact_code", "link_id": "link-1"},
        "calculation_rule_version": "enterprise_decimal_v1",
    }, {
        "snapshot_line_id": "line-2",
        "enterprise_resource_id": "resource-2",
        "price_value": None,
        "unit": "mock-unit",
        "tax_mode": "unknown",
        "region": "mock-region",
        "mapping_snapshot": {"match_method": "unmatched", "link_id": None},
        "calculation_rule_version": "enterprise_decimal_v1",
    }]
    payload = canonical_snapshot_payload(historical)
    digest = snapshot_sha256(historical)
    historical[0]["price_value"] = Decimal("99.999999")
    restored = restore_snapshot_payload(payload)
    assert restored[0]["price_value"] == Decimal("12.345600")
    assert restored[1]["price_value"] is None
    assert snapshot_sha256(restored) == digest


def test_pilot_04_model_contains_source_and_independent_link_contracts():
    source_columns = set(EnterprisePriceSourceDocument.__table__.columns.keys())
    assert {
        "source_price_document_id", "file_name", "absolute_path", "sha256", "file_type", "record_count",
        "resource_code_status", "resource_name_status", "specification_status", "unit_status", "price_status",
        "tax_mode_status", "effective_date_status", "region_status", "source_role", "authority_status", "review_status",
    } <= source_columns
    link_columns = set(EnterpriseResourceReferenceLink.__table__.columns.keys())
    assert {
        "link_id", "enterprise_resource_id", "reference_resource_id", "reference_resource_code", "match_method",
        "match_score", "name_match_status", "specification_match_status", "unit_match_status",
        "category_match_status", "review_status", "risk_reason",
    } <= link_columns


def test_pilot_05_authenticated_web_and_api_routes_exist():
    paths = {getattr(route, "path", "") for route in app.router.routes}
    assert "/enterprise-quota" in paths
    assert "/enterprise-quota/a111-pilot" in paths
    assert "/api/v1/enterprise-quota/summary" in paths
    assert "/api/v1/enterprise-quota/tree" in paths
    assert "/api/v1/enterprise-quota/versions/{version_id}" in paths
    assert "/api/v1/enterprise-quota/prices" in paths
    assert "/api/v1/enterprise-quota/prices/resources/{resource_id}/manual" in paths
    assert "/api/v1/enterprise-quota/prices/{price_id}/accept-fallback" in paths
    assert "/api/v1/enterprise-quota/prices/resources/{resource_id}/restore-fallback" in paths
    assert "/api/v1/enterprise-quota/prices/{price_id}/review" in paths
    assert "/api/v1/enterprise-quota/versions/{version_id}/components" in paths
    assert "/api/v1/enterprise-quota/versions/{version_id}/components/batch" in paths
    assert "/api/v1/enterprise-quota/versions/{version_id}/components/{component_id}" in paths
    assert "/api/v1/enterprise-quota/versions/{version_id}/publish" in paths


def test_pilot_06_web_has_all_required_tabs_and_no_browser_price_math():
    markup = (WEB / "enterprise-quota.html").read_text(encoding="utf-8")
    script = (WEB / "static/enterprise-quota.js").read_text(encoding="utf-8")
    for label in (
        "定额组成", "价格对比", "人工核价", "费用汇总", "工作内容", "工程量规则",
        "企业换算规则", "变更记录", "省定额 PDF", "审核记录", "版本历史",
    ):
        assert label in markup
    for label in (
        "资源编码", "资源名称", "资源类别", "计算类型", "企业规格", "省消耗量", "企业消耗量",
        "企业直接金额", "省定额单价", "企业采用价", "省定额合价", "企业合价", "组件状态",
        "增加企业资源", "替换资源", "移除资源", "恢复 Reference", "未保存预览",
    ):
        assert label in script
    assert 'activeTab:"composition"' in script
    assert "class DraftEditBuffer" in script
    assert "/components/batch" in script
    assert "保存修改" in markup and "查看变更" in markup and "退出编辑" in markup
    assert not any(token in script for token in ("prompt(", "confirm(", "alert(", "window.prompt", "window.confirm", "window.alert"))
    css = (WEB / "static/enterprise-quota.css").read_text(encoding="utf-8")
    for state_name in ("readonly", "editable", "focused", "editing", "dirty", "invalid", "conflicted", "saving", "saved"):
        assert state_name in css or state_name in script
    assert "parseFloat" not in script
    assert "selected_enterprise_price *" not in script
    assert "enterprise_component_amount" in script
    assert "内部价格表历史观察值" in script
    assert "接受省定额" in script
    assert "恢复省定额" in script


def test_pilot_07_publish_is_explicitly_disabled_in_pilot_router():
    route = next(route for route in app.router.routes if getattr(route, "path", "") == "/api/v1/enterprise-quota/versions/{version_id}/publish")
    assert "POST" in route.methods
    source = Path(route.endpoint.__code__.co_filename).read_text(encoding="utf-8")
    assert "Formal publication is disabled for the A1.1 pilot" in source


def test_pilot_08_transactional_save_version_diff_review_and_restore(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        version = session.scalar(select(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
        ).order_by(EnterpriseQuotaVersion.source_quota_code))
        assert version is not None
        editor = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(AppUser.tenant_id == version.tenant_id, AppRole.role_code == "editor")
            .order_by(AppUser.login_name)
        )
        reviewer = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(
                AppUser.tenant_id == version.tenant_id,
                AppRole.role_code == "reviewer",
                AppUser.app_user_id != editor.app_user_id,
            )
            .order_by(AppUser.login_name)
        )
        assert editor is not None and reviewer is not None
        editor_context = SimpleNamespace(tenant_id=version.tenant_id, user=editor)
        reviewer_context = SimpleNamespace(tenant_id=version.tenant_id, user=reviewer)
        repository = EnterpriseQuotaRepository(session, version.tenant_id)
        change_count = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0)
        audit_count = int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0)
        request_id = uuid.uuid4()
        saved = repository.save_draft(version.enterprise_quota_version_id, {
            "row_version": version.row_version,
            "idempotency_key": f"test-save-{uuid.uuid4()}",
            "change_type": "edit_enterprise_note",
            "change_reason": "transactional test only",
            "changes": {"enterprise_note": "mock transaction note"},
        }, editor_context, request_id)
        assert saved["status"] == "draft"
        assert int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0) == change_count + 1
        assert int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0) == audit_count + 1

        session.expire_all()
        version = session.get(EnterpriseQuotaVersion, version.enterprise_quota_version_id)
        cloned = repository.save_as_new(version.enterprise_quota_version_id, {
            "row_version": version.row_version,
            "idempotency_key": f"test-clone-{uuid.uuid4()}",
            "change_type": "save_as_new_version",
            "change_reason": "transactional clone test only",
            "changes": {"work_content": "mock changed work content"},
        }, editor_context, uuid.uuid4())
        clone_id = uuid.UUID(cloned["enterprise_quota_version_id"])
        difference = repository.diff(version.enterprise_quota_version_id, clone_id)
        assert any(item["field"] == "work_content" for item in difference["field_changes"])

        session.expire_all()
        clone = session.get(EnterpriseQuotaVersion, clone_id)
        repository.transition(
            clone_id, expected=("draft",), target="submitted", row_version=clone.row_version,
            comment="mock submit", idempotency_key=f"test-submit-{uuid.uuid4()}",
            context=editor_context, request_id=uuid.uuid4(),
        )
        session.expire_all()
        clone = session.get(EnterpriseQuotaVersion, clone_id)
        repository.transition(
            clone_id, expected=("submitted",), target="reviewed", row_version=clone.row_version,
            comment="mock review", idempotency_key=f"test-review-{uuid.uuid4()}",
            context=reviewer_context, request_id=uuid.uuid4(),
        )
        session.expire_all()
        clone = session.get(EnterpriseQuotaVersion, clone_id)
        with pytest.raises(EnterpriseQuotaValidation, match="prices must be complete|authority is not confirmed"):
            repository.transition(
                clone_id, expected=("reviewed",), target="approved", row_version=clone.row_version,
                comment="must fail", idempotency_key=f"test-approve-{uuid.uuid4()}",
                context=editor_context, request_id=uuid.uuid4(),
            )
        restored = repository.restore(
            clone_id, row_version=clone.row_version, change_reason="transactional restore test only",
            idempotency_key=f"test-restore-{uuid.uuid4()}", context=editor_context, request_id=uuid.uuid4(),
        )
        assert restored["status"] == "draft"
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_pilot_09_fallback_model_and_stage_counts(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine) as session:
        tenant_id = session.scalar(select(EnterpriseQuotaVersion.tenant_id).where(
            EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
        ))
        assert tenant_id is not None
        repository = EnterpriseQuotaRepository(session, tenant_id)
        summary = repository.summary()
        assert summary["final_status"] == "enterprise_quota_component_editing_ready_for_human_uat"
        assert summary["a111_reference_quota_count"] == 137
        assert summary["enterprise_resource_count"] == 55
        assert summary["provincial_fallback_price_count"] == 54
        assert summary["missing_enterprise_price_resource_count"] == 1
        assert summary["calculation_price_coverage"] == "54/55"
        assert summary["enterprise_confirmed_price_coverage"] == "0/55"
        assert summary["quantity_unit_price_component_count"] == 500
        assert summary["direct_amount_component_count"] == 129
        assert summary["rate_based_component_count"] == 0
        assert summary["formula_based_component_count"] == 0
        assert summary["unclassified_component_count"] == 0
        assert summary["calculable_enterprise_quota_count"] == 137
        assert summary["blocked_enterprise_quota_count"] == 0
        assert summary["enterprise_quota_calculation_coverage"] == "137/137"
        assert summary["approved_count"] == 0
        assert summary["published_count"] == 0
        prices = repository.price_workbench()
        assert prices["total"] == 55
        assert sum(row["selected_price"] is not None for row in prices["items"]) == 54
        missing = [row for row in prices["items"] if row["selected_price"] is None]
        assert [(row["resource_code"], row["resource_name"], row["unit"]) for row in missing] == [
            ("00010010", "人工费", "元")
        ]
        assert all(row["enterprise_confirmed"] is False for row in prices["items"])
    engine.dispose()


def test_pilot_11_component_calculation_basis_contracts():
    assert component_amount_by_basis({
        "calculation_basis": "quantity_unit_price", "consumption": "2.5", "selected_enterprise_price": "3.2",
    }) == (Decimal("8.000000"), None)
    assert component_amount_by_basis({
        "calculation_basis": "direct_amount", "enterprise_direct_amount": "13.8",
    }) == (Decimal("13.800000"), None)
    assert component_amount_by_basis({
        "calculation_basis": "rate_based", "calculation_base": "100", "enterprise_rate": "0.08",
    }) == (Decimal("8.000000"), None)
    assert component_amount_by_basis({
        "calculation_basis": "formula_based", "formula_code": "base_times_rate", "formula_version": "v1",
        "calculation_base": "120", "enterprise_rate": "0.05",
    }) == (Decimal("6.000000"), None)
    assert component_amount_by_basis({
        "calculation_basis": "direct_amount", "enterprise_direct_amount": None,
    }) == (None, "missing_direct_amount")
    assert component_amount_by_basis({
        "lifecycle_status": "removed", "calculation_basis": "quantity_unit_price",
        "consumption": None, "selected_enterprise_price": None,
    }) == (Decimal("0.000000"), None)


def test_pilot_12_component_profile_and_change_models_are_governed():
    profile_columns = set(EnterpriseComponentCalculationProfile.__table__.columns.keys())
    assert {
        "profile_id", "tenant_id", "reference_resource_id", "resource_code", "resource_name", "unit",
        "calculation_basis", "classification_reason", "source_evidence", "review_status", "created_at",
        "created_by", "row_version",
    } <= profile_columns
    component_columns = set(EnterpriseQuotaComponentVersion.__table__.columns.keys())
    assert {
        "source_enterprise_resource_id", "calculation_basis", "source_direct_amount",
        "enterprise_direct_amount", "calculation_base", "enterprise_rate", "formula_code", "formula_version",
        "component_status", "lifecycle_status", "specification_override", "row_version",
    } <= component_columns
    change_columns = set(EnterpriseQuotaComponentChange.__table__.columns.keys())
    assert {
        "quota_version_id", "component_id", "change_type", "field_name", "before_value", "after_value",
        "change_reason", "changed_by", "changed_at", "request_id", "idempotency_key", "row_version",
    } <= change_columns


def test_pilot_13_transactional_component_editing_change_set_audit_and_soft_delete(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        version = session.scalar(select(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.source_quota_code == "A1-1-1"
        ))
        assert version is not None
        editor = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(AppUser.tenant_id == version.tenant_id, AppRole.role_code == "editor")
            .order_by(AppUser.login_name)
        )
        reviewer = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(
                AppUser.tenant_id == version.tenant_id,
                AppRole.role_code == "reviewer",
                AppUser.app_user_id != editor.app_user_id,
            )
            .order_by(AppUser.login_name)
        )
        assert editor is not None and reviewer is not None
        editor_context = SimpleNamespace(tenant_id=version.tenant_id, user=editor)
        reviewer_context = SimpleNamespace(tenant_id=version.tenant_id, user=reviewer)
        repository = EnterpriseQuotaRepository(session, version.tenant_id)
        direct = session.scalar(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
            EnterpriseQuotaComponentVersion.calculation_basis == "direct_amount",
        ))
        quantity = session.scalar(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
            EnterpriseQuotaComponentVersion.calculation_basis == "quantity_unit_price",
        ).order_by(EnterpriseQuotaComponentVersion.line_no))
        replacement = session.scalar(
            select(EnterpriseResource)
            .join(EnterprisePriceVersion, EnterprisePriceVersion.enterprise_resource_id == EnterpriseResource.enterprise_resource_id)
            .where(
                EnterpriseResource.tenant_id == version.tenant_id,
                EnterpriseResource.enterprise_resource_id != quantity.enterprise_resource_id,
                EnterprisePriceVersion.price_source_type == "provincial_reference_fallback",
            )
            .order_by(EnterpriseResource.resource_code)
        )
        assert direct is not None and quantity is not None and replacement is not None
        baseline_components = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id
        )) or 0)
        baseline_changes = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange)) or 0)
        baseline_sets = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0)
        baseline_audit = int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0)

        add_key = f"test-component-add-{uuid.uuid4()}"
        added = repository.add_component(version.enterprise_quota_version_id, {
            "row_version": version.row_version,
            "idempotency_key": add_key,
            "change_reason": "transactional add component UAT",
            "enterprise_resource_id": replacement.enterprise_resource_id,
            "calculation_basis": "quantity_unit_price",
            "enterprise_quantity": "0.125",
            "specification": "transaction-only specification",
        }, editor_context, uuid.uuid4())
        assert added["component"]["component_status"] == "resource_added"
        assert added["component"]["enterprise_component_amount"] is not None
        replay = repository.add_component(version.enterprise_quota_version_id, {
            "row_version": version.row_version,
            "idempotency_key": add_key,
            "change_reason": "ignored idempotent replay",
            "enterprise_resource_id": replacement.enterprise_resource_id,
            "calculation_basis": "quantity_unit_price",
            "enterprise_quantity": "999",
        }, editor_context, uuid.uuid4())
        assert replay["status"] == "idempotent"

        session.refresh(quantity)
        quantity_result = repository.mutate_component(version.enterprise_quota_version_id, quantity.enterprise_quota_component_version_id, {
            "row_version": quantity.row_version, "idempotency_key": f"test-component-quantity-{uuid.uuid4()}",
            "change_reason": "transactional quantity UAT", "action": "edit_quantity",
            "enterprise_quantity": str(Decimal(quantity.consumption) + Decimal("0.1")),
        }, editor_context, uuid.uuid4())
        assert quantity_result["component"]["component_status"] == "quantity_modified"
        assert Decimal(quantity_result["component"]["enterprise_component_amount"]) == (
            Decimal(quantity_result["component"]["consumption"])
            * Decimal(quantity_result["component"]["selected_enterprise_price"])
        ).quantize(Decimal("0.000001"))

        session.refresh(direct)
        direct_result = repository.mutate_component(version.enterprise_quota_version_id, direct.enterprise_quota_component_version_id, {
            "row_version": direct.row_version, "idempotency_key": f"test-component-direct-{uuid.uuid4()}",
            "change_reason": "transactional direct amount UAT", "action": "edit_direct_amount",
            "enterprise_direct_amount": str(Decimal(direct.enterprise_direct_amount) + Decimal("1")),
        }, editor_context, uuid.uuid4())
        assert direct_result["component"]["component_status"] == "amount_modified"
        assert direct_result["component"]["selected_enterprise_price"] is None
        assert direct_result["component"]["enterprise_component_amount"] == direct_result["component"]["enterprise_direct_amount"]

        session.refresh(quantity)
        replaced = repository.mutate_component(version.enterprise_quota_version_id, quantity.enterprise_quota_component_version_id, {
            "row_version": quantity.row_version, "idempotency_key": f"test-component-replace-{uuid.uuid4()}",
            "change_reason": "transactional replace resource UAT", "action": "replace_resource",
            "enterprise_resource_id": replacement.enterprise_resource_id, "calculation_basis": "quantity_unit_price",
            "enterprise_quantity": "0.250", "specification": "replacement UAT",
        }, editor_context, uuid.uuid4())
        assert replaced["component"]["component_status"] == "resource_replaced"
        assert replaced["component"]["enterprise_resource_id"] == str(replacement.enterprise_resource_id)

        session.refresh(quantity)
        removed = repository.mutate_component(version.enterprise_quota_version_id, quantity.enterprise_quota_component_version_id, {
            "row_version": quantity.row_version, "idempotency_key": f"test-component-remove-{uuid.uuid4()}",
            "change_reason": "transactional soft delete UAT", "action": "remove_resource",
        }, editor_context, uuid.uuid4())
        assert removed["component"]["lifecycle_status"] == "removed"
        assert removed["component"]["enterprise_component_amount"] == "0.000000"
        assert int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id
        )) or 0) == baseline_components + 1

        session.refresh(quantity)
        restored = repository.mutate_component(version.enterprise_quota_version_id, quantity.enterprise_quota_component_version_id, {
            "row_version": quantity.row_version, "idempotency_key": f"test-component-restore-{uuid.uuid4()}",
            "change_reason": "transactional restore Reference UAT", "action": "restore_reference",
        }, editor_context, uuid.uuid4())
        assert restored["component"]["component_status"] == "restored"
        assert restored["component"]["lifecycle_status"] == "active"
        assert restored["component"]["enterprise_resource_id"] == restored["component"]["source_enterprise_resource_id"]

        session.refresh(quantity)
        specification = repository.mutate_component(version.enterprise_quota_version_id, quantity.enterprise_quota_component_version_id, {
            "row_version": quantity.row_version, "idempotency_key": f"test-component-spec-{uuid.uuid4()}",
            "change_reason": "transactional specification UAT", "action": "edit_specification",
            "specification": "enterprise specification override UAT",
        }, editor_context, uuid.uuid4())
        assert specification["component"]["specification_override"] == "enterprise specification override UAT"

        assert int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange)) or 0) == baseline_changes + 7
        assert int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0) == baseline_sets + 7
        assert int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0) == baseline_audit + 7
        session.refresh(version)
        repository.transition(
            version.enterprise_quota_version_id, expected=("draft",), target="submitted", row_version=version.row_version,
            comment="transactional submit for reviewer guard", idempotency_key=f"test-component-submit-{uuid.uuid4()}",
            context=editor_context, request_id=uuid.uuid4(),
        )
        session.refresh(version)
        with pytest.raises(EnterpriseQuotaValidation, match="cannot review"):
            repository.transition(
                version.enterprise_quota_version_id, expected=("submitted",), target="reviewed", row_version=version.row_version,
                comment="self review must fail", idempotency_key=f"test-component-self-review-{uuid.uuid4()}",
                context=editor_context, request_id=uuid.uuid4(),
            )
        reviewed = repository.transition(
            version.enterprise_quota_version_id, expected=("submitted",), target="reviewed", row_version=version.row_version,
            comment="independent reviewer UAT", idempotency_key=f"test-component-review-{uuid.uuid4()}",
            context=reviewer_context, request_id=uuid.uuid4(),
        )
        assert reviewed["status"] == "reviewed"
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_pilot_14_transactional_spreadsheet_batch_is_atomic_and_audited(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        versions = list(session.scalars(select(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
        ).order_by(EnterpriseQuotaVersion.source_quota_code)))
        version = next(item for item in versions if (
            session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentVersion).where(
                EnterpriseQuotaComponentVersion.enterprise_quota_version_id == item.enterprise_quota_version_id,
                EnterpriseQuotaComponentVersion.calculation_basis == "quantity_unit_price",
            )) or 0
        ) >= 2)
        editor = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(AppUser.tenant_id == version.tenant_id, AppRole.role_code == "editor")
            .order_by(AppUser.login_name)
        )
        context = SimpleNamespace(tenant_id=version.tenant_id, user=editor)
        repository = EnterpriseQuotaRepository(session, version.tenant_id)
        quantity_rows = list(session.scalars(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
            EnterpriseQuotaComponentVersion.calculation_basis == "quantity_unit_price",
        ).order_by(EnterpriseQuotaComponentVersion.line_no).limit(2)))
        direct = session.scalar(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
            EnterpriseQuotaComponentVersion.calculation_basis == "direct_amount",
        ))
        replacement = session.scalar(
            select(EnterpriseResource)
            .join(EnterprisePriceVersion, EnterprisePriceVersion.enterprise_resource_id == EnterpriseResource.enterprise_resource_id)
            .where(
                EnterpriseResource.tenant_id == version.tenant_id,
                EnterprisePriceVersion.price_source_type == "provincial_reference_fallback",
            )
            .order_by(EnterpriseResource.resource_code)
        )
        assert len(quantity_rows) == 2 and direct is not None and replacement is not None
        baseline_sets = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0)
        baseline_details = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange)) or 0)
        baseline_audit = int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0)
        key = f"test-spreadsheet-batch-{uuid.uuid4()}"
        changes = [
            {
                "component_id": row.enterprise_quota_component_version_id,
                "field_name": "enterprise_quantity", "before_value": str(row.consumption),
                "after_value": str(Decimal(row.consumption) + Decimal("0.01")),
                "change_type": "quantity_modified", "reason": "multi-row spreadsheet quantity UAT",
            }
            for row in quantity_rows
        ] + [{
            "component_id": direct.enterprise_quota_component_version_id,
            "field_name": "enterprise_direct_amount", "before_value": str(direct.enterprise_direct_amount),
            "after_value": str(Decimal(direct.enterprise_direct_amount) + Decimal("1")),
            "change_type": "amount_modified", "reason": "spreadsheet direct amount UAT",
        }, {
            "component_id": quantity_rows[0].enterprise_quota_component_version_id,
            "field_name": "enterprise_specification", "before_value": None,
            "after_value": "spreadsheet specification UAT", "change_type": "specification_modified",
            "reason": "spreadsheet specification UAT",
        }, {
            "component_id": quantity_rows[1].enterprise_quota_component_version_id,
            "field_name": "lifecycle_status", "before_value": "active", "after_value": "removed",
            "change_type": "resource_removed", "reason": "spreadsheet pending remove UAT",
        }, {
            "component_id": None, "client_component_id": f"local-{uuid.uuid4()}", "field_name": "component",
            "before_value": None, "after_value": {
                "enterprise_resource_id": str(replacement.enterprise_resource_id),
                "calculation_basis": "quantity_unit_price", "enterprise_quantity": "0.125",
                "enterprise_specification": "batch added resource UAT",
            }, "change_type": "resource_added", "reason": "spreadsheet drawer add UAT",
        }]
        result = repository.batch_mutate_components(version.enterprise_quota_version_id, {
            "base_row_version": version.row_version, "changes": changes,
            "change_reason": "spreadsheet batch transaction UAT", "idempotency_key": key,
            "save_as_new": False,
        }, context, uuid.uuid4())
        assert result["status"] == "draft" and result["saved_change_count"] == 6
        assert result["detail"]["cost_summary"]["calculation_status"].startswith("complete")
        assert int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0) == baseline_sets + 1
        assert int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange)) or 0) == baseline_details + 6
        assert int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0) == baseline_audit + 1
        replay = repository.batch_mutate_components(version.enterprise_quota_version_id, {
            "base_row_version": version.row_version, "changes": changes,
            "change_reason": "ignored replay", "idempotency_key": key, "save_as_new": False,
        }, context, uuid.uuid4())
        assert replay["status"] == "idempotent"

        session.refresh(version)
        with pytest.raises(EnterpriseQuotaBatchConflict) as conflict:
            repository.batch_mutate_components(version.enterprise_quota_version_id, {
                "base_row_version": 999999, "changes": changes[:1], "change_reason": "stale conflict UAT",
                "idempotency_key": f"test-stale-{uuid.uuid4()}", "save_as_new": False,
            }, context, uuid.uuid4())
        assert conflict.value.current_row_version == version.row_version

        original_quantity = str(quantity_rows[0].consumption)
        nested = session.begin_nested()
        try:
            with pytest.raises(EnterpriseQuotaFieldValidation) as invalid:
                repository.batch_mutate_components(version.enterprise_quota_version_id, {
                    "base_row_version": version.row_version,
                    "changes": [{
                        "component_id": quantity_rows[0].enterprise_quota_component_version_id,
                        "field_name": "enterprise_quantity", "before_value": original_quantity,
                        "after_value": "1.123456789", "change_type": "quantity_modified",
                        "reason": "must rollback invalid scale",
                    }],
                    "change_reason": "invalid transaction rollback UAT",
                    "idempotency_key": f"test-invalid-{uuid.uuid4()}", "save_as_new": False,
                }, context, uuid.uuid4())
            assert invalid.value.field_errors[0]["field_name"] == "enterprise_quantity"
        finally:
            nested.rollback()
        session.expire_all()
        assert str(session.get(EnterpriseQuotaComponentVersion, quantity_rows[0].enterprise_quota_component_version_id).consumption) == original_quantity
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_pilot_10_transactional_manual_review_restore_and_audit(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        tenant_id = session.scalar(select(EnterpriseQuotaVersion.tenant_id).where(
            EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
        ))
        editor = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(AppUser.tenant_id == tenant_id, AppRole.role_code == "editor")
            .order_by(AppUser.login_name)
        )
        reviewer = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(
                AppUser.tenant_id == tenant_id,
                AppRole.role_code == "reviewer",
                AppUser.app_user_id != editor.app_user_id,
            )
            .order_by(AppUser.login_name)
        )
        assert editor is not None and reviewer is not None and editor.app_user_id != reviewer.app_user_id
        editor_context = SimpleNamespace(tenant_id=tenant_id, user=editor)
        reviewer_context = SimpleNamespace(tenant_id=tenant_id, user=reviewer)
        repository = EnterpriseQuotaRepository(session, tenant_id)
        resource = session.scalar(
            select(EnterpriseResource)
            .join(EnterprisePriceVersion, EnterprisePriceVersion.enterprise_resource_id == EnterpriseResource.enterprise_resource_id)
            .where(
                EnterpriseResource.tenant_id == tenant_id,
                EnterprisePriceVersion.price_source_type == "provincial_reference_fallback",
            )
            .order_by(EnterpriseResource.resource_code)
        )
        fallback = session.scalar(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == tenant_id,
            EnterprisePriceVersion.enterprise_resource_id == resource.enterprise_resource_id,
            EnterprisePriceVersion.version_no == 1,
        ))
        original_fallback_value = fallback.price_value
        change_count = int(session.scalar(select(func.count()).select_from(EnterprisePriceChangeSet)) or 0)
        audit_count = int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0)
        manual_key = f"test-price-manual-{uuid.uuid4()}"
        manual = repository.create_manual_price(resource.enterprise_resource_id, {
            "row_version": fallback.row_version,
            "idempotency_key": manual_key,
            "price_value": str(original_fallback_value + Decimal("1.250000")),
            "tax_mode": "test_tax_mode",
            "region": "广东省",
            "effective_from": "2026-07-14T00:00:00+08:00",
            "change_reason": "transactional manual price test",
        }, editor_context, uuid.uuid4())
        manual_row = session.get(EnterprisePriceVersion, uuid.UUID(manual["price"]["enterprise_price_version_id"]))
        assert manual_row.version_no == 2
        assert manual_row.price_source_type == "enterprise_manual_price"
        assert manual_row.is_fallback is False
        assert fallback.price_value == original_fallback_value
        assert int(session.scalar(select(func.count()).select_from(EnterprisePriceChangeSet)) or 0) == change_count + 1
        assert int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0) == audit_count + 1
        replay = repository.create_manual_price(resource.enterprise_resource_id, {
            "row_version": fallback.row_version,
            "idempotency_key": manual_key,
            "price_value": "999999",
            "tax_mode": "ignored",
            "region": "ignored",
            "effective_from": "2026-07-14T00:00:00+08:00",
            "change_reason": "idempotent replay",
        }, editor_context, uuid.uuid4())
        assert replay["status"] == "idempotent"
        with pytest.raises(EnterpriseQuotaValidation, match="cannot review"):
            repository.review_price(manual_row.enterprise_price_version_id, {
                "row_version": manual_row.row_version,
                "idempotency_key": f"test-self-review-{uuid.uuid4()}",
                "change_reason": "must fail",
                "action": "review",
            }, editor_context, uuid.uuid4())
        reviewed = repository.review_price(manual_row.enterprise_price_version_id, {
            "row_version": manual_row.row_version,
            "idempotency_key": f"test-review-price-{uuid.uuid4()}",
            "change_reason": "transactional reviewer test",
            "action": "review",
        }, reviewer_context, uuid.uuid4())
        assert reviewed["price"]["pricing_review_status"] == "manual_price_reviewed"
        assert reviewed["price"]["requires_manual_review"] is False
        session.refresh(manual_row)
        restored = repository.restore_fallback(resource.enterprise_resource_id, {
            "row_version": manual_row.row_version,
            "idempotency_key": f"test-restore-price-{uuid.uuid4()}",
            "change_reason": "transactional fallback restore",
        }, editor_context, uuid.uuid4())
        restored_row = session.get(EnterprisePriceVersion, uuid.UUID(restored["price"]["enterprise_price_version_id"]))
        assert restored_row.version_no == 3
        assert restored_row.price_source_type == "provincial_reference_fallback"
        selected = next(row for row in repository.price_workbench()["items"] if row["enterprise_resource_id"] == str(resource.enterprise_resource_id))
        assert selected["selected_price_version_id"] == str(restored_row.enterprise_price_version_id)
        assert len(selected["version_history"]) == 3
        accepted = repository.accept_fallback(restored_row.enterprise_price_version_id, {
            "row_version": restored_row.row_version,
            "idempotency_key": f"test-accept-price-{uuid.uuid4()}",
            "change_reason": "transactional fallback acceptance",
        }, editor_context, uuid.uuid4())
        assert accepted["price"]["price_source_type"] == "provincial_reference_fallback"
        assert accepted["price"]["pricing_review_status"] == "reviewed_fallback_accepted"
        assert accepted["price"]["requires_manual_review"] is False
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
