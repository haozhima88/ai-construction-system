from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from platform_db.config import get_settings
from platform_db.database import build_engine
from platform_db.security import SecurityConfigurationError
from platform_db.services.authentication import AuthContext, csrf_matches, load_auth_context
from platform_db.services.security_audit import record_security_event


engine = build_engine()
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    with SessionFactory() as session:
        try:
            yield session
            session.commit()
        except HTTPException:
            if session.info.pop("commit_on_http_error", False):
                session.commit()
            else:
                session.rollback()
            raise
        except Exception:
            session.rollback()
            raise


def get_current_session(request: Request, db: Session = Depends(get_db_session)) -> AuthContext:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name, "")
    try:
        context = load_auth_context(db, settings, raw_token)
    except SecurityConfigurationError as exc:
        raise HTTPException(503, "Authentication service is not configured") from exc
    if context is None:
        raise HTTPException(401, "Authentication required")
    return context


def get_current_user(context: AuthContext = Depends(get_current_session)):
    return context.user


def _deny(db: Session, context: AuthContext, request: Request, reason: str) -> None:
    record_security_event(
        db, tenant_id=context.tenant_id, app_user_id=context.user.app_user_id,
        action="permission_denied", object_type="http_request", object_id=request.url.path,
        result="denied", reason=reason, request=request, actor_user_id=context.user.app_user_id,
    )
    db.info["commit_on_http_error"] = True


def require_permission(permission_code: str) -> Callable:
    def dependency(
        request: Request,
        context: AuthContext = Depends(get_current_session),
        db: Session = Depends(get_db_session),
    ) -> AuthContext:
        if context.user.must_change_password:
            _deny(db, context, request, "password_change_required")
            raise HTTPException(403, "Password change required")
        if permission_code not in context.permissions:
            _deny(db, context, request, f"missing_permission:{permission_code}")
            raise HTTPException(403, "Permission denied")
        return context
    return dependency


def require_role(role_code: str) -> Callable:
    def dependency(
        request: Request,
        context: AuthContext = Depends(get_current_session),
        db: Session = Depends(get_db_session),
    ) -> AuthContext:
        if context.user.must_change_password:
            _deny(db, context, request, "password_change_required")
            raise HTTPException(403, "Password change required")
        if role_code not in context.roles:
            _deny(db, context, request, f"missing_role:{role_code}")
            raise HTTPException(403, "Permission denied")
        return context
    return dependency


def require_tenant_scope(context: AuthContext = Depends(get_current_session)) -> uuid.UUID:
    return context.tenant_id


def enforce_tenant_scope(
    db: Session,
    context: AuthContext,
    resource_tenant_id: uuid.UUID,
    request: Request | None = None,
) -> None:
    if context.tenant_id == resource_tenant_id:
        return
    record_security_event(
        db, tenant_id=context.tenant_id, app_user_id=context.user.app_user_id,
        action="tenant_scope_rejected", object_type="tenant", object_id=resource_tenant_id,
        result="denied", reason="resource_tenant_mismatch", request=request,
        actor_user_id=context.user.app_user_id,
    )
    raise HTTPException(403, "Tenant scope denied")


def require_csrf(
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    context: AuthContext = Depends(get_current_session),
    db: Session = Depends(get_db_session),
) -> AuthContext:
    if csrf_matches(context, x_csrf_token, get_settings()):
        return context
    record_security_event(
        db, tenant_id=context.tenant_id, app_user_id=context.user.app_user_id,
        action="csrf_rejected", object_type="http_request", object_id=request.url.path,
        result="denied", reason="csrf_mismatch", request=request,
        actor_user_id=context.user.app_user_id,
    )
    db.info["commit_on_http_error"] = True
    raise HTTPException(403, "CSRF validation failed")
