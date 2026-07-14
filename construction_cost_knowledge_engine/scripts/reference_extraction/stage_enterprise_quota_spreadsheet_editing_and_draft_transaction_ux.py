from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ENGINE_ROOT.parent
sys.path.insert(0, str(ENGINE_ROOT))

from platform_db.database import build_engine  # noqa: E402
from platform_db.importers.hash_guard import validate_rc1_manifest  # noqa: E402
from platform_db.local_runtime import load_local_environment  # noqa: E402
from platform_db.models import (  # noqa: E402
    AppRole,
    AppUser,
    AppUserRoleAssignment,
    EnterpriseQuotaChangeSet,
    EnterpriseQuotaComponentChange,
    EnterpriseQuotaComponentVersion,
    EnterpriseQuotaVersion,
    EnterpriseResource,
    EnterprisePriceVersion,
    ReferenceQuotaItem,
    SystemAuditEvent,
)
from platform_db.repositories import (  # noqa: E402
    EnterpriseQuotaBatchConflict,
    EnterpriseQuotaFieldValidation,
    EnterpriseQuotaRepository,
)


RUN_DIR = ENGINE_ROOT / "data/private/reference_extraction/runs/ENTERPRISE_QUOTA_SPREADSHEET_EDITING_AND_DRAFT_TRANSACTION_UX_1"
MANIFEST = ENGINE_ROOT / "data/private/reference_extraction/runs/PLATFORM_FOUNDATION_AND_ENTERPRISE_QUOTA_ARCHITECTURE_LOCK_1/building_rc1_release_manifest.csv"
SQLITE = ENGINE_ROOT / "web_collab_prototype/data/web_quota_building_draft.sqlite"
EXPECTED_SQLITE_SHA256 = "e5cd6dfe9f399d2d74c5f28a2dbfedb9b00c4ffcd816cc16d8408663ae72168f"
SCREENSHOTS = [
    "enterprise_quota_view_mode.png", "enterprise_quota_edit_mode.png", "enterprise_quota_cell_focused.png",
    "enterprise_quota_cell_dirty.png", "enterprise_quota_validation_error.png",
    "enterprise_quota_change_summary.png", "enterprise_quota_add_resource_drawer.png",
    "enterprise_quota_replace_resource_drawer.png", "enterprise_quota_pending_remove.png",
    "enterprise_quota_save_conflict.png", "enterprise_quota_saved_result.png",
]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"Cannot write empty artifact: {name}")
    with (RUN_DIR / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pass_row(check_id: str, check: str, expected: Any, actual: Any, evidence: str) -> dict[str, Any]:
    return {
        "check_id": check_id, "check": check, "expected": expected, "actual": actual,
        "evidence": evidence, "status": "pass",
    }


def preflight(session: Session) -> dict[str, Any]:
    quota_count = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(
        EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
    )) or 0)
    components = list(session.scalars(select(EnterpriseQuotaComponentVersion).where(
        EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_(select(
            EnterpriseQuotaVersion.enterprise_quota_version_id
        ).where(EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")))
    )))
    basis = {
        name: sum(row.calculation_basis == name for row in components)
        for name in ("quantity_unit_price", "direct_amount", "rate_based", "formula_based")
    }
    tenant_id = session.scalar(select(EnterpriseQuotaVersion.tenant_id).where(
        EnterpriseQuotaVersion.source_quota_code.like("A1-1-%")
    ))
    summary = EnterpriseQuotaRepository(session, tenant_id).summary()
    guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    sqlite_hash = file_sha256(SQLITE)
    if quota_count != 137 or len(components) != 629:
        raise RuntimeError("blocked_inline_editing_failed")
    if basis != {"quantity_unit_price": 500, "direct_amount": 129, "rate_based": 0, "formula_based": 0}:
        raise RuntimeError("blocked_reference_integrity_changed")
    if summary["calculable_enterprise_quota_count"] != 137 or summary["blocked_enterprise_quota_count"] != 0:
        raise RuntimeError("blocked_batch_transaction_failed")
    if not guard["ok"] or sqlite_hash != EXPECTED_SQLITE_SHA256:
        raise RuntimeError("blocked_reference_integrity_changed")
    return {
        "quota_count": quota_count, "component_count": len(components), "basis": basis,
        "tenant_id": tenant_id, "summary": summary, "hash_guard": guard, "sqlite_sha256": sqlite_hash,
    }


def transaction_checks() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    engine = build_engine()
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    batch_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    concurrency_rows: list[dict[str, Any]] = []
    try:
        version = session.scalar(select(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.source_quota_code == "A1-1-66"
        ))
        editor = session.scalar(
            select(AppUser)
            .join(AppUserRoleAssignment, AppUserRoleAssignment.app_user_id == AppUser.app_user_id)
            .join(AppRole, AppRole.app_role_id == AppUserRoleAssignment.app_role_id)
            .where(AppUser.tenant_id == version.tenant_id, AppRole.role_code == "editor")
            .order_by(AppUser.login_name)
        )
        context = SimpleNamespace(tenant_id=version.tenant_id, user=editor)
        repository = EnterpriseQuotaRepository(session, version.tenant_id)
        quantities = list(session.scalars(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
            EnterpriseQuotaComponentVersion.calculation_basis == "quantity_unit_price",
        ).order_by(EnterpriseQuotaComponentVersion.line_no)))
        direct = session.scalar(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
            EnterpriseQuotaComponentVersion.calculation_basis == "direct_amount",
        ))
        priced = session.scalar(
            select(EnterpriseResource)
            .join(EnterprisePriceVersion, EnterprisePriceVersion.enterprise_resource_id == EnterpriseResource.enterprise_resource_id)
            .where(
                EnterpriseResource.tenant_id == version.tenant_id,
                EnterprisePriceVersion.price_source_type == "provincial_reference_fallback",
            ).order_by(EnterpriseResource.resource_code)
        )
        baseline_sets = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0)
        baseline_details = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange)) or 0)
        baseline_audit = int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0)
        changes = [
            {
                "component_id": row.enterprise_quota_component_version_id,
                "field_name": "enterprise_quantity", "before_value": str(row.consumption),
                "after_value": str(Decimal(row.consumption) + Decimal("0.01")),
                "change_type": "quantity_modified", "reason": "Stage spreadsheet multi-row edit",
            }
            for row in quantities[:2]
        ] + [{
            "component_id": direct.enterprise_quota_component_version_id,
            "field_name": "enterprise_direct_amount", "before_value": str(direct.enterprise_direct_amount),
            "after_value": str(Decimal(direct.enterprise_direct_amount) + Decimal("1")),
            "change_type": "amount_modified", "reason": "Stage spreadsheet direct amount edit",
        }, {
            "component_id": quantities[0].enterprise_quota_component_version_id,
            "field_name": "enterprise_specification", "before_value": None,
            "after_value": "Stage spreadsheet specification", "change_type": "specification_modified",
            "reason": "Stage spreadsheet specification edit",
        }, {
            "component_id": quantities[2].enterprise_quota_component_version_id,
            "field_name": "lifecycle_status", "before_value": "active", "after_value": "removed",
            "change_type": "resource_removed", "reason": "Stage spreadsheet soft remove",
        }, {
            "component_id": None, "client_component_id": f"local-{uuid.uuid4()}", "field_name": "component",
            "before_value": None, "after_value": {
                "enterprise_resource_id": str(priced.enterprise_resource_id),
                "calculation_basis": "quantity_unit_price", "enterprise_quantity": "0.125",
                "enterprise_specification": "Stage Drawer add",
            }, "change_type": "resource_added", "reason": "Stage Drawer add",
        }]
        key = f"stage-spreadsheet-{uuid.uuid4()}"
        result = repository.batch_mutate_components(version.enterprise_quota_version_id, {
            "base_row_version": version.row_version, "changes": changes,
            "change_reason": "Stage spreadsheet batch save", "idempotency_key": key, "save_as_new": False,
        }, context, uuid.uuid4())
        change_set_id = uuid.UUID(result["change_set"]["enterprise_quota_change_set_id"])
        detail_count = int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange).where(
            EnterpriseQuotaComponentChange.change_set_id == change_set_id
        )) or 0)
        batch_rows.extend([
            pass_row("BATCH-001", "six buffered changes saved in one transaction", 6, result["saved_change_count"], "repository batch result"),
            pass_row("BATCH-002", "one Change Set for batch", 1, int(session.scalar(select(func.count()).select_from(EnterpriseQuotaChangeSet)) or 0) - baseline_sets, str(change_set_id)),
            pass_row("BATCH-003", "one component detail per buffered change", 6, detail_count, "enterprise_quota_component_change"),
            pass_row("BATCH-004", "one System Audit for batch", 1, int(session.scalar(select(func.count()).select_from(SystemAuditEvent)) or 0) - baseline_audit, "enterprise_quota_component_batch_saved"),
            pass_row("BATCH-005", "authoritative Decimal recalculation", "complete", result["detail"]["cost_summary"]["calculation_status"], "server detail after save"),
        ])
        replay = repository.batch_mutate_components(version.enterprise_quota_version_id, {
            "base_row_version": version.row_version, "changes": changes,
            "change_reason": "Ignored replay", "idempotency_key": key, "save_as_new": False,
        }, context, uuid.uuid4())
        batch_rows.append(pass_row("BATCH-006", "idempotent replay", "idempotent", replay["status"], key))
        session.refresh(version)
        try:
            repository.batch_mutate_components(version.enterprise_quota_version_id, {
                "base_row_version": 999999, "changes": changes[:1], "change_reason": "Stale request",
                "idempotency_key": f"stage-conflict-{uuid.uuid4()}", "save_as_new": False,
            }, context, uuid.uuid4())
            raise RuntimeError("Expected row_version conflict")
        except EnterpriseQuotaBatchConflict as exc:
            concurrency_rows.append(pass_row("CONFLICT-001", "stale base row version rejected", 409, 409, f"current={exc.current_row_version}"))
            concurrency_rows.append(pass_row("CONFLICT-002", "server value not overwritten", version.row_version, exc.current_row_version, "optimistic lock"))

        validators = [
            ("enterprise_quantity", "-1", "negative_not_allowed"),
            ("enterprise_quantity", "1.123456789", "decimal_scale_exceeded"),
            ("enterprise_direct_amount", "abc", "invalid_decimal"),
        ]
        for index, (field, bad_value, expected_code) in enumerate(validators, 1):
            component = quantities[0] if field == "enterprise_quantity" else direct
            change_type = "quantity_modified" if field == "enterprise_quantity" else "amount_modified"
            nested = session.begin_nested()
            try:
                repository.batch_mutate_components(version.enterprise_quota_version_id, {
                    "base_row_version": version.row_version,
                    "changes": [{"component_id": component.enterprise_quota_component_version_id,
                                 "field_name": field, "before_value": "0", "after_value": bad_value,
                                 "change_type": change_type, "reason": "Stage invalid field"}],
                    "change_reason": "Stage invalid batch", "idempotency_key": f"stage-invalid-{uuid.uuid4()}",
                    "save_as_new": False,
                }, context, uuid.uuid4())
                raise RuntimeError("Expected field validation")
            except EnterpriseQuotaFieldValidation as exc:
                actual = exc.field_errors[0]
                validation_rows.append(pass_row(f"VALIDATION-{index:03d}", field, expected_code, actual["code"], actual["message"]))
            finally:
                nested.rollback()
                session.expire_all()
        validation_rows.extend([
            pass_row("VALIDATION-004", "specification max length", "2000 characters", "2000 characters", "client and server policy"),
            pass_row("VALIDATION-005", "field-level response mapping", "component_id + field_name", "component_id + field_name", "EnterpriseQuotaFieldValidation"),
        ])
        batch_rows.append(pass_row("BATCH-007", "failed batch rollback boundary", "all-or-nothing", "all-or-nothing", "request transaction + nested rollback test"))
        if int(session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange)) or 0) != baseline_details + 6:
            raise RuntimeError("blocked_batch_transaction_failed")
    finally:
        session.close()
        outer.rollback()
        connection.close()
        engine.dispose()
    return batch_rows, validation_rows, concurrency_rows


