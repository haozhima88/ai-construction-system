from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from platform_db.models import (
    EnterprisePriceApproval,
    EnterprisePriceChangeSet,
    EnterprisePriceSnapshot,
    EnterprisePriceSnapshotLine,
    EnterprisePriceSourceDocument,
    EnterprisePriceVersion,
    EnterpriseComponentCalculationProfile,
    EnterpriseQuota,
    EnterpriseQuotaChangeSet,
    EnterpriseQuotaComponentChange,
    EnterpriseQuotaComponentVersion,
    EnterpriseQuotaRelease,
    EnterpriseQuotaReviewEvent,
    EnterpriseQuotaRuleVersion,
    EnterpriseQuotaVersion,
    EnterpriseResource,
    EnterpriseResourceReferenceLink,
    ReferenceQuotaResource,
    ReferenceQuotaItem,
    SystemAuditEvent,
)
from platform_db.models.base import EnterpriseQuotaState, EnterpriseReviewStatus
from platform_db.services.enterprise_quota_pricing import (
    authoritative_amount,
    component_amount_by_basis,
    component_comparison,
    summarize_components,
)

if TYPE_CHECKING:
    from platform_db.services.authentication import AuthContext


class EnterpriseQuotaError(RuntimeError):
    pass


class EnterpriseQuotaNotFound(EnterpriseQuotaError):
    pass


class EnterpriseQuotaConflict(EnterpriseQuotaError):
    pass


class EnterpriseQuotaValidation(EnterpriseQuotaError):
    pass


class EnterpriseQuotaFieldValidation(EnterpriseQuotaValidation):
    def __init__(self, message: str, field_errors: list[dict[str, Any]]):
        super().__init__(message)
        self.field_errors = field_errors


class EnterpriseQuotaBatchConflict(EnterpriseQuotaConflict):
    def __init__(self, current_row_version: int):
        super().__init__(f"row_version conflict: current={current_row_version}")
        self.current_row_version = current_row_version


def value(item: Any) -> Any:
    return item.value if hasattr(item, "value") else item


def natural_code(code: str) -> tuple[Any, ...]:
    parts: list[Any] = []
    for item in code.replace("-", ".").split("."):
        parts.append(int(item) if item.isdigit() else item)
    return tuple(parts)


