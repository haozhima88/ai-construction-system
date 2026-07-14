from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_db.dependencies import get_db_session, require_csrf, require_permission
from platform_db.repositories import (
    EnterpriseQuotaBatchConflict,
    EnterpriseQuotaConflict,
    EnterpriseQuotaFieldValidation,
    EnterpriseQuotaNotFound,
    EnterpriseQuotaRepository,
    EnterpriseQuotaValidation,
)
from platform_db.services.authentication import AuthContext


router = APIRouter(prefix="/api/v1/enterprise-quota", tags=["enterprise-quota-pilot"])


class DraftSaveRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    change_type: str = Field(min_length=1, max_length=64)
    change_reason: str = Field(min_length=1, max_length=2000)
    changes: dict[str, Any] = Field(default_factory=dict)


class TransitionRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    comment: str = Field(default="", max_length=4000)


class RestoreRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    change_reason: str = Field(min_length=1, max_length=2000)


class ManualPriceRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    price_value: Decimal = Field(ge=0)
    tax_mode: str = Field(min_length=1, max_length=32)
    region: str = Field(min_length=1, max_length=128)
    effective_from: datetime
    change_reason: str = Field(min_length=1, max_length=2000)


class PriceActionRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    change_reason: str = Field(min_length=1, max_length=2000)


class PriceReviewRequest(PriceActionRequest):
    action: str = Field(default="review", pattern="^(review|return)$")


class ComponentAddRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    change_reason: str = Field(min_length=1, max_length=2000)
    enterprise_resource_id: uuid.UUID
    calculation_basis: str = Field(pattern="^(quantity_unit_price|direct_amount|rate_based|formula_based)$")
    enterprise_quantity: Decimal | None = Field(default=None, ge=0)
    enterprise_direct_amount: Decimal | None = Field(default=None, ge=0)
    calculation_base: Decimal | None = Field(default=None, ge=0)
    enterprise_rate: Decimal | None = Field(default=None, ge=0)
    formula_code: str | None = Field(default=None, max_length=128)
    formula_version: str | None = Field(default=None, max_length=64)
    specification: str | None = Field(default=None, max_length=2000)


class ComponentMutationRequest(BaseModel):
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)
    change_reason: str = Field(min_length=1, max_length=2000)
    action: str = Field(pattern="^(edit_quantity|edit_direct_amount|replace_resource|remove_resource|restore_reference|edit_specification)$")
    enterprise_resource_id: uuid.UUID | None = None
    calculation_basis: str | None = Field(default=None, pattern="^(quantity_unit_price|direct_amount|rate_based|formula_based)$")
    enterprise_quantity: Decimal | None = Field(default=None, ge=0)
    enterprise_direct_amount: Decimal | None = Field(default=None, ge=0)
    calculation_base: Decimal | None = Field(default=None, ge=0)
    enterprise_rate: Decimal | None = Field(default=None, ge=0)
    formula_code: str | None = Field(default=None, max_length=128)
    formula_version: str | None = Field(default=None, max_length=64)
    specification: str | None = Field(default=None, max_length=2000)


class ComponentBatchChangeRequest(BaseModel):
    component_id: uuid.UUID | None = None
    client_component_id: str | None = Field(default=None, max_length=128)
    field_name: str = Field(min_length=1, max_length=128)
    before_value: Any = None
    after_value: Any = None
    change_type: str = Field(
        pattern="^(quantity_modified|amount_modified|specification_modified|resource_added|resource_replaced|resource_removed|restored)$"
    )
    reason: str = Field(min_length=1, max_length=2000)


class ComponentBatchRequest(BaseModel):
    base_row_version: int = Field(ge=1)
    changes: list[ComponentBatchChangeRequest] = Field(min_length=1, max_length=500)
    change_reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=180)
    save_as_new: bool = False


def request_id(request: Request) -> uuid.UUID:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, uuid.UUID) else uuid.uuid4()


def translate(exc: Exception) -> HTTPException:
    if isinstance(exc, EnterpriseQuotaBatchConflict):
        return HTTPException(409, {
            "code": "row_version_conflict",
            "message": str(exc),
            "current_row_version": exc.current_row_version,
        })
    if isinstance(exc, EnterpriseQuotaFieldValidation):
        return HTTPException(422, {
            "code": "field_validation_failed",
            "message": str(exc),
            "field_errors": exc.field_errors,
        })
    if isinstance(exc, EnterpriseQuotaNotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, EnterpriseQuotaConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, EnterpriseQuotaValidation):
        return HTTPException(400, str(exc))
    return HTTPException(500, "Enterprise Quota operation failed")


@router.get("/summary")
def summary(
    context: AuthContext = Depends(require_permission("enterprise_quota.read")),
    db: Session = Depends(get_db_session),
):
    return EnterpriseQuotaRepository(db, context.tenant_id).summary()