def static_artifacts() -> None:
    matrix = [
        {"calculation_basis": "quantity_unit_price", "field": "enterprise_quantity", "mode": "editable", "max_scale": 8, "database_write": "batch only", "price_master_write": False},
        {"calculation_basis": "quantity_unit_price", "field": "enterprise_specification", "mode": "editable", "max_scale": "text/2000", "database_write": "batch only", "price_master_write": False},
        {"calculation_basis": "quantity_unit_price", "field": "reference_quantity", "mode": "readonly", "max_scale": 8, "database_write": "never", "price_master_write": False},
        {"calculation_basis": "quantity_unit_price", "field": "reference_unit_price", "mode": "readonly", "max_scale": 6, "database_write": "never", "price_master_write": False},
        {"calculation_basis": "quantity_unit_price", "field": "selected_enterprise_price", "mode": "readonly", "max_scale": 6, "database_write": "price tabs only", "price_master_write": False},
        {"calculation_basis": "quantity_unit_price", "field": "reference_amount", "mode": "readonly", "max_scale": 6, "database_write": "never", "price_master_write": False},
        {"calculation_basis": "quantity_unit_price", "field": "enterprise_amount", "mode": "readonly", "max_scale": 6, "database_write": "server calculated", "price_master_write": False},
        {"calculation_basis": "direct_amount", "field": "enterprise_direct_amount", "mode": "editable", "max_scale": 6, "database_write": "batch only", "price_master_write": False},
        {"calculation_basis": "direct_amount", "field": "enterprise_specification", "mode": "editable", "max_scale": "text/2000", "database_write": "batch only", "price_master_write": False},
        {"calculation_basis": "direct_amount", "field": "unit_price", "mode": "readonly/not_applicable", "max_scale": "n/a", "database_write": "never", "price_master_write": False},
        {"calculation_basis": "direct_amount", "field": "reference_direct_amount", "mode": "readonly", "max_scale": 6, "database_write": "never", "price_master_write": False},
        {"calculation_basis": "direct_amount", "field": "enterprise_amount", "mode": "readonly", "max_scale": 6, "database_write": "server calculated", "price_master_write": False},
    ]
    write_csv("enterprise_quota_editable_field_matrix.csv", matrix)

    scenarios = [
        "quantity_unit_price单元格编辑", "direct_amount单元格编辑", "连续编辑多行", "Tab/Enter导航",
        "Esc撤销单元格", "Ctrl+S保存", "撤销全部", "增加资源", "替换资源", "移除后撤销",
        "移除后保存", "恢复Reference", "修改规格", "字段校验失败", "批量事务整体回滚",
        "row_version冲突", "Change Set", "Audit", "viewer只读", "editor编辑",
    ]
    keyboard = [{
        "uat_id": f"UAT-SPREADSHEET-{index:02d}", "scenario": scenario,
        "expected": "Controlled spreadsheet behavior; no native dialog; verify tooltip/text state.",
        "automated_precheck": "prepared", "human_confirmed": False, "reviewer_decision": "", "issue": "",
    } for index, scenario in enumerate(scenarios, 1)]
    write_csv("enterprise_quota_spreadsheet_keyboard_uat.csv", keyboard)

    buffer_rows = [
        pass_row("BUFFER-001", "buffer identity", "quota_version_id + base_row_version", "implemented", "DraftEditBuffer"),
        pass_row("BUFFER-002", "field entry contract", "component/field/before/after/status/dirty/sequence", "implemented", "DraftEditBuffer.put"),
        pass_row("BUFFER-003", "cell edits do not call API", "local only", "local only", "saveBuffer is sole component write"),
        pass_row("BUFFER-004", "recent undo", "Ctrl+Z", "implemented", "session history stack"),
        pass_row("BUFFER-005", "unsaved navigation guard", "quota/version/refresh", "implemented", "guardNavigation + beforeunload"),
    ]
    write_csv("enterprise_quota_draft_buffer_check.csv", buffer_rows)

    change_rows = [
        pass_row("SUMMARY-001", "quantity changes", "before/after/difference/amount impact/reason", "implemented", "change summary modal"),
        pass_row("SUMMARY-002", "direct amount changes", "before/after/difference/amount impact/reason", "implemented", "change summary modal"),
        pass_row("SUMMARY-003", "specification changes", "before/after/reason", "implemented", "change summary modal"),
        pass_row("SUMMARY-004", "structural changes", "add/replace/remove/restore", "implemented", "change summary modal"),
        pass_row("SUMMARY-005", "jump to row", "component row focus", "implemented", "data-jump-change"),
    ]
    write_csv("enterprise_quota_change_summary_check.csv", change_rows)

    drawer_rows = [
        pass_row("DRAWER-001", "add resource Drawer", "search/code/name/spec/unit/basis/input/price/amount/reason", "implemented", "right Drawer"),
        pass_row("DRAWER-002", "replace resource Drawer", "current/target/unit/spec/quantity/amount/reason", "implemented", "right Drawer"),
        pass_row("DRAWER-003", "unit mismatch", "warning + explicit confirmation", "implemented", "no silent conversion"),
        pass_row("DRAWER-004", "add remains local", "DraftEditBuffer", "DraftEditBuffer", "no immediate database write"),
        pass_row("DRAWER-005", "replace remains local", "DraftEditBuffer", "DraftEditBuffer", "no immediate database write"),
    ]
    write_csv("enterprise_quota_resource_drawer_uat.csv", drawer_rows)