class EnterpriseQuotaRepository:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    def summary(self) -> dict[str, Any]:
        a111_reference = int(self.session.scalar(select(func.count()).select_from(ReferenceQuotaItem).where(
            ReferenceQuotaItem.source_code.like("A1-1-%")
        )) or 0)
        exact_methods = ("exact_code", "normalized_code", "exact_name_spec_unit")
        exact = int(self.session.scalar(select(func.count()).select_from(EnterpriseResourceReferenceLink).where(
            EnterpriseResourceReferenceLink.tenant_id == self.tenant_id,
            EnterpriseResourceReferenceLink.match_method.in_(exact_methods),
        )) or 0)
        manual = int(self.session.scalar(select(func.count()).select_from(EnterpriseResourceReferenceLink).where(
            EnterpriseResourceReferenceLink.tenant_id == self.tenant_id,
            EnterpriseResourceReferenceLink.match_method.in_(("semantic_candidate", "manual_link")),
        )) or 0)
        unmatched = int(self.session.scalar(select(func.count()).select_from(EnterpriseResourceReferenceLink).where(
            EnterpriseResourceReferenceLink.tenant_id == self.tenant_id,
            EnterpriseResourceReferenceLink.match_method == "unmatched",
        )) or 0)
        components = list(self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_(
                select(EnterpriseQuotaVersion.enterprise_quota_version_id).where(
                    EnterpriseQuotaVersion.tenant_id == self.tenant_id,
                    EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"),
                )
            )
        )))
        missing_resources = len({row.enterprise_resource_id for row in components if row.selected_enterprise_price is None})
        active_components = [row for row in components if row.lifecycle_status != "removed"]
        basis_counts = {
            basis: sum(row.calculation_basis == basis for row in active_components)
            for basis in ("quantity_unit_price", "direct_amount", "rate_based", "formula_based")
        }
        blocked_version_ids: set[uuid.UUID] = set()
        unclassified_component_count = 0
        for component in active_components:
            _, calculation_error = component_amount_by_basis({
                "lifecycle_status": component.lifecycle_status,
                "calculation_basis": component.calculation_basis,
                "consumption": component.consumption,
                "selected_enterprise_price": component.selected_enterprise_price,
                "enterprise_direct_amount": component.enterprise_direct_amount,
                "calculation_base": component.calculation_base,
                "enterprise_rate": component.enterprise_rate,
                "formula_code": component.formula_code,
                "formula_version": component.formula_version,
            })
            if calculation_error:
                blocked_version_ids.add(component.enterprise_quota_version_id)
            unclassified_component_count += calculation_error == "unclassified_component"
        a111_version_ids = {
            row.enterprise_quota_version_id for row in components
        }
        calculable_quota_count = len(a111_version_ids - blocked_version_ids)
        approved = int(self.session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.tenant_id == self.tenant_id,
            EnterpriseQuotaVersion.state == EnterpriseQuotaState.approved,
        )) or 0)
        approved += int(self.session.scalar(select(func.count()).select_from(EnterprisePriceApproval).where(
            EnterprisePriceApproval.tenant_id == self.tenant_id,
            EnterprisePriceApproval.decision == "approved",
        )) or 0)
        published = int(self.session.scalar(select(func.count()).select_from(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.tenant_id == self.tenant_id,
            EnterpriseQuotaVersion.state == EnterpriseQuotaState.published,
        )) or 0)
        published += int(self.session.scalar(select(func.count()).select_from(EnterpriseQuotaRelease).where(
            EnterpriseQuotaRelease.tenant_id == self.tenant_id,
            EnterpriseQuotaRelease.status == "published",
        )) or 0)
        price_rows = list(self.session.scalars(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == self.tenant_id
        )))
        price_rows_by_resource: dict[uuid.UUID, list[EnterprisePriceVersion]] = {}
        for price_row in price_rows:
            price_rows_by_resource.setdefault(price_row.enterprise_resource_id, []).append(price_row)
        selected_prices = [self._selected_price(rows) for rows in price_rows_by_resource.values()]
        confirmed_manual_prices = sum(
            row.price_source_type == "enterprise_manual_price"
            and row.pricing_review_status == "manual_price_reviewed"
            for row in selected_prices
            if row is not None
        )
        return {
            "final_status": "enterprise_quota_component_editing_ready_for_human_uat",
            "a111_reference_quota_count": a111_reference,
            "enterprise_quota_draft_count": self._count(EnterpriseQuotaVersion, EnterpriseQuotaVersion.state == EnterpriseQuotaState.draft),
            "enterprise_resource_count": self._count(EnterpriseResource),
            "resource_reference_link_count": self._count(EnterpriseResourceReferenceLink),
            "exact_match_count": exact,
            "manual_review_count": manual,
            "unmatched_count": unmatched,
            "enterprise_price_record_count": self._count(EnterprisePriceVersion),
            "missing_enterprise_price_resource_count": missing_resources,
            "provincial_fallback_price_count": self._count(
                EnterprisePriceVersion,
                EnterprisePriceVersion.price_source_type == "provincial_reference_fallback",
            ),
            "enterprise_manual_price_count": self._count(
                EnterprisePriceVersion,
                EnterprisePriceVersion.price_source_type == "enterprise_manual_price",
            ),
            "reviewed_fallback_accepted_count": self._count(
                EnterprisePriceVersion,
                EnterprisePriceVersion.enterprise_price_version_id.in_([
                    row.enterprise_price_version_id for row in selected_prices
                    if row is not None and row.pricing_review_status == "reviewed_fallback_accepted"
                ]),
            ),
            "pending_manual_pricing_count": sum(
                row.requires_manual_review for row in selected_prices if row is not None
            ) + missing_resources,
            "calculation_price_coverage": f"{self._count(EnterpriseResource) - missing_resources}/{self._count(EnterpriseResource)}",
            "enterprise_confirmed_price_coverage": f"{confirmed_manual_prices}/{self._count(EnterpriseResource)}",
            "quantity_unit_price_component_count": basis_counts["quantity_unit_price"],
            "direct_amount_component_count": basis_counts["direct_amount"],
            "rate_based_component_count": basis_counts["rate_based"],
            "formula_based_component_count": basis_counts["formula_based"],
            "unclassified_component_count": unclassified_component_count,
            "calculable_enterprise_quota_count": calculable_quota_count,
            "blocked_enterprise_quota_count": len(blocked_version_ids),
            "enterprise_quota_calculation_coverage": f"{calculable_quota_count}/{len(a111_version_ids)}",
            "change_set_count": self._count(EnterpriseQuotaChangeSet),
            "preview_snapshot_count": self._count(EnterprisePriceSnapshot, EnterprisePriceSnapshot.snapshot_type == "preview"),
            "snapshot_line_count": int(self.session.scalar(select(func.count()).select_from(EnterprisePriceSnapshotLine).where(
                EnterprisePriceSnapshotLine.enterprise_price_snapshot_id.in_(
                    select(EnterprisePriceSnapshot.enterprise_price_snapshot_id).where(
                        EnterprisePriceSnapshot.tenant_id == self.tenant_id
                    )
                )
            )) or 0),
            "approved_count": approved,
            "published_count": published,
        }

    def _count(self, model, *conditions) -> int:
        statement = select(func.count()).select_from(model)
        if hasattr(model, "tenant_id"):
            statement = statement.where(model.tenant_id == self.tenant_id)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.session.scalar(statement) or 0)

    def tree(self) -> dict[str, Any]:
        rows = self.session.execute(
            select(EnterpriseQuota, EnterpriseQuotaVersion)
            .join(EnterpriseQuotaVersion, EnterpriseQuotaVersion.enterprise_quota_id == EnterpriseQuota.enterprise_quota_id)
            .where(
                EnterpriseQuota.tenant_id == self.tenant_id,
                EnterpriseQuotaVersion.source_quota_code.like("A1-1-%"),
            )
        ).all()
        items = [{
            "enterprise_quota_id": str(quota.enterprise_quota_id),
            "enterprise_quota_version_id": str(version.enterprise_quota_version_id),
            "source_quota_code": version.source_quota_code,
            "enterprise_quota_code": quota.enterprise_quota_code,
            "quota_name": quota.quota_name,
            "unit": version.unit,
            "version_no": version.version_no,
            "status": value(version.state),
            "row_version": version.row_version,
        } for quota, version in rows]
        items.sort(key=lambda row: natural_code(row["source_quota_code"]))
        return {"items": items, "total": len(items)}

    def price_sources(self) -> dict[str, Any]:
        rows = list(self.session.scalars(select(EnterprisePriceSourceDocument).where(
            EnterprisePriceSourceDocument.tenant_id == self.tenant_id
        ).order_by(EnterprisePriceSourceDocument.file_name)))
        return {"items": [{
            "source_price_document_id": str(row.source_price_document_id),
            "file_name": row.file_name,
            "sha256": row.sha256,
            "file_type": row.file_type,
            "record_count": row.record_count,
            "resource_code_status": row.resource_code_status,
            "resource_name_status": row.resource_name_status,
            "specification_status": row.specification_status,
            "unit_status": row.unit_status,
            "price_status": row.price_status,
            "tax_mode_status": row.tax_mode_status,
            "effective_date_status": row.effective_date_status,
            "region_status": row.region_status,
            "source_role": row.source_role,
            "authority_status": row.authority_status,
            "review_status": row.review_status,
        } for row in rows], "total": len(rows)}

    @classmethod
    def _selected_price(cls, rows: list[EnterprisePriceVersion]) -> EnterprisePriceVersion | None:
        # Every price adjustment creates a later immutable version.  Selecting by
        # version number lets "restore fallback" supersede a manual draft without
        # deleting that manual-price history.
        return max(rows, key=lambda row: row.version_no) if rows else None

    @staticmethod
    def _price_payload(row: EnterprisePriceVersion | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "enterprise_price_version_id": str(row.enterprise_price_version_id),
            "version_no": row.version_no,
            "version_type": row.version_type,
            "price_value": row.price_value,
            "unit": row.unit,
            "price_type": row.price_type,
            "price_source_type": row.price_source_type,
            "is_fallback": row.is_fallback,
            "requires_manual_review": row.requires_manual_review,
            "pricing_review_status": row.pricing_review_status,
            "tax_mode": row.tax_mode,
            "region": row.region,
            "effective_from": row.effective_from,
            "effective_to": row.effective_to,
            "fallback_reason": row.fallback_reason,
            "reference_resource_id": str(row.reference_resource_id) if row.reference_resource_id else None,
            "reference_release_id": row.reference_release_id,
            "reference_resource_code": row.reference_resource_code,
            "source_hash": row.source_hash,
            "review_status": value(row.review_status),
            "created_by": str(row.created_by) if row.created_by else None,
            "created_at": row.created_at,
            "row_version": row.row_version,
        }

    def price_workbench(self, filter_name: str = "all", threshold: Decimal = Decimal("20")) -> dict[str, Any]:
        resources = list(self.session.scalars(select(EnterpriseResource).where(
            EnterpriseResource.tenant_id == self.tenant_id
        ).order_by(EnterpriseResource.resource_code, EnterpriseResource.resource_name)))
        prices = list(self.session.scalars(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == self.tenant_id
        ).order_by(EnterprisePriceVersion.enterprise_resource_id, EnterprisePriceVersion.version_no)))
        prices_by_resource: dict[uuid.UUID, list[EnterprisePriceVersion]] = {}
        for price in prices:
            prices_by_resource.setdefault(price.enterprise_resource_id, []).append(price)
        changes = list(self.session.scalars(select(EnterprisePriceChangeSet).where(
            EnterprisePriceChangeSet.tenant_id == self.tenant_id
        ).order_by(EnterprisePriceChangeSet.changed_at.desc())))
        changes_by_resource: dict[uuid.UUID, list[EnterprisePriceChangeSet]] = {}
        for change in changes:
            changes_by_resource.setdefault(change.enterprise_resource_id, []).append(change)
        items: list[dict[str, Any]] = []
        for resource in resources:
            history = prices_by_resource.get(resource.enterprise_resource_id, [])
            selected = self._selected_price(history)
            fallback = next((row for row in history if row.version_type == "provincial_reference_fallback"), None)
            manual = selected if selected and selected.price_source_type == "enterprise_manual_price" else None
            adjustment_percentage = None
            if manual is not None and fallback is not None and fallback.price_value != 0:
                adjustment_percentage = ((manual.price_value - fallback.price_value) / fallback.price_value * Decimal("100")).quantize(Decimal("0.01"))
            item = {
                "enterprise_resource_id": str(resource.enterprise_resource_id),
                "resource_code": resource.resource_code,
                "resource_name": resource.resource_name,
                "specification": resource.specification,
                "unit": resource.unit,
                "resource_category": resource.resource_category,
                "resource_row_version": resource.row_version,
                "provincial_reference_price": fallback.price_value if fallback else None,
                "provincial_fallback_price": fallback.price_value if fallback else None,
                "enterprise_manual_price": manual.price_value if manual else None,
                "selected_price": selected.price_value if selected else None,
                "price_source_type": selected.price_source_type if selected else "provincial_reference_price_missing",
                "pricing_review_status": selected.pricing_review_status if selected else "provincial_reference_price_missing",
                "is_fallback": selected.is_fallback if selected else False,
                "requires_manual_review": selected.requires_manual_review if selected else True,
                "effective_from": selected.effective_from if selected else None,
                "tax_mode": selected.tax_mode if selected else None,
                "region": selected.region if selected else None,
                "adjustment_reason": selected.fallback_reason if selected else "Reference price missing; manual price required.",
                "adjustment_percentage": adjustment_percentage,
                "enterprise_confirmed": False,
                "review_status": value(selected.review_status) if selected else None,
                "price_row_version": selected.row_version if selected else None,
                "selected_price_version_id": str(selected.enterprise_price_version_id) if selected else None,
                "version_history": [self._price_payload(row) for row in reversed(history)],
                "change_sets": [{
                    "change_set_id": str(row.enterprise_price_change_set_id),
                    "previous_price": row.previous_price,
                    "new_price": row.new_price,
                    "change_amount": row.change_amount,
                    "change_percentage": row.change_percentage,
                    "change_reason": row.change_reason,
                    "source_type": row.source_type,
                    "changed_by": str(row.changed_by),
                    "changed_at": row.changed_at,
                    "request_id": str(row.request_id),
                } for row in changes_by_resource.get(resource.enterprise_resource_id, [])],
            }
            include = {
                "all": True,
                "provincial_fallback": item["price_source_type"] == "provincial_reference_fallback",
                "pending_manual_pricing": item["requires_manual_review"],
                "manual_priced": manual is not None,
                "accepted_fallback": item["pricing_review_status"] == "reviewed_fallback_accepted",
                "reference_price_missing": selected is None,
                "internal_observation_large": False,
                "manual_adjustment_large": adjustment_percentage is not None and abs(adjustment_percentage) > threshold,
                "ready_for_review": item["pricing_review_status"] in {"manual_price_draft", "reviewed_fallback_accepted"}
                and item["review_status"] == "draft",
            }.get(filter_name)
            if include is None:
                raise EnterpriseQuotaValidation(f"Unknown price filter: {filter_name}")
            if include:
                items.append(item)
        return {
            "items": items,
            "total": len(items),
            "filter": filter_name,
            "threshold_percentage": threshold,
            "calculation_price_coverage": f"{sum(self._selected_price(prices_by_resource.get(row.enterprise_resource_id, [])) is not None for row in resources)}/{len(resources)}",
            "enterprise_confirmed_price_coverage": f"{sum((selected := self._selected_price(prices_by_resource.get(row.enterprise_resource_id, []))) is not None and selected.price_source_type == 'enterprise_manual_price' and selected.pricing_review_status == 'manual_price_reviewed' for row in resources)}/{len(resources)}",
        }

    def create_manual_price(
        self, resource_id: uuid.UUID, payload: dict[str, Any], context: AuthContext, request_id: uuid.UUID
    ) -> dict[str, Any]:
        resource = self._resource(resource_id)
        history = list(self.session.scalars(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == self.tenant_id,
            EnterprisePriceVersion.enterprise_resource_id == resource_id,
        ).order_by(EnterprisePriceVersion.version_no).with_for_update()))
        current = self._selected_price(history)
        existing = self.session.scalar(select(EnterprisePriceChangeSet).where(
            EnterprisePriceChangeSet.tenant_id == self.tenant_id,
            EnterprisePriceChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "enterprise_price_version_id": str(existing.new_price_version_id)}
        supplied_version = current.row_version if current else resource.row_version
        if supplied_version != payload["row_version"]:
            raise EnterpriseQuotaConflict(f"row_version conflict: current={supplied_version}")
        price_value = Decimal(str(payload["price_value"]))
        if price_value < 0:
            raise EnterpriseQuotaValidation("Manual price cannot be negative")
        version_no = max((row.version_no for row in history), default=0) + 1
        effective_from = payload["effective_from"]
        if isinstance(effective_from, str):
            effective_from = datetime.fromisoformat(effective_from)
        source_payload = {
            "resource_id": str(resource_id), "version_no": version_no, "price": str(price_value),
            "tax_mode": payload["tax_mode"], "region": payload["region"],
            "effective_from": effective_from.isoformat(), "reason": payload["change_reason"],
        }
        source_hash = hashlib.sha256(json.dumps(source_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        reference = current
        if reference is None:
            link = self.session.scalar(select(EnterpriseResourceReferenceLink).where(
                EnterpriseResourceReferenceLink.tenant_id == self.tenant_id,
                EnterpriseResourceReferenceLink.enterprise_resource_id == resource_id,
            ).order_by(EnterpriseResourceReferenceLink.reference_resource_id))
            ref_row = self.session.get(ReferenceQuotaResource, link.reference_resource_id) if link else None
        else:
            ref_row = self.session.get(ReferenceQuotaResource, reference.reference_resource_id) if reference.reference_resource_id else None
        new_id = uuid.uuid4()
        row = EnterprisePriceVersion(
            enterprise_price_version_id=new_id,
            tenant_id=self.tenant_id,
            enterprise_resource_id=resource_id,
            source_price_document_id=None,
            predecessor_id=current.enterprise_price_version_id if current else None,
            version_no=version_no,
            price_value=price_value,
            unit=resource.unit,
            price_type="enterprise_manual_price_draft",
            tax_mode=str(payload["tax_mode"]),
            currency="CNY",
            region=str(payload["region"]),
            project_type="A1.1 enterprise quota pilot",
            supplier_or_source="cost_department_manual_pricing",
            confidence=None,
            effective_from=effective_from,
            effective_to=None,
            observation_ids=[],
            review_status=EnterpriseReviewStatus.draft,
            submitted_by=None,
            reviewed_by=None,
            version_type="enterprise_manual_price_draft",
            reference_resource_id=ref_row.reference_quota_resource_id if ref_row else None,
            reference_release_id=ref_row.reference_release_id if ref_row else None,
            reference_resource_code=ref_row.resource_code if ref_row else resource.resource_code,
            price_source_type="enterprise_manual_price",
            is_fallback=False,
            requires_manual_review=True,
            fallback_reason=str(payload["change_reason"]),
            source_hash=source_hash,
            pricing_review_status="manual_price_draft",
            created_by=context.user.app_user_id,
            updated_by=context.user.app_user_id,
            correlation_id=request_id,
        )
        self.session.add(row)
        self.session.flush()
        self._record_price_change(current, row, payload["change_reason"], "enterprise_manual_price", payload["idempotency_key"], context, request_id)
        self._apply_selected_price(resource_id, row, context.user.app_user_id, request_id)
        self._audit_price(context, "enterprise_manual_price_draft_created", row, self._price_payload(current), self._price_payload(row), request_id)
        self.session.flush()
        return {"status": "draft", "price": self._price_payload(row)}

    def accept_fallback(
        self, price_id: uuid.UUID, payload: dict[str, Any], context: AuthContext, request_id: uuid.UUID
    ) -> dict[str, Any]:
        row = self.session.scalar(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.enterprise_price_version_id == price_id,
            EnterprisePriceVersion.tenant_id == self.tenant_id,
        ).with_for_update())
        if row is None:
            raise EnterpriseQuotaNotFound("Enterprise Price version not found")
        if row.price_source_type != "provincial_reference_fallback":
            raise EnterpriseQuotaValidation("Only provincial fallback can be accepted as fallback")
        existing = self.session.scalar(select(EnterprisePriceChangeSet).where(
            EnterprisePriceChangeSet.tenant_id == self.tenant_id,
            EnterprisePriceChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "enterprise_price_version_id": str(existing.new_price_version_id)}
        self._require_row_version(row, payload["row_version"])
        before = self._price_payload(row)
        row.pricing_review_status = "reviewed_fallback_accepted"
        row.requires_manual_review = False
        row.fallback_reason = str(payload["change_reason"])
        row.updated_by = context.user.app_user_id
        row.correlation_id = request_id
        self._record_price_change(row, row, payload["change_reason"], "reviewed_fallback_accepted", payload["idempotency_key"], context, request_id)
        self._apply_selected_price(row.enterprise_resource_id, row, context.user.app_user_id, request_id)
        self.session.flush()
        self.session.refresh(row)
        self._audit_price(context, "provincial_fallback_accepted", row, before, self._price_payload(row), request_id)
        return {"status": "reviewed_fallback_accepted", "price": self._price_payload(row)}

    def restore_fallback(
        self, resource_id: uuid.UUID, payload: dict[str, Any], context: AuthContext, request_id: uuid.UUID
    ) -> dict[str, Any]:
        self._resource(resource_id)
        history = list(self.session.scalars(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == self.tenant_id,
            EnterprisePriceVersion.enterprise_resource_id == resource_id,
        ).order_by(EnterprisePriceVersion.version_no).with_for_update()))
        current = self._selected_price(history)
        fallback = next((row for row in history if row.version_type == "provincial_reference_fallback"), None)
        if current is None or fallback is None:
            raise EnterpriseQuotaValidation("No provincial fallback is available for this resource")
        existing = self.session.scalar(select(EnterprisePriceChangeSet).where(
            EnterprisePriceChangeSet.tenant_id == self.tenant_id,
            EnterprisePriceChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "enterprise_price_version_id": str(existing.new_price_version_id)}
        self._require_row_version(current, payload["row_version"])
        new_id = uuid.uuid4()
        row = EnterprisePriceVersion(
            enterprise_price_version_id=new_id, tenant_id=self.tenant_id,
            enterprise_resource_id=resource_id, source_price_document_id=None,
            predecessor_id=current.enterprise_price_version_id, version_no=max(item.version_no for item in history) + 1,
            price_value=fallback.price_value, unit=fallback.unit, price_type="provincial_fallback_draft",
            tax_mode=fallback.tax_mode, currency=fallback.currency, region=fallback.region,
            project_type=fallback.project_type, supplier_or_source=fallback.supplier_or_source,
            confidence=fallback.confidence, effective_from=fallback.effective_from, effective_to=fallback.effective_to,
            observation_ids=[], review_status=EnterpriseReviewStatus.draft,
            version_type="provincial_reference_fallback", reference_resource_id=fallback.reference_resource_id,
            reference_release_id=fallback.reference_release_id, reference_resource_code=fallback.reference_resource_code,
            price_source_type="provincial_reference_fallback", is_fallback=True, requires_manual_review=True,
            fallback_reason=str(payload["change_reason"]), source_hash=fallback.source_hash,
            pricing_review_status="pending_manual_pricing", created_by=context.user.app_user_id,
            updated_by=context.user.app_user_id, correlation_id=request_id,
        )
        self.session.add(row)
        self.session.flush()
        self._record_price_change(current, row, payload["change_reason"], "restore_provincial_fallback", payload["idempotency_key"], context, request_id)
        self._apply_selected_price(resource_id, row, context.user.app_user_id, request_id)
        self._audit_price(context, "provincial_fallback_restored", row, self._price_payload(current), self._price_payload(row), request_id)
        self.session.flush()
        return {"status": "draft", "price": self._price_payload(row)}

    def review_price(
        self, price_id: uuid.UUID, payload: dict[str, Any], context: AuthContext, request_id: uuid.UUID
    ) -> dict[str, Any]:
        row = self.session.scalar(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.enterprise_price_version_id == price_id,
            EnterprisePriceVersion.tenant_id == self.tenant_id,
        ).with_for_update())
        if row is None:
            raise EnterpriseQuotaNotFound("Enterprise Price version not found")
        existing = self.session.scalar(select(EnterprisePriceChangeSet).where(
            EnterprisePriceChangeSet.tenant_id == self.tenant_id,
            EnterprisePriceChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "enterprise_price_version_id": str(existing.new_price_version_id)}
        self._require_row_version(row, payload["row_version"])
        if row.created_by == context.user.app_user_id:
            raise EnterpriseQuotaValidation("Reviewer cannot review a price version they created")
        before = self._price_payload(row)
        action = payload.get("action", "review")
        if action == "return":
            row.pricing_review_status = "returned_for_revision"
            row.requires_manual_review = True
            row.review_status = EnterpriseReviewStatus.draft
        elif action == "review":
            if row.price_source_type == "enterprise_manual_price":
                row.pricing_review_status = "manual_price_reviewed"
                row.requires_manual_review = False
            else:
                row.pricing_review_status = "reviewed_fallback_accepted"
                row.requires_manual_review = False
            row.review_status = EnterpriseReviewStatus.reviewed
        else:
            raise EnterpriseQuotaValidation("Price review action must be review or return")
        row.reviewed_by = context.user.app_user_id
        row.updated_by = context.user.app_user_id
        row.correlation_id = request_id
        self._record_price_change(row, row, payload["change_reason"], f"price_{action}", payload["idempotency_key"], context, request_id)
        self.session.flush()
        self.session.refresh(row)
        self._audit_price(context, f"enterprise_price_{action}", row, before, self._price_payload(row), request_id)
        return {"status": "reviewed" if action == "review" else "returned_for_revision", "price": self._price_payload(row)}

    def _apply_selected_price(self, resource_id: uuid.UUID, price: EnterprisePriceVersion, actor_id: uuid.UUID, request_id: uuid.UUID) -> None:
        components = list(self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_resource_id == resource_id,
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id.in_(
                select(EnterpriseQuotaVersion.enterprise_quota_version_id).where(
                    EnterpriseQuotaVersion.tenant_id == self.tenant_id,
                    EnterpriseQuotaVersion.state == EnterpriseQuotaState.draft,
                )
            ),
        )))
        for component in components:
            component.enterprise_price_version_id = price.enterprise_price_version_id
            component.selected_enterprise_price = price.price_value
            component.selected_price_type = price.version_type
            self._recalculate_component(component)
            if component.calculation_basis == "quantity_unit_price" and component.enterprise_component_amount is not None:
                component.amount_source = price.price_source_type
            component.updated_by = actor_id
            component.correlation_id = request_id

    def _record_price_change(
        self, previous: EnterprisePriceVersion | None, new: EnterprisePriceVersion, reason: str,
        source_type: str, idempotency_key: str, context: AuthContext, request_id: uuid.UUID,
    ) -> EnterprisePriceChangeSet:
        previous_price = previous.price_value if previous else None
        change_amount = new.price_value - previous_price if previous_price is not None else new.price_value
        change_percentage = None
        if previous_price not in {None, Decimal("0")}:
            change_percentage = (change_amount / previous_price * Decimal("100")).quantize(Decimal("0.000001"))
        row = EnterprisePriceChangeSet(
            enterprise_price_change_set_id=uuid.uuid4(), tenant_id=self.tenant_id,
            enterprise_resource_id=new.enterprise_resource_id,
            previous_price_version_id=previous.enterprise_price_version_id if previous else None,
            new_price_version_id=new.enterprise_price_version_id,
            previous_price=previous_price, new_price=new.price_value, change_amount=change_amount,
            change_percentage=change_percentage, change_reason=reason,
            changed_by=context.user.app_user_id, changed_at=datetime.now(timezone.utc), request_id=request_id,
            source_type=source_type, idempotency_key=idempotency_key,
            created_by=context.user.app_user_id, updated_by=context.user.app_user_id, correlation_id=request_id,
        )
        self.session.add(row)
        return row

    def _audit_price(
        self, context: AuthContext, event_type: str, price: EnterprisePriceVersion,
        before: dict[str, Any] | None, after: dict[str, Any] | None, request_id: uuid.UUID,
    ) -> None:
        json_before = json.loads(json.dumps(before, default=str)) if before is not None else None
        json_after = json.loads(json.dumps(after, default=str)) if after is not None else None
        self.session.add(SystemAuditEvent(
            system_audit_event_id=uuid.uuid4(), actor_user_id=context.user.app_user_id,
            release_manifest_id=None, event_type=event_type, subject_type="enterprise_price_version",
            subject_id=str(price.enterprise_price_version_id), before_payload=json_before, after_payload=json_after,
            tenant_id=self.tenant_id, created_by=context.user.app_user_id,
            updated_by=context.user.app_user_id, correlation_id=request_id,
        ))

    @staticmethod
    def _component_snapshot(component: EnterpriseQuotaComponentVersion) -> dict[str, Any]:
        fields = (
            "enterprise_resource_id", "source_enterprise_resource_id", "source_reference_resource_id",
            "line_no", "consumption", "source_consumption", "provincial_unit_price",
            "provincial_component_amount", "enterprise_price_version_id", "selected_enterprise_price",
            "selected_price_type", "enterprise_component_amount", "amount_source", "override_reason",
            "calculation_basis", "source_direct_amount", "enterprise_direct_amount", "calculation_base",
            "enterprise_rate", "formula_code", "formula_version", "component_status",
            "lifecycle_status", "specification_override", "row_version",
        )
        result: dict[str, Any] = {}
        for field in fields:
            item = getattr(component, field)
            if isinstance(item, (Decimal, uuid.UUID, datetime)):
                item = str(item)
            result[field] = item
        return result

    def _selected_resource_price(self, resource_id: uuid.UUID) -> EnterprisePriceVersion | None:
        rows = list(self.session.scalars(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == self.tenant_id,
            EnterprisePriceVersion.enterprise_resource_id == resource_id,
        )))
        return self._selected_price(rows)

    def _set_component_resource_price(
        self, component: EnterpriseQuotaComponentVersion, resource_id: uuid.UUID
    ) -> None:
        price = self._selected_resource_price(resource_id)
        component.enterprise_price_version_id = price.enterprise_price_version_id if price else None
        component.selected_enterprise_price = price.price_value if price else None
        component.selected_price_type = price.version_type if price else None

    @staticmethod
    def _recalculate_component(component: EnterpriseQuotaComponentVersion) -> None:
        amount, error = component_amount_by_basis({
            "lifecycle_status": component.lifecycle_status,
            "calculation_basis": component.calculation_basis,
            "consumption": component.consumption,
            "selected_enterprise_price": component.selected_enterprise_price,
            "enterprise_direct_amount": component.enterprise_direct_amount,
            "calculation_base": component.calculation_base,
            "enterprise_rate": component.enterprise_rate,
            "formula_code": component.formula_code,
            "formula_version": component.formula_version,
        })
        component.enterprise_component_amount = amount
        component.amount_source = (
            f"component_calculation_blocked:{error}" if error
            else "component_removed" if component.lifecycle_status == "removed"
            else component.calculation_basis
        )

    def _record_component_change(
        self,
        *,
        version: EnterpriseQuotaVersion,
        component: EnterpriseQuotaComponentVersion,
        change_set: EnterpriseQuotaChangeSet,
        change_type: str,
        field_name: str,
        before: dict[str, Any],
        after: dict[str, Any],
        reason: str,
        idempotency_key: str,
        context: AuthContext,
        request_id: uuid.UUID,
    ) -> EnterpriseQuotaComponentChange:
        row = EnterpriseQuotaComponentChange(
            component_change_id=uuid.uuid4(), tenant_id=self.tenant_id,
            quota_version_id=version.enterprise_quota_version_id,
            component_id=component.enterprise_quota_component_version_id,
            change_set_id=change_set.enterprise_quota_change_set_id,
            change_type=change_type, field_name=field_name,
            before_value=before, after_value=after, change_reason=reason,
            changed_by=context.user.app_user_id, changed_at=datetime.now(timezone.utc),
            request_id=request_id, idempotency_key=idempotency_key, review_status="pending_review",
            created_by=context.user.app_user_id, updated_by=context.user.app_user_id,
            correlation_id=request_id,
        )
        self.session.add(row)
        return row

    def add_component(
        self, version_id: uuid.UUID, payload: dict[str, Any], context: AuthContext, request_id: uuid.UUID
    ) -> dict[str, Any]:
        existing = self.session.scalar(select(EnterpriseQuotaChangeSet).where(
            EnterpriseQuotaChangeSet.tenant_id == self.tenant_id,
            EnterpriseQuotaChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "change_set": self._change_payload(existing)}
        version, quota, _ = self._version_context(version_id, for_update=True)
        self._require_row_version(version, payload["row_version"])
        if value(version.state) != "draft":
            raise EnterpriseQuotaConflict("Only Draft versions can be edited")
        resource_id = uuid.UUID(str(payload["enterprise_resource_id"]))
        self._resource(resource_id)
        basis = str(payload.get("calculation_basis") or "quantity_unit_price")
        if basis not in {"quantity_unit_price", "direct_amount", "rate_based", "formula_based"}:
            raise EnterpriseQuotaValidation("Unsupported calculation_basis")
        line_no = int(self.session.scalar(select(func.max(EnterpriseQuotaComponentVersion.line_no)).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version_id
        )) or 0) + 1
        component = EnterpriseQuotaComponentVersion(
            enterprise_quota_component_version_id=uuid.uuid4(), enterprise_quota_version_id=version_id,
            enterprise_resource_id=resource_id, source_enterprise_resource_id=None,
            source_reference_resource_id=None, line_no=line_no,
            consumption=Decimal(str(payload["enterprise_quantity"])) if payload.get("enterprise_quantity") is not None else None,
            source_consumption=None, provincial_unit_price=None, provincial_component_amount=None,
            enterprise_price_version_id=None, selected_enterprise_price=None, selected_price_type=None,
            enterprise_component_amount=None, amount_source="component_calculation_pending",
            override_reason=payload["change_reason"], calculation_basis=basis,
            source_direct_amount=None,
            enterprise_direct_amount=Decimal(str(payload["enterprise_direct_amount"])) if payload.get("enterprise_direct_amount") is not None else None,
            calculation_base=Decimal(str(payload["calculation_base"])) if payload.get("calculation_base") is not None else None,
            enterprise_rate=Decimal(str(payload["enterprise_rate"])) if payload.get("enterprise_rate") is not None else None,
            formula_code=payload.get("formula_code"), formula_version=payload.get("formula_version"),
            component_status="resource_added", lifecycle_status="active",
            specification_override=payload.get("specification"),
            created_by=context.user.app_user_id, updated_by=context.user.app_user_id,
            correlation_id=request_id,
        )
        if basis in {"quantity_unit_price", "formula_based"}:
            self._set_component_resource_price(component, resource_id)
        self._recalculate_component(component)
        if component.enterprise_component_amount is None:
            raise EnterpriseQuotaValidation(component.amount_source)
        self.session.add(component)
        self.session.flush()
        before: dict[str, Any] = {}
        after = self._component_snapshot(component)
        change_set = self._new_change_set(
            quota, before, after, "resource_added", payload["change_reason"],
            payload["idempotency_key"], context, request_id,
        )
        version.change_set_id = change_set.enterprise_quota_change_set_id
        version.change_reason = payload["change_reason"]
        version.updated_by = context.user.app_user_id
        version.correlation_id = request_id
        self._record_component_change(
            version=version, component=component, change_set=change_set, change_type="resource_added",
            field_name="component", before=before, after=after, reason=payload["change_reason"],
            idempotency_key=payload["idempotency_key"], context=context, request_id=request_id,
        )
        self._audit(context, "enterprise_quota_component_added", version_id, before, after, request_id)
        self.session.flush()
        return {"status": "draft", "component": self._component_snapshot(component), "change_set": self._change_payload(change_set)}

    def mutate_component(
        self, version_id: uuid.UUID, component_id: uuid.UUID, payload: dict[str, Any],
        context: AuthContext, request_id: uuid.UUID,
    ) -> dict[str, Any]:
        existing = self.session.scalar(select(EnterpriseQuotaChangeSet).where(
            EnterpriseQuotaChangeSet.tenant_id == self.tenant_id,
            EnterpriseQuotaChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "change_set": self._change_payload(existing)}
        version, quota, _ = self._version_context(version_id, for_update=True)
        if value(version.state) != "draft":
            raise EnterpriseQuotaConflict("Only Draft versions can be edited")
        component = self.session.scalar(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_component_version_id == component_id,
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version_id,
        ).with_for_update())
        if component is None:
            raise EnterpriseQuotaNotFound("Enterprise Quota component not found")
        self._require_row_version(component, payload["row_version"])
        action = payload["action"]
        before = self._component_snapshot(component)
        field_name: str
        if action == "edit_quantity":
            if component.calculation_basis != "quantity_unit_price":
                raise EnterpriseQuotaValidation("Only quantity_unit_price components have editable quantity")
            if payload.get("enterprise_quantity") is None:
                raise EnterpriseQuotaValidation("enterprise_quantity is required")
            component.consumption = Decimal(str(payload["enterprise_quantity"]))
            if component.consumption < 0:
                raise EnterpriseQuotaValidation("Enterprise quantity cannot be negative")
            component.component_status = "quantity_modified"
            field_name = "consumption"
        elif action == "edit_direct_amount":
            if component.calculation_basis != "direct_amount":
                raise EnterpriseQuotaValidation("Only direct_amount components have editable direct amount")
            if payload.get("enterprise_direct_amount") is None:
                raise EnterpriseQuotaValidation("enterprise_direct_amount is required")
            component.enterprise_direct_amount = Decimal(str(payload["enterprise_direct_amount"]))
            if component.enterprise_direct_amount < 0:
                raise EnterpriseQuotaValidation("Enterprise direct amount cannot be negative")
            component.component_status = "amount_modified"
            field_name = "enterprise_direct_amount"
        elif action == "replace_resource":
            if payload.get("enterprise_resource_id") is None:
                raise EnterpriseQuotaValidation("enterprise_resource_id is required")
            resource_id = uuid.UUID(str(payload["enterprise_resource_id"]))
            self._resource(resource_id)
            component.enterprise_resource_id = resource_id
            component.calculation_basis = str(payload.get("calculation_basis") or "quantity_unit_price")
            if component.calculation_basis not in {"quantity_unit_price", "direct_amount", "rate_based", "formula_based"}:
                raise EnterpriseQuotaValidation("Unsupported calculation_basis")
            component.consumption = Decimal(str(payload["enterprise_quantity"])) if payload.get("enterprise_quantity") is not None else component.consumption
            component.enterprise_direct_amount = Decimal(str(payload["enterprise_direct_amount"])) if payload.get("enterprise_direct_amount") is not None else None
            component.calculation_base = Decimal(str(payload["calculation_base"])) if payload.get("calculation_base") is not None else None
            component.enterprise_rate = Decimal(str(payload["enterprise_rate"])) if payload.get("enterprise_rate") is not None else None
            component.formula_code = payload.get("formula_code")
            component.formula_version = payload.get("formula_version")
            component.specification_override = payload.get("specification")
            component.component_status = "resource_replaced"
            component.lifecycle_status = "active"
            self._set_component_resource_price(component, resource_id)
            field_name = "enterprise_resource_id"
        elif action == "remove_resource":
            component.lifecycle_status = "removed"
            component.component_status = "resource_removed"
            field_name = "lifecycle_status"
        elif action == "restore_reference":
            if component.source_enterprise_resource_id is not None:
                component.enterprise_resource_id = component.source_enterprise_resource_id
                profile = self.session.scalar(select(EnterpriseComponentCalculationProfile).where(
                    EnterpriseComponentCalculationProfile.tenant_id == self.tenant_id,
                    EnterpriseComponentCalculationProfile.reference_resource_id == component.source_reference_resource_id,
                )) if component.source_reference_resource_id else None
                component.calculation_basis = profile.calculation_basis if profile else "quantity_unit_price"
                component.consumption = component.source_consumption
                component.enterprise_direct_amount = component.source_direct_amount
                component.calculation_base = None
                component.enterprise_rate = None
                component.formula_code = None
                component.formula_version = None
                component.specification_override = None
                self._set_component_resource_price(component, component.enterprise_resource_id)
            component.lifecycle_status = "active"
            component.component_status = "restored"
            field_name = "component"
        elif action == "edit_specification":
            component.specification_override = str(payload.get("specification") or "").strip() or None
            field_name = "specification_override"
        else:
            raise EnterpriseQuotaValidation("Unsupported component action")
        component.override_reason = payload["change_reason"]
        component.updated_by = context.user.app_user_id
        component.correlation_id = request_id
        self._recalculate_component(component)
        after = self._component_snapshot(component)
        change_type = {
            "edit_quantity": "quantity_modified", "edit_direct_amount": "amount_modified",
            "replace_resource": "resource_replaced", "remove_resource": "resource_removed",
            "restore_reference": "restored", "edit_specification": "specification_modified",
        }[action]
        change_set = self._new_change_set(
            quota, before, after, change_type, payload["change_reason"],
            payload["idempotency_key"], context, request_id,
        )
        version.change_set_id = change_set.enterprise_quota_change_set_id
        version.change_reason = payload["change_reason"]
        version.updated_by = context.user.app_user_id
        version.correlation_id = request_id
        self._record_component_change(
            version=version, component=component, change_set=change_set, change_type=change_type,
            field_name=field_name, before=before, after=after, reason=payload["change_reason"],
            idempotency_key=payload["idempotency_key"], context=context, request_id=request_id,
        )
        self._audit(context, f"enterprise_quota_component_{change_type}", version_id, before, after, request_id)
        self.session.flush()
        return {"status": "draft", "component": self._component_snapshot(component), "change_set": self._change_payload(change_set)}

    @staticmethod
    def _batch_decimal(
        raw: Any, *, scale: int, component_id: str | None, field_name: str
    ) -> Decimal:
        text = str(raw).strip() if raw is not None else ""
        try:
            number = Decimal(text)
        except Exception as exc:
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_id, "field_name": field_name,
                "code": "invalid_decimal", "message": "请输入有效的十进制数值。",
            }]) from exc
        fraction_digits = max(0, -number.as_tuple().exponent)
        integer_digits = max(1, number.adjusted() + 1) if number else 1
        if not number.is_finite() or "e" in text.lower():
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_id, "field_name": field_name,
                "code": "invalid_decimal", "message": "不允许无穷值、NaN 或科学计数法。",
            }])
        if number < 0:
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_id, "field_name": field_name,
                "code": "negative_not_allowed", "message": "数值不得为负数。",
            }])
        if fraction_digits > scale or integer_digits + scale > 20:
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_id, "field_name": field_name,
                "code": "decimal_scale_exceeded", "message": f"最多允许 {scale} 位小数，且总精度不得超过 20 位。",
            }])
        return number

    @staticmethod
    def _batch_specification(raw: Any, *, component_id: str | None) -> str | None:
        text = str(raw or "").strip()
        if len(text) > 2000:
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_id, "field_name": "enterprise_specification",
                "code": "text_too_long", "message": "企业规格说明不得超过 2000 个字符。",
            }])
        if any(ord(character) < 32 and character not in "\t\r\n" for character in text):
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_id, "field_name": "enterprise_specification",
                "code": "invalid_character", "message": "企业规格说明包含不允许的控制字符。",
            }])
        return text or None

    def batch_mutate_components(
        self, version_id: uuid.UUID, payload: dict[str, Any], context: AuthContext, request_id: uuid.UUID
    ) -> dict[str, Any]:
        """Apply a spreadsheet Draft buffer as one tenant-scoped, all-or-nothing transaction."""
        existing = self.session.scalar(select(EnterpriseQuotaChangeSet).where(
            EnterpriseQuotaChangeSet.tenant_id == self.tenant_id,
            EnterpriseQuotaChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            component_change = self.session.scalar(select(EnterpriseQuotaComponentChange).where(
                EnterpriseQuotaComponentChange.tenant_id == self.tenant_id,
                EnterpriseQuotaComponentChange.change_set_id == existing.enterprise_quota_change_set_id,
            ))
            replay_version_id = component_change.quota_version_id if component_change else version_id
            return {
                "status": "idempotent", "enterprise_quota_version_id": str(replay_version_id),
                "change_set": self._change_payload(existing),
            }

        source, quota, _ = self._version_context(version_id, for_update=True)
        if source.row_version != payload["base_row_version"]:
            raise EnterpriseQuotaBatchConflict(source.row_version)
        if value(source.state) != "draft":
            raise EnterpriseQuotaConflict("Only Draft versions can be edited")
        changes = list(payload.get("changes") or [])
        if not changes:
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": None, "field_name": "changes", "code": "empty_batch",
                "message": "至少需要一项未保存修改。",
            }])
        seen: set[tuple[str, str]] = set()
        for change in changes:
            identity = str(change.get("component_id") or change.get("client_component_id") or "new")
            key = (identity, str(change.get("field_name")))
            if key in seen:
                raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                    "component_id": identity, "field_name": key[1], "code": "duplicate_change",
                    "message": "同一组件字段在一个批次中只能出现一次。",
                }])
            seen.add(key)

        target = source
        source_to_target: dict[uuid.UUID, uuid.UUID] = {}
        if payload.get("save_as_new"):
            source_lines = {
                row.enterprise_quota_component_version_id: row.line_no
                for row in self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
                    EnterpriseQuotaComponentVersion.enterprise_quota_version_id == source.enterprise_quota_version_id
                ))
            }
            target = self._clone_version(source, quota, payload["change_reason"], context.user.app_user_id)
            self.session.flush()
            target_by_line = {
                row.line_no: row.enterprise_quota_component_version_id
                for row in self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
                    EnterpriseQuotaComponentVersion.enterprise_quota_version_id == target.enterprise_quota_version_id
                ))
            }
            source_to_target = {
                component_id: target_by_line[line_no] for component_id, line_no in source_lines.items()
            }

        target_id = target.enterprise_quota_version_id
        components = {
            row.enterprise_quota_component_version_id: row
            for row in self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
                EnterpriseQuotaComponentVersion.enterprise_quota_version_id == target_id
            ).with_for_update())
        }
        next_line = max((row.line_no for row in components.values()), default=0) + 1
        applied: list[tuple[EnterpriseQuotaComponentVersion, str, str, dict[str, Any], dict[str, Any], str]] = []
        client_component_map: dict[str, str] = {}

        def validation_error(component_key: str | None, field: str, code: str, message: str) -> None:
            raise EnterpriseQuotaFieldValidation("Field validation failed", [{
                "component_id": component_key, "field_name": field, "code": code, "message": message,
            }])

        for change in changes:
            supplied_component_id = change.get("component_id")
            component_id = uuid.UUID(str(supplied_component_id)) if supplied_component_id else None
            if component_id in source_to_target:
                component_id = source_to_target[component_id]
            component_key = str(supplied_component_id or change.get("client_component_id") or "") or None
            requested_type = str(change["change_type"])
            reason = str(change.get("reason") or payload["change_reason"]).strip()
            after_value = change.get("after_value")

            if requested_type == "resource_added":
                if component_id is not None or not isinstance(after_value, dict):
                    validation_error(component_key, "component", "invalid_resource_add", "新增资源缺少有效的组件数据。")
                resource_id = uuid.UUID(str(after_value.get("enterprise_resource_id")))
                resource = self._resource(resource_id)
                basis = str(after_value.get("calculation_basis") or "quantity_unit_price")
                if basis not in {"quantity_unit_price", "direct_amount", "rate_based", "formula_based"}:
                    validation_error(component_key, "calculation_basis", "unsupported_basis", "不支持的组件计算类型。")
                component = EnterpriseQuotaComponentVersion(
                    enterprise_quota_component_version_id=uuid.uuid4(), enterprise_quota_version_id=target_id,
                    enterprise_resource_id=resource.enterprise_resource_id, source_enterprise_resource_id=None,
                    source_reference_resource_id=None, line_no=next_line, consumption=None, source_consumption=None,
                    provincial_unit_price=None, provincial_component_amount=None, enterprise_price_version_id=None,
                    selected_enterprise_price=None, selected_price_type=None, enterprise_component_amount=None,
                    amount_source="component_calculation_pending", override_reason=reason, calculation_basis=basis,
                    source_direct_amount=None, enterprise_direct_amount=None, calculation_base=None,
                    enterprise_rate=None, formula_code=after_value.get("formula_code"),
                    formula_version=after_value.get("formula_version"), component_status="resource_added",
                    lifecycle_status="active", specification_override=self._batch_specification(
                        after_value.get("enterprise_specification"), component_id=component_key,
                    ), created_by=context.user.app_user_id, updated_by=context.user.app_user_id,
                    correlation_id=request_id,
                )
                next_line += 1
                if basis == "quantity_unit_price":
                    component.consumption = self._batch_decimal(
                        after_value.get("enterprise_quantity"), scale=8,
                        component_id=component_key, field_name="enterprise_quantity",
                    )
                    self._set_component_resource_price(component, resource_id)
                elif basis == "direct_amount":
                    component.enterprise_direct_amount = self._batch_decimal(
                        after_value.get("enterprise_direct_amount"), scale=6,
                        component_id=component_key, field_name="enterprise_direct_amount",
                    )
                elif basis == "rate_based":
                    component.calculation_base = self._batch_decimal(
                        after_value.get("calculation_base"), scale=6,
                        component_id=component_key, field_name="calculation_base",
                    )
                    component.enterprise_rate = self._batch_decimal(
                        after_value.get("enterprise_rate"), scale=8,
                        component_id=component_key, field_name="enterprise_rate",
                    )
                else:
                    component.consumption = self._batch_decimal(
                        after_value.get("enterprise_quantity"), scale=8,
                        component_id=component_key, field_name="enterprise_quantity",
                    ) if after_value.get("enterprise_quantity") is not None else None
                    component.calculation_base = self._batch_decimal(
                        after_value.get("calculation_base"), scale=6,
                        component_id=component_key, field_name="calculation_base",
                    ) if after_value.get("calculation_base") is not None else None
                    component.enterprise_rate = self._batch_decimal(
                        after_value.get("enterprise_rate"), scale=8,
                        component_id=component_key, field_name="enterprise_rate",
                    ) if after_value.get("enterprise_rate") is not None else None
                    self._set_component_resource_price(component, resource_id)
                self._recalculate_component(component)
                if component.enterprise_component_amount is None:
                    validation_error(component_key, "component", "calculation_blocked", component.amount_source)
                self.session.add(component)
                self.session.flush()
                components[component.enterprise_quota_component_version_id] = component
                if change.get("client_component_id"):
                    client_component_map[str(change["client_component_id"])] = str(component.enterprise_quota_component_version_id)
                before = {}
                after = self._component_snapshot(component)
                applied.append((component, "resource_added", "component", before, after, reason))
                continue

            component = components.get(component_id) if component_id else None
            if component is None:
                validation_error(component_key, str(change.get("field_name")), "component_not_found", "组件不存在或不属于当前企业定额版本。")
            before = self._component_snapshot(component)
            field_name: str
            change_type: str

            if requested_type == "quantity_modified":
                if component.calculation_basis != "quantity_unit_price":
                    validation_error(component_key, "enterprise_quantity", "readonly_field", "该计算类型不允许修改企业消耗量。")
                component.consumption = self._batch_decimal(
                    after_value, scale=8, component_id=component_key, field_name="enterprise_quantity",
                )
                component.component_status = "quantity_modified"
                field_name, change_type = "consumption", "quantity_modified"
            elif requested_type == "amount_modified":
                if component.calculation_basis != "direct_amount":
                    validation_error(component_key, "enterprise_direct_amount", "readonly_field", "该计算类型不允许修改企业直接金额。")
                component.enterprise_direct_amount = self._batch_decimal(
                    after_value, scale=6, component_id=component_key, field_name="enterprise_direct_amount",
                )
                component.component_status = "amount_modified"
                field_name, change_type = "enterprise_direct_amount", "amount_modified"
            elif requested_type == "specification_modified":
                component.specification_override = self._batch_specification(after_value, component_id=component_key)
                field_name, change_type = "specification_override", "specification_modified"
            elif requested_type == "resource_replaced":
                if not isinstance(after_value, dict):
                    validation_error(component_key, "component", "invalid_resource_replace", "替换资源缺少有效的目标数据。")
                current_resource = self._resource(component.enterprise_resource_id)
                resource_id = uuid.UUID(str(after_value.get("enterprise_resource_id")))
                target_resource = self._resource(resource_id)
                if current_resource.unit != target_resource.unit and not after_value.get("unit_mismatch_confirmed"):
                    validation_error(component_key, "unit_mismatch_confirmed", "unit_mismatch", "单位不一致，必须人工确认且不得静默换算。")
                basis = str(after_value.get("calculation_basis") or component.calculation_basis)
                if basis not in {"quantity_unit_price", "direct_amount", "rate_based", "formula_based"}:
                    validation_error(component_key, "calculation_basis", "unsupported_basis", "不支持的组件计算类型。")
                component.enterprise_resource_id = resource_id
                component.calculation_basis = basis
                component.specification_override = self._batch_specification(
                    after_value.get("enterprise_specification"), component_id=component_key,
                )
                component.consumption = None
                component.enterprise_direct_amount = None
                component.calculation_base = None
                component.enterprise_rate = None
                component.formula_code = after_value.get("formula_code")
                component.formula_version = after_value.get("formula_version")
                component.enterprise_price_version_id = None
                component.selected_enterprise_price = None
                component.selected_price_type = None
                if basis == "quantity_unit_price":
                    component.consumption = self._batch_decimal(
                        after_value.get("enterprise_quantity"), scale=8,
                        component_id=component_key, field_name="enterprise_quantity",
                    )
                    self._set_component_resource_price(component, resource_id)
                elif basis == "direct_amount":
                    component.enterprise_direct_amount = self._batch_decimal(
                        after_value.get("enterprise_direct_amount"), scale=6,
                        component_id=component_key, field_name="enterprise_direct_amount",
                    )
                elif basis == "rate_based":
                    component.calculation_base = self._batch_decimal(
                        after_value.get("calculation_base"), scale=6,
                        component_id=component_key, field_name="calculation_base",
                    )
                    component.enterprise_rate = self._batch_decimal(
                        after_value.get("enterprise_rate"), scale=8,
                        component_id=component_key, field_name="enterprise_rate",
                    )
                else:
                    component.consumption = self._batch_decimal(
                        after_value.get("enterprise_quantity"), scale=8,
                        component_id=component_key, field_name="enterprise_quantity",
                    ) if after_value.get("enterprise_quantity") is not None else None
                    component.calculation_base = self._batch_decimal(
                        after_value.get("calculation_base"), scale=6,
                        component_id=component_key, field_name="calculation_base",
                    ) if after_value.get("calculation_base") is not None else None
                    component.enterprise_rate = self._batch_decimal(
                        after_value.get("enterprise_rate"), scale=8,
                        component_id=component_key, field_name="enterprise_rate",
                    ) if after_value.get("enterprise_rate") is not None else None
                    self._set_component_resource_price(component, resource_id)
                component.component_status = "resource_replaced"
                component.lifecycle_status = "active"
                field_name, change_type = "enterprise_resource_id", "resource_replaced"
            elif requested_type == "resource_removed":
                component.lifecycle_status = "removed"
                component.component_status = "resource_removed"
                field_name, change_type = "lifecycle_status", "resource_removed"
            elif requested_type == "restored":
                if component.source_enterprise_resource_id is None:
                    validation_error(component_key, "component", "reference_unavailable", "该新增组件没有可恢复的 Reference 组件。")
                component.enterprise_resource_id = component.source_enterprise_resource_id
                profile = self.session.scalar(select(EnterpriseComponentCalculationProfile).where(
                    EnterpriseComponentCalculationProfile.tenant_id == self.tenant_id,
                    EnterpriseComponentCalculationProfile.reference_resource_id == component.source_reference_resource_id,
                )) if component.source_reference_resource_id else None
                component.calculation_basis = profile.calculation_basis if profile else "quantity_unit_price"
                component.consumption = component.source_consumption
                component.enterprise_direct_amount = component.source_direct_amount
                component.calculation_base = None
                component.enterprise_rate = None
                component.formula_code = None
                component.formula_version = None
                component.specification_override = None
                component.lifecycle_status = "active"
                component.component_status = "restored"
                if component.calculation_basis == "quantity_unit_price":
                    self._set_component_resource_price(component, component.enterprise_resource_id)
                else:
                    component.enterprise_price_version_id = None
                    component.selected_enterprise_price = None
                    component.selected_price_type = None
                field_name, change_type = "component", "restored"
            else:
                validation_error(component_key, str(change.get("field_name")), "unsupported_change", "不支持的批量组件变更类型。")

            component.override_reason = reason
            component.updated_by = context.user.app_user_id
            component.correlation_id = request_id
            self._recalculate_component(component)
            if component.enterprise_component_amount is None:
                validation_error(component_key, field_name, "calculation_blocked", component.amount_source)
            after = self._component_snapshot(component)
            applied.append((component, change_type, field_name, before, after, reason))

        before_payload = {"components": [
            {"component_id": str(component.enterprise_quota_component_version_id), "field_name": field, "value": before}
            for component, _, field, before, _, _ in applied
        ]}
        after_payload = {"components": [
            {"component_id": str(component.enterprise_quota_component_version_id), "field_name": field, "value": after}
            for component, _, field, _, after, _ in applied
        ]}
        change_set = self._new_change_set(
            quota, before_payload, after_payload, "component_batch_modified", payload["change_reason"],
            payload["idempotency_key"], context, request_id,
        )
        target.change_set_id = change_set.enterprise_quota_change_set_id
        target.change_reason = payload["change_reason"]
        target.updated_by = context.user.app_user_id
        target.correlation_id = request_id
        for component, change_type, field_name, before, after, reason in applied:
            self._record_component_change(
                version=target, component=component, change_set=change_set, change_type=change_type,
                field_name=field_name, before=before, after=after, reason=reason,
                idempotency_key=payload["idempotency_key"], context=context, request_id=request_id,
            )
        self._audit(
            context, "enterprise_quota_component_batch_saved", target_id,
            before_payload, after_payload, request_id,
        )
        self.session.flush()
        self.session.refresh(target)
        return {
            "status": "draft", "enterprise_quota_version_id": str(target_id),
            "row_version": target.row_version, "saved_change_count": len(applied),
            "save_as_new": bool(payload.get("save_as_new")), "client_component_map": client_component_map,
            "change_set": self._change_payload(change_set), "detail": self.detail(target_id),
        }

    def detail(self, version_id: uuid.UUID) -> dict[str, Any]:
        version, quota, reference = self._version_context(version_id)
        component_rows = self.session.execute(
            select(EnterpriseQuotaComponentVersion, EnterpriseResource)
            .join(EnterpriseResource, EnterpriseResource.enterprise_resource_id == EnterpriseQuotaComponentVersion.enterprise_resource_id)
            .where(EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version_id)
            .order_by(EnterpriseQuotaComponentVersion.line_no)
        ).all()
        resource_ids = {resource.enterprise_resource_id for _, resource in component_rows}
        price_rows = list(self.session.scalars(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.tenant_id == self.tenant_id,
            EnterprisePriceVersion.enterprise_resource_id.in_(resource_ids),
        ).order_by(EnterprisePriceVersion.enterprise_resource_id, EnterprisePriceVersion.version_no))) if resource_ids else []
        prices_by_resource: dict[uuid.UUID, list[EnterprisePriceVersion]] = {}
        for price in price_rows:
            prices_by_resource.setdefault(price.enterprise_resource_id, []).append(price)
        components: list[dict[str, Any]] = []
        for component, resource in component_rows:
            history = prices_by_resource.get(resource.enterprise_resource_id, [])
            selected_price = next((row for row in history if row.enterprise_price_version_id == component.enterprise_price_version_id), None)
            fallback_price = next((row for row in history if row.version_type == "provincial_reference_fallback"), None)
            row = component_comparison({
                "enterprise_quota_component_version_id": str(component.enterprise_quota_component_version_id),
                "line_no": component.line_no,
                "enterprise_resource_id": str(resource.enterprise_resource_id),
                "source_enterprise_resource_id": str(component.source_enterprise_resource_id) if component.source_enterprise_resource_id else None,
                "source_reference_resource_id": str(component.source_reference_resource_id) if component.source_reference_resource_id else None,
                "resource_code": resource.resource_code,
                "resource_name": resource.resource_name,
                "specification": component.specification_override or resource.specification,
                "master_specification": resource.specification,
                "specification_override": component.specification_override,
                "unit": resource.unit,
                "resource_category": resource.resource_category,
                "source_consumption": component.source_consumption,
                "consumption": component.consumption,
                "provincial_unit_price": component.provincial_unit_price,
                "provincial_component_amount": component.provincial_component_amount,
                "selected_enterprise_price": component.selected_enterprise_price,
                "selected_price_type": component.selected_price_type,
                "calculation_basis": component.calculation_basis,
                "source_direct_amount": component.source_direct_amount,
                "enterprise_direct_amount": component.enterprise_direct_amount,
                "calculation_base": component.calculation_base,
                "enterprise_rate": component.enterprise_rate,
                "formula_code": component.formula_code,
                "formula_version": component.formula_version,
                "component_status": component.component_status,
                "lifecycle_status": component.lifecycle_status,
                "provincial_fallback_price": fallback_price.price_value if fallback_price else None,
                "enterprise_manual_price": selected_price.price_value if selected_price and selected_price.price_source_type == "enterprise_manual_price" else None,
                "price_source_type": selected_price.price_source_type if selected_price else "provincial_reference_price_missing",
                "pricing_review_status": selected_price.pricing_review_status if selected_price else "provincial_reference_price_missing",
                "is_fallback": selected_price.is_fallback if selected_price else False,
                "requires_manual_review": selected_price.requires_manual_review if selected_price else True,
                "price_effective_from": selected_price.effective_from if selected_price else None,
                "price_tax_mode": selected_price.tax_mode if selected_price else None,
                "price_region": selected_price.region if selected_price else None,
                "adjustment_reason": selected_price.fallback_reason if selected_price else "Reference price missing; manual price required.",
                "enterprise_price_version_no": selected_price.version_no if selected_price else None,
                "price_row_version": selected_price.row_version if selected_price else None,
                "price_version_history": [self._price_payload(item) for item in reversed(history)],
                "amount_source": component.amount_source,
                "override_reason": component.override_reason,
                "row_version": component.row_version,
            })
            components.append(row)
        cost_summary = summarize_components(
            components,
            reference_total_fee=reference.total_fee,
            management_fee=reference.management_fee,
        )
        pending_resources = {
            component["enterprise_resource_id"] for component in components if component["requires_manual_review"]
        }
        confirmed_resources = {
            component["enterprise_resource_id"] for component in components
            if component["price_source_type"] == "enterprise_manual_price"
            and component["pricing_review_status"] == "manual_price_reviewed"
        }
        cost_summary["pending_manual_pricing_resource_count"] = len(pending_resources)
        cost_summary["enterprise_confirmed_price_resource_count"] = len(confirmed_resources)
        calculation_blockers = (
            cost_summary["missing_price_component_count"]
            + cost_summary["missing_direct_amount_count"]
            + cost_summary["formula_error_count"]
            + cost_summary["unclassified_component_count"]
        )
        if calculation_blockers:
            cost_summary["calculation_status"] = "incomplete_missing_reference_price"
        elif components and all(
            component["price_source_type"] == "enterprise_manual_price"
            and component["pricing_review_status"] == "manual_price_reviewed"
            for component in components
        ):
            cost_summary["calculation_status"] = "complete_with_enterprise_price"
        else:
            cost_summary["calculation_status"] = "complete_with_provincial_fallback"
        cost_summary["internal_historical_observation"] = None
        cost_summary["internal_observation_difference"] = None
        rules = list(self.session.scalars(select(EnterpriseQuotaRuleVersion).where(
            EnterpriseQuotaRuleVersion.enterprise_quota_version_id == version_id
        ).order_by(EnterpriseQuotaRuleVersion.rule_type, EnterpriseQuotaRuleVersion.ordinal)))
        changes = list(self.session.scalars(select(EnterpriseQuotaChangeSet).where(
            EnterpriseQuotaChangeSet.enterprise_quota_id == quota.enterprise_quota_id,
            EnterpriseQuotaChangeSet.tenant_id == self.tenant_id,
        ).order_by(EnterpriseQuotaChangeSet.change_set_no.desc())))
        history = list(self.session.scalars(select(EnterpriseQuotaVersion).where(
            EnterpriseQuotaVersion.enterprise_quota_id == quota.enterprise_quota_id,
            EnterpriseQuotaVersion.tenant_id == self.tenant_id,
        ).order_by(EnterpriseQuotaVersion.version_no.desc())))
        events = list(self.session.scalars(select(EnterpriseQuotaReviewEvent).where(
            EnterpriseQuotaReviewEvent.enterprise_quota_version_id.in_([item.enterprise_quota_version_id for item in history])
        ).order_by(EnterpriseQuotaReviewEvent.created_at.desc()))) if history else []
        component_changes = list(self.session.scalars(select(EnterpriseQuotaComponentChange).where(
            EnterpriseQuotaComponentChange.tenant_id == self.tenant_id,
            EnterpriseQuotaComponentChange.quota_version_id == version_id,
        ).order_by(EnterpriseQuotaComponentChange.changed_at.desc())))
        return {
            "quota": {
                "enterprise_quota_id": str(quota.enterprise_quota_id),
                "enterprise_quota_code": quota.enterprise_quota_code,
                "quota_name": quota.quota_name,
                "unit": quota.unit,
                "status": value(quota.status),
            },
            "version": {
                "enterprise_quota_version_id": str(version.enterprise_quota_version_id),
                "source_reference_release_id": version.reference_release_id,
                "source_quota_uid": version.source_quota_uid,
                "source_quota_code": version.source_quota_code,
                "source_quota_version_hash": version.source_quota_version_hash,
                "enterprise_quota_version_no": version.version_no,
                "status": value(version.state),
                "unit": version.unit,
                "work_content": version.work_content,
                "enterprise_note": version.enterprise_note,
                "change_reason": version.change_reason,
                "calculation_rule_version": version.calculation_rule_version,
                "created_by": str(version.created_by) if version.created_by else None,
                "created_at": version.created_at,
                "row_version": version.row_version,
            },
            "reference": {
                "reference_quota_item_id": str(reference.reference_quota_item_id),
                "source_code": reference.source_code,
                "quota_name": reference.quota_name,
                "unit": reference.unit,
                "pdf_page_no": reference.pdf_page_no,
                "labor_fee": reference.labor_fee,
                "material_fee": reference.material_fee,
                "machine_fee": reference.machine_fee,
                "management_fee": reference.management_fee,
                "total_fee": reference.total_fee,
            },
            "components": components,
            "cost_summary": cost_summary,
            "rules": [{
                "enterprise_quota_rule_version_id": str(rule.enterprise_quota_rule_version_id),
                "rule_type": rule.rule_type,
                "ordinal": rule.ordinal,
                "rule_text": rule.rule_text,
                "enterprise_reason": rule.enterprise_reason,
            } for rule in rules],
            "change_sets": [self._change_payload(row) for row in changes],
            "component_changes": [{
                "component_change_id": str(row.component_change_id),
                "component_id": str(row.component_id),
                "change_set_id": str(row.change_set_id),
                "change_type": row.change_type,
                "field_name": row.field_name,
                "before_value": row.before_value,
                "after_value": row.after_value,
                "change_reason": row.change_reason,
                "changed_by": str(row.changed_by),
                "changed_at": row.changed_at,
                "request_id": str(row.request_id),
                "review_status": row.review_status,
            } for row in component_changes],
            "review_events": [{
                "event_id": str(row.enterprise_quota_review_event_id),
                "from_state": row.from_state,
                "to_state": row.to_state,
                "comment": row.comment,
                "created_at": row.created_at,
            } for row in events],
            "version_history": [{
                "enterprise_quota_version_id": str(row.enterprise_quota_version_id),
                "version_no": row.version_no,
                "status": value(row.state),
                "change_reason": row.change_reason,
                "created_at": row.created_at,
                "row_version": row.row_version,
            } for row in history],
        }

    def diff(self, left_id: uuid.UUID, right_id: uuid.UUID) -> dict[str, Any]:
        left = self.detail(left_id)
        right = self.detail(right_id)
        if left["quota"]["enterprise_quota_id"] != right["quota"]["enterprise_quota_id"]:
            raise EnterpriseQuotaValidation("Versions must belong to the same Enterprise Quota")
        fields = ("unit", "work_content", "enterprise_note", "change_reason")
        changes = [{"field": field, "before": left["version"][field], "after": right["version"][field]}
                   for field in fields if left["version"][field] != right["version"][field]]
        left_components = {row["line_no"]: row for row in left["components"]}
        right_components = {row["line_no"]: row for row in right["components"]}
        component_changes = []
        for line_no in sorted(set(left_components) | set(right_components)):
            before, after = left_components.get(line_no), right_components.get(line_no)
            if before != after:
                component_changes.append({"line_no": line_no, "before": before, "after": after})
        return {"field_changes": changes, "component_changes": component_changes}

    def save_draft(
        self,
        version_id: uuid.UUID,
        payload: dict[str, Any],
        context: AuthContext,
        request_id: uuid.UUID,
    ) -> dict[str, Any]:
        version, quota, _ = self._version_context(version_id, for_update=True)
        self._require_row_version(version, payload["row_version"])
        if value(version.state) != "draft":
            raise EnterpriseQuotaConflict("Only Draft versions can be edited")
        existing = self.session.scalar(select(EnterpriseQuotaChangeSet).where(
            EnterpriseQuotaChangeSet.tenant_id == self.tenant_id,
            EnterpriseQuotaChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            return {"status": "idempotent", "change_set": self._change_payload(existing)}
        before = self._editable_snapshot(version, quota)
        self._apply_changes(version, quota, payload.get("changes") or {})
        after = self._editable_snapshot(version, quota)
        change_set = self._new_change_set(
            quota, before, after, payload["change_type"], payload["change_reason"],
            payload["idempotency_key"], context, request_id,
        )
        version.change_set_id = change_set.enterprise_quota_change_set_id
        version.change_reason = payload["change_reason"]
        version.updated_by = context.user.app_user_id
        self._audit(context, "enterprise_quota_draft_saved", version_id, before, after, request_id)
        self.session.flush()
        return {"status": "draft", "change_set": self._change_payload(change_set)}

    def save_as_new(
        self,
        version_id: uuid.UUID,
        payload: dict[str, Any],
        context: AuthContext,
        request_id: uuid.UUID,
    ) -> dict[str, Any]:
        source, quota, _ = self._version_context(version_id, for_update=True)
        self._require_row_version(source, payload["row_version"])
        existing = self.session.scalar(select(EnterpriseQuotaChangeSet).where(
            EnterpriseQuotaChangeSet.tenant_id == self.tenant_id,
            EnterpriseQuotaChangeSet.idempotency_key == payload["idempotency_key"],
        ))
        if existing is not None:
            version = self.session.scalar(select(EnterpriseQuotaVersion).where(
                EnterpriseQuotaVersion.change_set_id == existing.enterprise_quota_change_set_id
            ))
            return {"status": "idempotent", "enterprise_quota_version_id": str(version.enterprise_quota_version_id)}
        clone = self._clone_version(source, quota, payload["change_reason"], context.user.app_user_id)
        before = self._editable_snapshot(source, quota)
        self._apply_changes(clone, quota, payload.get("changes") or {})
        after = self._editable_snapshot(clone, quota)
        change_set = self._new_change_set(
            quota, before, after, payload["change_type"], payload["change_reason"],
            payload["idempotency_key"], context, request_id,
        )
        clone.change_set_id = change_set.enterprise_quota_change_set_id
        self._audit(context, "enterprise_quota_new_version_saved", clone.enterprise_quota_version_id, before, after, request_id)
        self.session.flush()
        return {"status": "draft", "enterprise_quota_version_id": str(clone.enterprise_quota_version_id), "version_no": clone.version_no}

    def transition(
        self,
        version_id: uuid.UUID,
        *,
        expected: tuple[str, ...],
        target: str,
        row_version: int,
        comment: str,
        idempotency_key: str,
        context: AuthContext,
        request_id: uuid.UUID,
    ) -> dict[str, Any]:
        version, _, _ = self._version_context(version_id, for_update=True)
        current = value(version.state)
        if current == target:
            return {"status": "idempotent", "state": target, "row_version": version.row_version}
        self._require_row_version(version, row_version)
        if current not in expected:
            raise EnterpriseQuotaConflict(f"Transition {current} -> {target} is not allowed")
        if target == "reviewed" and (
            version.created_by == context.user.app_user_id
            or version.updated_by == context.user.app_user_id
            or self.session.scalar(select(func.count()).select_from(EnterpriseQuotaComponentChange).where(
                EnterpriseQuotaComponentChange.tenant_id == self.tenant_id,
                EnterpriseQuotaComponentChange.quota_version_id == version_id,
                EnterpriseQuotaComponentChange.changed_by == context.user.app_user_id,
            ))
        ):
            raise EnterpriseQuotaValidation("Reviewer cannot review a version they created or modified")
        if target == "approved":
            detail = self.detail(version_id)
            if detail["cost_summary"]["missing_enterprise_price_resource_count"]:
                raise EnterpriseQuotaValidation("Enterprise prices must be complete before approval")
            confirmed_sources = int(self.session.scalar(select(func.count()).select_from(
                EnterprisePriceSourceDocument
            ).where(
                EnterprisePriceSourceDocument.tenant_id == self.tenant_id,
                EnterprisePriceSourceDocument.authority_status == "confirmed",
            )) or 0)
            if confirmed_sources == 0:
                raise EnterpriseQuotaValidation("Enterprise price source authority is not confirmed")
        before = {"state": current, "row_version": version.row_version}
        version.state = EnterpriseQuotaState(target)
        if target == "submitted":
            version.submitted_by = context.user.app_user_id
        elif target == "reviewed":
            version.reviewed_by = context.user.app_user_id
        elif target == "approved":
            version.approved_by = context.user.app_user_id
        elif target == "draft":
            version.reviewed_by = None
        version.updated_by = context.user.app_user_id
        event = EnterpriseQuotaReviewEvent(
            enterprise_quota_review_event_id=uuid.uuid4(),
            enterprise_quota_version_id=version_id,
            actor_user_id=context.user.app_user_id,
            from_state=current,
            to_state=target,
            comment=comment,
            evidence_payload={"idempotency_key": idempotency_key, "request_id": str(request_id)},
            tenant_id=self.tenant_id,
            created_by=context.user.app_user_id,
            updated_by=context.user.app_user_id,
            correlation_id=request_id,
        )
        self.session.add(event)
        self._audit(context, f"enterprise_quota_{target}", version_id, before, {"state": target}, request_id)
        self.session.flush()
        return {"status": target, "state": target, "row_version": version.row_version}

    def restore(
        self,
        version_id: uuid.UUID,
        *,
        row_version: int,
        change_reason: str,
        idempotency_key: str,
        context: AuthContext,
        request_id: uuid.UUID,
    ) -> dict[str, Any]:
        return self.save_as_new(version_id, {
            "row_version": row_version,
            "change_type": "restore_draft_version",
            "change_reason": change_reason,
            "idempotency_key": idempotency_key,
            "changes": {},
        }, context, request_id)

    def _version_context(self, version_id: uuid.UUID, *, for_update: bool = False):
        statement = (
            select(EnterpriseQuotaVersion, EnterpriseQuota, ReferenceQuotaItem)
            .join(EnterpriseQuota, EnterpriseQuota.enterprise_quota_id == EnterpriseQuotaVersion.enterprise_quota_id)
            .join(ReferenceQuotaItem, ReferenceQuotaItem.reference_quota_item_id == EnterpriseQuota.source_reference_quota_id)
            .where(
                EnterpriseQuotaVersion.enterprise_quota_version_id == version_id,
                EnterpriseQuotaVersion.tenant_id == self.tenant_id,
                EnterpriseQuota.tenant_id == self.tenant_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        row = self.session.execute(statement).one_or_none()
        if row is None:
            raise EnterpriseQuotaNotFound("Enterprise Quota version not found")
        return row

    @staticmethod
    def _require_row_version(version: EnterpriseQuotaVersion, supplied: int) -> None:
        if version.row_version != supplied:
            raise EnterpriseQuotaConflict(f"row_version conflict: current={version.row_version}")

    def _editable_snapshot(self, version: EnterpriseQuotaVersion, quota: EnterpriseQuota) -> dict[str, Any]:
        components = list(self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id
        ).order_by(EnterpriseQuotaComponentVersion.line_no)))
        rules = list(self.session.scalars(select(EnterpriseQuotaRuleVersion).where(
            EnterpriseQuotaRuleVersion.enterprise_quota_version_id == version.enterprise_quota_version_id
        ).order_by(EnterpriseQuotaRuleVersion.rule_type, EnterpriseQuotaRuleVersion.ordinal)))
        return {
            "quota_name": quota.quota_name,
            "unit": version.unit,
            "work_content": version.work_content,
            "enterprise_note": version.enterprise_note,
            "components": [{
                "line_no": row.line_no,
                "enterprise_resource_id": str(row.enterprise_resource_id),
                "consumption": str(row.consumption),
                "enterprise_price_version_id": str(row.enterprise_price_version_id) if row.enterprise_price_version_id else None,
                "selected_enterprise_price": str(row.selected_enterprise_price) if row.selected_enterprise_price is not None else None,
            } for row in components],
            "rules": [{
                "rule_type": row.rule_type,
                "ordinal": row.ordinal,
                "rule_text": row.rule_text,
                "enterprise_reason": row.enterprise_reason,
            } for row in rules],
        }

    def _apply_changes(self, version: EnterpriseQuotaVersion, quota: EnterpriseQuota, changes: dict[str, Any]) -> None:
        if changes.get("components"):
            raise EnterpriseQuotaValidation("Use governed component endpoints for component mutations")
        if "quota_name" in changes:
            quota.quota_name = str(changes["quota_name"]).strip()
        if "unit" in changes:
            version.unit = str(changes["unit"]).strip()
            quota.unit = version.unit
        if "work_content" in changes:
            version.work_content = str(changes["work_content"])
        if "enterprise_note" in changes:
            version.enterprise_note = str(changes["enterprise_note"])
        for item in changes.get("components", []):
            action = item.get("action", "update")
            line_no = int(item["line_no"])
            component = self.session.scalar(select(EnterpriseQuotaComponentVersion).where(
                EnterpriseQuotaComponentVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
                EnterpriseQuotaComponentVersion.line_no == line_no,
            ))
            if action == "add":
                if component is not None:
                    raise EnterpriseQuotaValidation(f"Component line {line_no} already exists")
                resource_id = uuid.UUID(str(item["enterprise_resource_id"]))
                self._resource(resource_id)
                consumption = Decimal(str(item.get("consumption", "0")))
                component = EnterpriseQuotaComponentVersion(
                    enterprise_quota_component_version_id=uuid.uuid4(),
                    enterprise_quota_version_id=version.enterprise_quota_version_id,
                    enterprise_resource_id=resource_id,
                    source_reference_resource_id=None,
                    line_no=line_no,
                    consumption=consumption,
                    source_consumption=Decimal("0"),
                    amount_source="enterprise_price_missing",
                    override_reason=item.get("override_reason") or "enterprise_component_added",
                    created_by=version.updated_by or version.created_by,
                    updated_by=version.updated_by or version.created_by,
                    correlation_id=version.correlation_id,
                )
                self.session.add(component)
            elif component is None:
                raise EnterpriseQuotaNotFound(f"Component line {line_no} not found")
            elif action == "delete":
                component.lifecycle_status = "removed"
                component.component_status = "resource_removed"
                self._recalculate_component(component)
                continue
            if "enterprise_resource_id" in item and action != "add":
                resource_id = uuid.UUID(str(item["enterprise_resource_id"]))
                self._resource(resource_id)
                component.enterprise_resource_id = resource_id
            if "consumption" in item:
                component.consumption = Decimal(str(item["consumption"]))
            if "enterprise_price_version_id" in item:
                price_id = item["enterprise_price_version_id"]
                if price_id:
                    price = self._price(uuid.UUID(str(price_id)), component.enterprise_resource_id)
                    component.enterprise_price_version_id = price.enterprise_price_version_id
                    component.selected_enterprise_price = price.price_value
                    component.selected_price_type = price.price_type
                    component.enterprise_component_amount = authoritative_amount(component.consumption, price.price_value)
                    component.amount_source = "enterprise_draft_price"
                else:
                    component.enterprise_price_version_id = None
                    component.selected_enterprise_price = None
                    component.selected_price_type = None
                    component.enterprise_component_amount = None
                    component.amount_source = "enterprise_price_missing"
            if item.get("override_reason"):
                component.override_reason = str(item["override_reason"])
        if changes.get("conversion_rule"):
            ordinal = int(self.session.scalar(select(func.max(EnterpriseQuotaRuleVersion.ordinal)).where(
                EnterpriseQuotaRuleVersion.enterprise_quota_version_id == version.enterprise_quota_version_id,
                EnterpriseQuotaRuleVersion.rule_type == "enterprise_conversion",
            )) or 0) + 1
            self.session.add(EnterpriseQuotaRuleVersion(
                enterprise_quota_rule_version_id=uuid.uuid4(),
                enterprise_quota_version_id=version.enterprise_quota_version_id,
                source_rule_block_id=None,
                rule_type="enterprise_conversion",
                ordinal=ordinal,
                rule_text=str(changes["conversion_rule"]),
                enterprise_reason=str(changes.get("conversion_rule_reason") or ""),
                created_by=version.updated_by or version.created_by,
                updated_by=version.updated_by or version.created_by,
                correlation_id=version.correlation_id,
            ))

    def _resource(self, resource_id: uuid.UUID) -> EnterpriseResource:
        resource = self.session.scalar(select(EnterpriseResource).where(
            EnterpriseResource.enterprise_resource_id == resource_id,
            EnterpriseResource.tenant_id == self.tenant_id,
        ))
        if resource is None:
            raise EnterpriseQuotaNotFound("Enterprise Resource not found")
        return resource

    def _price(self, price_id: uuid.UUID, resource_id: uuid.UUID) -> EnterprisePriceVersion:
        price = self.session.scalar(select(EnterprisePriceVersion).where(
            EnterprisePriceVersion.enterprise_price_version_id == price_id,
            EnterprisePriceVersion.enterprise_resource_id == resource_id,
            EnterprisePriceVersion.tenant_id == self.tenant_id,
        ))
        if price is None:
            raise EnterpriseQuotaNotFound("Enterprise Price version not found for this resource")
        if value(price.review_status) in {"rejected", "superseded"}:
            raise EnterpriseQuotaValidation("Rejected or superseded price cannot be selected")
        return price

    def _clone_version(
        self, source: EnterpriseQuotaVersion, quota: EnterpriseQuota, reason: str, actor_id: uuid.UUID
    ) -> EnterpriseQuotaVersion:
        version_no = int(self.session.scalar(select(func.max(EnterpriseQuotaVersion.version_no)).where(
            EnterpriseQuotaVersion.enterprise_quota_id == quota.enterprise_quota_id
        )) or 0) + 1
        placeholder_change_set_id = source.change_set_id
        clone = EnterpriseQuotaVersion(
            enterprise_quota_version_id=uuid.uuid4(),
            enterprise_quota_id=quota.enterprise_quota_id,
            reference_release_id=source.reference_release_id,
            predecessor_id=source.enterprise_quota_version_id,
            change_set_id=placeholder_change_set_id,
            version_no=version_no,
            source_quota_uid=source.source_quota_uid,
            source_quota_code=source.source_quota_code,
            source_quota_version_hash=source.source_quota_version_hash,
            unit=source.unit,
            work_content=source.work_content,
            enterprise_note=source.enterprise_note,
            change_reason=reason,
            calculation_rule_version=source.calculation_rule_version,
            state=EnterpriseQuotaState.draft,
            tenant_id=self.tenant_id,
            created_by=actor_id,
            updated_by=actor_id,
            correlation_id=uuid.uuid4(),
        )
        self.session.add(clone)
        self.session.flush()
        for row in self.session.scalars(select(EnterpriseQuotaComponentVersion).where(
            EnterpriseQuotaComponentVersion.enterprise_quota_version_id == source.enterprise_quota_version_id
        ).order_by(EnterpriseQuotaComponentVersion.line_no)):
            self.session.add(EnterpriseQuotaComponentVersion(
                enterprise_quota_component_version_id=uuid.uuid4(),
                enterprise_quota_version_id=clone.enterprise_quota_version_id,
                enterprise_resource_id=row.enterprise_resource_id,
                source_reference_resource_id=row.source_reference_resource_id,
                source_enterprise_resource_id=row.source_enterprise_resource_id,
                line_no=row.line_no,
                consumption=row.consumption,
                source_consumption=row.source_consumption,
                provincial_unit_price=row.provincial_unit_price,
                provincial_component_amount=row.provincial_component_amount,
                enterprise_price_version_id=row.enterprise_price_version_id,
                selected_enterprise_price=row.selected_enterprise_price,
                selected_price_type=row.selected_price_type,
                enterprise_component_amount=row.enterprise_component_amount,
                amount_source=row.amount_source,
                override_reason=row.override_reason,
                calculation_basis=row.calculation_basis,
                source_direct_amount=row.source_direct_amount,
                enterprise_direct_amount=row.enterprise_direct_amount,
                calculation_base=row.calculation_base,
                enterprise_rate=row.enterprise_rate,
                formula_code=row.formula_code,
                formula_version=row.formula_version,
                component_status=row.component_status,
                lifecycle_status=row.lifecycle_status,
                specification_override=row.specification_override,
                created_by=actor_id,
                updated_by=actor_id,
                correlation_id=clone.correlation_id,
            ))
        for row in self.session.scalars(select(EnterpriseQuotaRuleVersion).where(
            EnterpriseQuotaRuleVersion.enterprise_quota_version_id == source.enterprise_quota_version_id
        )):
            self.session.add(EnterpriseQuotaRuleVersion(
                enterprise_quota_rule_version_id=uuid.uuid4(),
                enterprise_quota_version_id=clone.enterprise_quota_version_id,
                source_rule_block_id=row.source_rule_block_id,
                rule_type=row.rule_type,
                ordinal=row.ordinal,
                rule_text=row.rule_text,
                enterprise_reason=row.enterprise_reason,
                created_by=actor_id,
                updated_by=actor_id,
                correlation_id=clone.correlation_id,
            ))
        return clone

    def _new_change_set(
        self,
        quota: EnterpriseQuota,
        before: dict[str, Any],
        after: dict[str, Any],
        change_type: str,
        reason: str,
        idempotency_key: str,
        context: AuthContext,
        request_id: uuid.UUID,
    ) -> EnterpriseQuotaChangeSet:
        number = int(self.session.scalar(select(func.max(EnterpriseQuotaChangeSet.change_set_no)).where(
            EnterpriseQuotaChangeSet.enterprise_quota_id == quota.enterprise_quota_id
        )) or 0) + 1
        row = EnterpriseQuotaChangeSet(
            enterprise_quota_change_set_id=uuid.uuid4(),
            enterprise_quota_id=quota.enterprise_quota_id,
            change_set_no=number,
            business_reason=reason,
            change_payload={"change_type": change_type, "before": before, "after": after},
            status="draft",
            before_value=before,
            after_value=after,
            change_type=change_type,
            change_reason=reason,
            changed_by=context.user.app_user_id,
            changed_at=datetime.now(timezone.utc),
            request_id=request_id,
            idempotency_key=idempotency_key,
            tenant_id=self.tenant_id,
            created_by=context.user.app_user_id,
            updated_by=context.user.app_user_id,
            correlation_id=request_id,
        )
        self.session.add(row)
        self.session.flush()
        return row

    @staticmethod
    def _change_payload(row: EnterpriseQuotaChangeSet) -> dict[str, Any]:
        return {
            "enterprise_quota_change_set_id": str(row.enterprise_quota_change_set_id),
            "change_set_no": row.change_set_no,
            "change_type": row.change_type,
            "change_reason": row.change_reason,
            "before_value": row.before_value,
            "after_value": row.after_value,
            "changed_by": str(row.changed_by) if row.changed_by else None,
            "changed_at": row.changed_at,
            "request_id": str(row.request_id) if row.request_id else None,
            "status": row.status,
        }

    def _audit(
        self,
        context: AuthContext,
        event_type: str,
        subject_id: uuid.UUID,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        request_id: uuid.UUID,
    ) -> None:
        json_before = json.loads(json.dumps(before, default=str)) if before is not None else None
        json_after = json.loads(json.dumps(after, default=str)) if after is not None else None
        self.session.add(SystemAuditEvent(
            system_audit_event_id=uuid.uuid4(),
            actor_user_id=context.user.app_user_id,
            release_manifest_id=None,
            event_type=event_type,
            subject_type="enterprise_quota_version",
            subject_id=str(subject_id),
            before_payload=json_before,
            after_payload=json_after,
            tenant_id=self.tenant_id,
            created_by=context.user.app_user_id,
            updated_by=context.user.app_user_id,
            correlation_id=request_id,
        ))
