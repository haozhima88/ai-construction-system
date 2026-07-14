from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_db.config import get_settings
from platform_db.dependencies import get_current_session, get_db_session, require_csrf
from platform_db.repositories import TenantAuthRepository
from platform_db.services.authentication import (
    AuthenticationFailure, AuthContext, authenticate, change_password, context_payload,
    revoke_other_sessions, revoke_session,
)
from platform_db.services.security_audit import record_security_event
from platform_db.security import SecurityConfigurationError


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024, repr=False)
    new_password: str = Field(min_length=12, max_length=1024, repr=False)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db_session)):
    settings = get_settings()
    try:
        result = authenticate(db, settings, payload.username, payload.password, request)
    except AuthenticationFailure as exc:
        db.info["commit_on_http_error"] = True
        raise HTTPException(exc.status_code, str(exc)) from exc
    except SecurityConfigurationError as exc:
        raise HTTPException(503, "Authentication service is not configured") from exc
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.raw_session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
        max_age=settings.session_absolute_timeout_hours * 3600,
    )
    return context_payload(result.context)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    revoke_session(db, context, context.app_session.session_id, request)
    record_security_event(
        db, tenant_id=context.tenant_id, app_user_id=context.user.app_user_id,
        action="logout", object_type="app_session", object_id=context.app_session.session_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.session_cookie_secure, samesite=settings.session_cookie_samesite)
    return {"status": "logged_out"}


@router.get("/me")
def me(context: AuthContext = Depends(get_current_session)):
    return context_payload(context)


@router.post("/change-password")
def password_change(
    payload: ChangePasswordRequest,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    try:
        change_password(db, context, payload.current_password, payload.new_password, request)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "password_changed"}


@router.get("/sessions")
def sessions(context: AuthContext = Depends(get_current_session), db: Session = Depends(get_db_session)):
    rows = TenantAuthRepository(db, context.tenant_id).sessions(context.user.app_user_id)
    return {"items": [{
        "session_id": str(row.session_id),
        "current": row.session_id == context.app_session.session_id,
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
        "expires_at": row.expires_at,
        "absolute_expires_at": row.absolute_expires_at,
        "client_ip": row.client_ip,
        "user_agent": row.user_agent,
        "status": row.status,
    } for row in rows]}


@router.delete("/sessions/{session_id}")
def session_revoke(
    session_id: uuid.UUID,
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    if session_id == context.app_session.session_id:
        raise HTTPException(400, "Use logout to revoke the current session")
    if not revoke_session(db, context, session_id, request):
        raise HTTPException(404, "Session not found")
    return {"status": "revoked"}


@router.post("/sessions/revoke-others")
def sessions_revoke_others(
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db_session),
):
    return {"status": "revoked", "count": revoke_other_sessions(db, context, request)}