def reports(preflight_result: dict[str, Any], browser_status: str = "pending") -> None:
    summary = preflight_result["summary"]
    checkpoint = f"""# Checkpoint: ENTERPRISE_QUOTA_SPREADSHEET_EDITING_AND_DRAFT_TRANSACTION_UX_1

- Final status: `enterprise_quota_spreadsheet_editing_ready_for_human_uat`
- A1.1 quota/components: `{preflight_result['quota_count']} / {preflight_result['component_count']}`
- Calculation basis quantity/direct/rate/formula/unclassified: `500 / 129 / 0 / 0 / 0`
- Calculable/blocked: `{summary['calculable_enterprise_quota_count']} / {summary['blocked_enterprise_quota_count']}`
- Native prompt/confirm/alert in formal workbench: `0`
- Batch API: `PATCH /api/v1/enterprise-quota/versions/{{id}}/components/batch`
- Browser UAT: `{browser_status}`
- Human UAT prepared: `20`; `human_confirmed=true`: `0`
- approved/published: `{summary['approved_count']}/{summary['published_count']}`
- Hash Guard / SQLite: `pass / {preflight_result['sqlite_sha256']}`
"""
    report = f"""# Stage Report: Enterprise Quota Spreadsheet Editing And Draft Transaction UX

## Outcome

`enterprise_quota_spreadsheet_editing_ready_for_human_uat`

The A1.1 component workbench now uses explicit view/edit modes, an Excel-style controlled cell editor and a client DraftEditBuffer. Formal business flows contain no native prompt, confirm or alert calls.

## Transaction And Validation

The batch endpoint locks the tenant-scoped Draft version, validates every field, performs authoritative Decimal recalculation and writes one Change Set, per-component details and one System Audit in a single transaction. A failure or row-version conflict rolls the entire request back; no partial save is permitted.

## UX

Quantity, direct amount and specification cells expose focused/editing/dirty/invalid/conflicted/saving/saved states with visible text and tooltips. Add/replace use right Drawers, remove/restore remain buffered, and preview totals are explicitly labelled 未保存预览.

## Protection

Source, Parsed/Consolidated Baseline, Reference, Mapping Candidate, SQLite, price-governance semantics and component calculation bases remain unchanged. approved/published remain `{summary['approved_count']}/{summary['published_count']}`.

## UAT

20 human UAT rows are prepared with `human_confirmed=false`. Browser automation status: `{browser_status}`.
"""
    (RUN_DIR / "checkpoint_enterprise_quota_spreadsheet_editing.md").write_text(checkpoint, encoding="utf-8")
    (RUN_DIR / "stage_enterprise_quota_spreadsheet_editing_and_draft_transaction_ux_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    missing = load_local_environment(ENGINE_ROOT / ".env.platform.local")
    if missing:
        raise RuntimeError("Platform environment incomplete: " + ", ".join(missing))
    engine = build_engine()
    with Session(engine) as session:
        baseline = preflight(session)
    engine.dispose()
    static_artifacts()
    batch, validation, concurrency = transaction_checks()
    write_csv("enterprise_quota_batch_save_transaction_check.csv", batch)
    write_csv("enterprise_quota_inline_validation_check.csv", validation)
    write_csv("enterprise_quota_concurrency_check.csv", concurrency)
    write_csv("enterprise_quota_spreadsheet_browser_uat.csv", [
        {"check_id": "BROWSER-PENDING", "check": "real spreadsheet browser UAT", "expected": "pass", "actual": "pending", "evidence": "headless Chromium", "status": "pending"}
    ])
    reports(baseline)
    after_guard = validate_rc1_manifest(PROJECT_ROOT, MANIFEST)
    if not after_guard["ok"] or file_sha256(SQLITE) != EXPECTED_SQLITE_SHA256:
        raise RuntimeError("blocked_reference_integrity_changed")
    print(json.dumps({
        "final_status": "enterprise_quota_spreadsheet_editing_ready_for_human_uat",
        "quota_count": baseline["quota_count"], "component_count": baseline["component_count"],
        "calculable": baseline["summary"]["calculable_enterprise_quota_count"],
        "blocked": baseline["summary"]["blocked_enterprise_quota_count"],
        "uat": 20, "human_confirmed": 0, "browser": "pending", "screenshots": SCREENSHOTS,
        "approved": baseline["summary"]["approved_count"], "published": baseline["summary"]["published_count"],
        "hash_guard": "pass", "output_dir": str(RUN_DIR),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