@router.get("/tree")
def tree(
    context: AuthContext = Depends(require_permission("enterprise_quota.read")),
    db: Session = Depends(get_db_session),
):
    return EnterpriseQuotaRepository(db, context.tenant_id).tree()


@router.get("/price-sources")
def price_sources(
    context: AuthContext = Depends(require_permission("enterprise_price.read")),
    db: Session = Depends(get_db_session),
):
    return EnterpriseQuotaRepository(db, context.tenant_id).price_sources()


@router.get("/prices")
def price_workbench(
    filter: str = "all",
    threshold_percentage: Decimal = Decimal("20"),
    context: AuthContext = Depends(require_permission("enterprise_price.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).price_workbench(filter, threshold_percentage)
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/prices/resources/{resource_id}/manual")
def create_manual_price(
    resource_id: uuid.UUID,
    payload: ManualPriceRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_price.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).create_manual_price(
            resource_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/prices/{price_id}/accept-fallback")
def accept_fallback(
    price_id: uuid.UUID,
    payload: PriceActionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_price.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).accept_fallback(
            price_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/prices/resources/{resource_id}/restore-fallback")
def restore_fallback(
    resource_id: uuid.UUID,
    payload: PriceActionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_price.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).restore_fallback(
            resource_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/prices/{price_id}/review")
def review_price(
    price_id: uuid.UUID,
    payload: PriceReviewRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_price.review")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).review_price(
            price_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.get("/versions/{version_id}")
def detail(
    version_id: uuid.UUID,
    context: AuthContext = Depends(require_permission("enterprise_quota.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).detail(version_id)
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/components")
def add_component(
    version_id: uuid.UUID,
    payload: ComponentAddRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).add_component(
            version_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.patch("/versions/{version_id}/components/batch")
def batch_mutate_components(
    version_id: uuid.UUID,
    payload: ComponentBatchRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    if payload.save_as_new and "enterprise_quota.create" not in context.permissions:
        raise HTTPException(403, "Permission denied")
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).batch_mutate_components(
            version_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.patch("/versions/{version_id}/components/{component_id}")
def mutate_component(
    version_id: uuid.UUID,
    component_id: uuid.UUID,
    payload: ComponentMutationRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).mutate_component(
            version_id, component_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.get("/versions/{version_id}/diff/{other_version_id}")
def diff(
    version_id: uuid.UUID,
    other_version_id: uuid.UUID,
    context: AuthContext = Depends(require_permission("enterprise_quota.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).diff(version_id, other_version_id)
    except Exception as exc:
        raise translate(exc) from exc


@router.patch("/versions/{version_id}/draft")
def save_draft(
    version_id: uuid.UUID,
    payload: DraftSaveRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).save_draft(
            version_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/save-as-new")
def save_as_new(
    version_id: uuid.UUID,
    payload: DraftSaveRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.create")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).save_as_new(
            version_id, payload.model_dump(), context, request_id(request)
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/submit")
def submit(
    version_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.edit")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).transition(
            version_id, expected=("draft",), target="submitted", row_version=payload.row_version,
            comment=payload.comment, idempotency_key=payload.idempotency_key,
            context=context, request_id=request_id(request),
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/review")
def review(
    version_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.review")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).transition(
            version_id, expected=("submitted",), target="reviewed", row_version=payload.row_version,
            comment=payload.comment, idempotency_key=payload.idempotency_key,
            context=context, request_id=request_id(request),
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/return-to-draft")
def return_to_draft(
    version_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.review")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).transition(
            version_id, expected=("submitted", "reviewed"), target="draft", row_version=payload.row_version,
            comment=payload.comment, idempotency_key=payload.idempotency_key,
            context=context, request_id=request_id(request),
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/approve")
def approve(
    version_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.approve")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).transition(
            version_id, expected=("reviewed",), target="approved", row_version=payload.row_version,
            comment=payload.comment, idempotency_key=payload.idempotency_key,
            context=context, request_id=request_id(request),
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/restore")
def restore(
    version_id: uuid.UUID,
    payload: RestoreRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise_quota.create")),
    _: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        return EnterpriseQuotaRepository(db, context.tenant_id).restore(
            version_id, row_version=payload.row_version, change_reason=payload.change_reason,
            idempotency_key=payload.idempotency_key, context=context, request_id=request_id(request),
        )
    except Exception as exc:
        raise translate(exc) from exc


@router.post("/versions/{version_id}/publish")
def publish_disabled(
    version_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("enterprise_quota.publish")),
    __: AuthContext = Depends(require_csrf),
):
    del version_id
    raise HTTPException(403, "Formal publication is disabled for the A1.1 pilot")
