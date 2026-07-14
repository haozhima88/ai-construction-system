from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from platform_db.dependencies import get_db_session, require_csrf, require_permission
from platform_db.models import (
    MappingAuditEvent, MappingCandidateEdge, MappingDraftEdge, ReferenceBillItem,
    ReferenceQuotaItem, ReferenceQuotaResource,
)
from platform_db.repositories import (
    BillReviewRepository, MappingAuditRepository, MappingDraftRepository,
    MappingReviewRepository, MappingReviewWriteRepository, QuotaDetailRepository,
    ReviewConflictError, ReviewNotFoundError, ReviewValidationError,
)
from platform_db.services.authentication import AuthContext
from platform_db.services.quota_cost_summary import QuotaCostSummaryService


router = APIRouter(prefix="/api/v1/review", tags=["postgres-review"])


class DraftMutation(BaseModel):
    edge_id: uuid.UUID
    target_bill_code_9: str | None = Field(default=None, pattern=r"^[0-9]{9}$")
    operation_reason: str = Field(default="", max_length=2000)
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)


class RestoreMutation(BaseModel):
    draft_id: uuid.UUID
    row_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=180)


class ReviewMutation(BaseModel):
    review_status: str
    comment: str = Field(default="", max_length=4000)
    row_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=180)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ReviewNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ReviewConflictError):
        return HTTPException(409, str(exc))
    if isinstance(exc, ReviewValidationError):
        return HTTPException(400, str(exc))
    return HTTPException(500, "Review operation failed")


