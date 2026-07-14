from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_db.dependencies import get_db_session, require_csrf, require_permission, require_role
from platform_db.services.authentication import AuthContext
from platform_db.services.user_administration import (
    assign_role, create_user, list_users, remove_role, reset_password, role_catalog,
    set_user_enabled, update_user, user_payload,
)


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["administration"],
    dependencies=[Depends(require_role("administrator"))],
)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    initial_password: str = Field(min_length=12, max_length=1024, repr=False)


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=1024, repr=False)


class AssignRoleRequest(BaseModel):
    role_id: uuid.UUID


@router.get("/users")
def users(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
    context: AuthContext = Depends(require_permission("user.read")),
    db: Session = Depends(get_db_session),
):
    return list_users(db, context, page, page_size)


@router.post("/users")
def user_create(
    payload: CreateUserRequest,
    request: Request,
    _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("user.create")),
    db: Session = Depends(get_db_session),
):
    try:
        user = create_user(
            db, context, login_name=payload.username, display_name=payload.display_name,
            password=payload.initial_password, email=payload.email, request=request,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return user_payload(db, context.tenant_id, user)


@router.get("/users/{user_id}")
def user_get(
    user_id: uuid.UUID,
    context: AuthContext = Depends(require_permission("user.read")),
    db: Session = Depends(get_db_session),
):
    from platform_db.repositories import TenantAuthRepository
    user = TenantAuthRepository(db, context.tenant_id).user(user_id)
    if user is None or user.is_service_account:
        raise HTTPException(404, "User not found")
    return user_payload(db, context.tenant_id, user)


@router.patch("/users/{user_id}")
def user_update(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    request: Request,
    _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("user.update")),
    db: Session = Depends(get_db_session),
):
    try:
        user = update_user(db, context, user_id, display_name=payload.display_name, email=payload.email, request=request)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return user_payload(db, context.tenant_id, user)


def _enabled_action(
    user_id: uuid.UUID, enabled: bool, request: Request, context: AuthContext, db: Session,
):
    try:
        user = set_user_enabled(db, context, user_id, enabled, request)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return user_payload(db, context.tenant_id, user)


@router.post("/users/{user_id}/disable")
def user_disable(
    user_id: uuid.UUID, request: Request, _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("user.disable")), db: Session = Depends(get_db_session),
):
    return _enabled_action(user_id, False, request, context, db)


@router.post("/users/{user_id}/enable")
def user_enable(
    user_id: uuid.UUID, request: Request, _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("user.update")), db: Session = Depends(get_db_session),
):
    return _enabled_action(user_id, True, request, context, db)


@router.post("/users/{user_id}/reset-password")
def user_reset_password(
    user_id: uuid.UUID, payload: ResetPasswordRequest, request: Request,
    _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("user.update")), db: Session = Depends(get_db_session),
):
    try:
        user = reset_password(db, context, user_id, payload.new_password, request)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return user_payload(db, context.tenant_id, user)


@router.get("/roles")
def roles(
    context: AuthContext = Depends(require_permission("user.read")), db: Session = Depends(get_db_session),
):
    return {"items": role_catalog(db, context)}


@router.post("/users/{user_id}/roles")
def role_add(
    user_id: uuid.UUID, payload: AssignRoleRequest, request: Request,
    _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("role.assign")), db: Session = Depends(get_db_session),
):
    try:
        assignment = assign_role(db, context, user_id, payload.role_id, request)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"assignment_id": str(assignment.assignment_id), "status": "active"}


@router.delete("/users/{user_id}/roles/{role_id}")
def role_delete(
    user_id: uuid.UUID, role_id: uuid.UUID, request: Request,
    _: AuthContext = Depends(require_csrf),
    context: AuthContext = Depends(require_permission("role.assign")), db: Session = Depends(get_db_session),
):
    try:
        removed = remove_role(db, context, user_id, role_id, request)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not removed:
        raise HTTPException(404, "Role assignment not found")
    return {"status": "removed"}