@router.get("/summary")
def summary(
    context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    repository = BillReviewRepository(db, context.tenant_id)
    counts = {
        "bill_count": int(db.scalar(select(func.count()).select_from(ReferenceBillItem).where(
            ReferenceBillItem.reference_release_id == repository.scope.reference_release_id)) or 0),
        "quota_count": int(db.scalar(select(func.count()).select_from(ReferenceQuotaItem).where(
            ReferenceQuotaItem.reference_release_id == repository.scope.reference_release_id)) or 0),
        "resource_count": int(db.scalar(select(func.count()).select_from(ReferenceQuotaResource).where(
            ReferenceQuotaResource.reference_release_id == repository.scope.reference_release_id)) or 0),
        "mapping_edge_count": int(db.scalar(select(func.count()).select_from(MappingCandidateEdge).where(
            MappingCandidateEdge.mapping_release_id == repository.scope.mapping_release_id)) or 0),
        "draft_count": int(db.scalar(select(func.count()).select_from(MappingDraftEdge).where(
            MappingDraftEdge.tenant_id == context.tenant_id,
            MappingDraftEdge.mapping_workspace_id == repository.scope.workspace_id)) or 0),
        "audit_count": int(db.scalar(select(func.count()).select_from(MappingAuditEvent).where(
            MappingAuditEvent.tenant_id == context.tenant_id,
            MappingAuditEvent.mapping_workspace_id == repository.scope.workspace_id)) or 0),
    }
    return {
        **counts, "reference_release_id": repository.scope.reference_release_id,
        "mapping_release_id": repository.scope.mapping_release_id,
        "mapping_workspace_name": repository.scope.workspace_name,
        "backend": "postgres", "approved_count": 0,
    }


@router.get("/tree")
def tree(
    page: int = Query(1, ge=1), page_size: int = Query(500, ge=1, le=500),
    q: str | None = Query(default=None, max_length=200),
    appendix_code: str | None = Query(default=None, max_length=16),
    context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return BillReviewRepository(db, context.tenant_id).tree(
            page=page, page_size=page_size, q=q, appendix_code=appendix_code
        )
    except (ReviewNotFoundError, ReviewValidationError) as exc:
        raise translate_error(exc) from exc


@router.get("/bills/{bill_id}")
def bill(
    bill_id: str, context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return {"bill": BillReviewRepository(db, context.tenant_id).bill_payload(bill_id)}
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


@router.get("/bills/{bill_id}/mappings")
def bill_mappings(
    bill_id: str, context: AuthContext = Depends(require_permission("mapping.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return MappingReviewRepository(db, context.tenant_id).mappings_for_bill(bill_id)
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


@router.get("/bills/{bill_id}/authority-evidence")
def bill_authority_evidence(
    bill_id: str,
    context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return BillReviewRepository(db, context.tenant_id).authority_evidence(bill_id)
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


@router.get("/quotas/{quota_id}")
def quota(
    quota_id: str, context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return {"quota": QuotaDetailRepository(db, context.tenant_id).detail(quota_id)}
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


@router.get("/quotas/{quota_id}/resources")
def quota_resources(
    quota_id: str, page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=500),
    context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        result = QuotaDetailRepository(db, context.tenant_id).resources(
            quota_id, page=page, page_size=page_size
        )
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc
    return {
        "items": QuotaCostSummaryService().resources(result["rows"]),
        "page": result["page"], "page_size": result["page_size"], "total": result["total"],
    }


def rules(quota_id: str, rule_type: str, context: AuthContext, db: Session):
    try:
        return QuotaDetailRepository(db, context.tenant_id).rules(quota_id, rule_type)
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


@router.get("/quotas/{quota_id}/work-content")
def work_content(quota_id: str, context: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session)):
    return rules(quota_id, "work_content", context, db)


@router.get("/quotas/{quota_id}/quantity-rules")
def quantity_rules(quota_id: str, context: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session)):
    return rules(quota_id, "quantity_rule", context, db)


@router.get("/quotas/{quota_id}/conversion-rules")
def conversion_rules(quota_id: str, context: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session)):
    return rules(quota_id, "conversion", context, db)


@router.get("/quotas/{quota_id}/notes")
def notes(quota_id: str, context: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session)):
    return rules(quota_id, "note", context, db)


@router.get("/quotas/{quota_id}/cost-summary")
def cost_summary(
    quota_id: str, context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        result = QuotaDetailRepository(db, context.tenant_id).resources(
            quota_id, page=1, page_size=10000
        )
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc
    return QuotaCostSummaryService().summarize(result["quota"], result["rows"])


@router.get("/quotas/{quota_id}/evidence")
def quota_evidence(
    quota_id: str, context: AuthContext = Depends(require_permission("reference.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return QuotaDetailRepository(db, context.tenant_id).evidence(quota_id)
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


@router.get("/audit")
def audit(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
    context: AuthContext = Depends(require_permission("mapping_review.read")),
    db: Session = Depends(get_db_session),
):
    try:
        return MappingAuditRepository(db, context.tenant_id).list(page=page, page_size=page_size)
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc


def draft_action(
    action: str, payload: DraftMutation, context: AuthContext, db: Session, request: Request
) -> dict[str, Any]:
    try:
        return MappingDraftRepository(db, context.tenant_id).create_draft(
            action=action, edge_id=payload.edge_id,
            target_bill_code_9=payload.target_bill_code_9,
            operation_reason=payload.operation_reason,
            expected_row_version=payload.row_version,
            idempotency_key=payload.idempotency_key,
            actor_user_id=context.user.app_user_id,
            request_id=request.state.request_id,
        )
    except (ReviewNotFoundError, ReviewConflictError, ReviewValidationError) as exc:
        raise translate_error(exc) from exc


@router.post("/mapping-drafts/copy")
def copy_draft(request: Request, payload: DraftMutation, context: AuthContext = Depends(require_permission("mapping_draft.create")), _: AuthContext = Depends(require_csrf), db: Session = Depends(get_db_session)):
    return draft_action("copy", payload, context, db, request)


@router.post("/mapping-drafts/move")
def move_draft(request: Request, payload: DraftMutation, context: AuthContext = Depends(require_permission("mapping_draft.update")), _: AuthContext = Depends(require_csrf), db: Session = Depends(get_db_session)):
    return draft_action("move", payload, context, db, request)


@router.post("/mapping-drafts/exclude")
def exclude_draft(request: Request, payload: DraftMutation, context: AuthContext = Depends(require_permission("mapping_draft.exclude")), _: AuthContext = Depends(require_csrf), db: Session = Depends(get_db_session)):
    return draft_action("exclude", payload, context, db, request)


@router.post("/mapping-drafts/restore")
def restore_draft(
    request: Request, payload: RestoreMutation,
    context: AuthContext = Depends(require_permission("mapping_draft.update")),
    _: AuthContext = Depends(require_csrf), db: Session = Depends(get_db_session),
):
    try:
        return MappingDraftRepository(db, context.tenant_id).restore(
            draft_id=payload.draft_id, expected_row_version=payload.row_version,
            idempotency_key=payload.idempotency_key,
            actor_user_id=context.user.app_user_id,
            request_id=request.state.request_id,
        )
    except (ReviewNotFoundError, ReviewConflictError, ReviewValidationError) as exc:
        raise translate_error(exc) from exc


@router.patch("/mappings/{edge_id}/review-state")
def update_review_state(
    edge_id: uuid.UUID, request: Request, payload: ReviewMutation,
    context: AuthContext = Depends(require_permission("mapping_review.update")),
    _: AuthContext = Depends(require_csrf), db: Session = Depends(get_db_session),
):
    try:
        return MappingReviewWriteRepository(db, context.tenant_id).update_review(
            edge_id=edge_id, review_status=payload.review_status, comment=payload.comment,
            expected_row_version=payload.row_version,
            idempotency_key=payload.idempotency_key,
            actor_user_id=context.user.app_user_id,
            request_id=request.state.request_id,
        )
    except (ReviewNotFoundError, ReviewConflictError, ReviewValidationError) as exc:
        raise translate_error(exc) from exc


def pdf_response(path_value: str, filename: str) -> FileResponse:
    path = Path(path_value)
    if not path.is_file():
        raise HTTPException(404, "PDF source is unavailable")
    return FileResponse(
        path, media_type="application/pdf", filename=filename,
        content_disposition_type="inline",
    )


@router.get("/quotas/{quota_id}/pdf")
def quota_pdf(quota_id: str, context: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session)):
    try:
        _, document = QuotaDetailRepository(db, context.tenant_id).document_path(quota_id)
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc
    return pdf_response(document.actual_path, f"{document.document_name}.pdf")


@router.get("/authority/pdf")
def authority_pdf(context: AuthContext = Depends(require_permission("reference.read")), db: Session = Depends(get_db_session)):
    try:
        document = QuotaDetailRepository(db, context.tenant_id).authority_document()
    except ReviewNotFoundError as exc:
        raise translate_error(exc) from exc
    return pdf_response(document.actual_path, "GB_T_50854-2024.pdf")
