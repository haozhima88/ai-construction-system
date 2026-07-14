from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from platform_db.config import Settings
from platform_db.models import (
    AppLoginAttempt, AppPasswordHistory, AppPermission, AppRole, AppRolePermission,
    AppSession, AppTenant, AppUser, AppUserRoleAssignment,
)
from platform_db.repositories import TenantAuthRepository
from platform_db.security import derive_csrf_token, hash_password, new_session_token, normalize_username, token_hash, verify_password

from .security_audit import record_security_event, request_metadata


GENERIC_LOGIN_MESSAGE = "Invalid username or password"


class AuthenticationFailure(ValueError):
    def __init__(self, reason_code: str, status_code: int = 401):
        super().__init__(GENERIC_LOGIN_MESSAGE)
        self.reason_code = reason_code
        self.status_code = status_code


@dataclass(frozen=True)
class AuthContext:
    app_session: AppSession
    user: AppUser
    tenant: AppTenant
    roles: tuple[str, ...]
    permissions: frozenset[str]
    raw_session_token: str
    csrf_token: str

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.tenant.tenant_id


@dataclass(frozen=True)
class LoginResult:
    context: AuthContext
    raw_session_token: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _active(value) -> bool:
    return getattr(value, "value", value) == "active"


def _tenant(session: Session, tenant_code: str) -> AppTenant:
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == tenant_code))
    if tenant is None or not _active(tenant.status):
        raise AuthenticationFailure("tenant_unavailable")
    return tenant


def role_permission_codes(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None) -> tuple[tuple[str, ...], frozenset[str]]:
    moment = now or utcnow()
    rows = session.execute(
        select(AppRole.role_code, AppPermission.permission_code)
        .join(AppUserRoleAssignment, AppUserRoleAssignment.app_role_id == AppRole.app_role_id)
        .join(AppRolePermission, AppRolePermission.app_role_id == AppRole.app_role_id)
        .join(AppPermission, AppPermission.permission_id == AppRolePermission.permission_id)
        .where(
            AppUserRoleAssignment.tenant_id == tenant_id,
            AppUserRoleAssignment.app_user_id == user_id,
            AppUserRoleAssignment.status == "active",
            AppUserRoleAssignment.effective_from <= moment,
            or_(AppUserRoleAssignment.effective_to.is_(None), AppUserRoleAssignment.effective_to > moment),
            AppRolePermission.tenant_id == tenant_id,
            AppRolePermission.status == "active",
            AppPermission.status == "active",
            AppRole.status == "active",
        )
    ).all()
    return tuple(sorted({row.role_code for row in rows})), frozenset(row.permission_code for row in rows)


def _failed_count(
    session: Session,
    tenant_id: uuid.UUID,
    username: str,
    client_ip: str | None,
    since: datetime,
) -> int:
    dimensions = [AppLoginAttempt.username_normalized == username]
    if client_ip:
        dimensions.append(AppLoginAttempt.client_ip == client_ip)
    return int(session.scalar(select(func.count()).select_from(AppLoginAttempt).where(
        AppLoginAttempt.tenant_id == tenant_id,
        AppLoginAttempt.success.is_(False),
        AppLoginAttempt.attempt_at >= since,
        or_(*dimensions),
    )) or 0)


def _attempt(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    username: str,
    user_id: uuid.UUID | None,
    success: bool,
    reason: str | None,
    request: Request | None,
    now: datetime,
) -> None:
    metadata = request_metadata(request)
    session.add(AppLoginAttempt(
        login_attempt_id=uuid.uuid4(), tenant_id=tenant_id, username_normalized=username,
        app_user_id=user_id, attempt_at=now, client_ip=metadata["client_ip"],
        user_agent=metadata["user_agent"], success=success, failure_reason=reason,
    ))


def authenticate(
    session: Session,
    settings: Settings,
    username: str,
    password: str,
    request: Request | None = None,
    now: datetime | None = None,
) -> LoginResult:
    moment = now or utcnow()
    normalized = normalize_username(username)
    tenant = _tenant(session, settings.tenant_code)
    metadata = request_metadata(request)
    since = moment - timedelta(minutes=settings.auth_failure_window_minutes)
    if _failed_count(session, tenant.tenant_id, normalized, metadata["client_ip"], since) >= settings.auth_max_failed_attempts:
        _attempt(session, tenant_id=tenant.tenant_id, username=normalized, user_id=None, success=False, reason="rate_limited", request=request, now=moment)
        record_security_event(
            session, tenant_id=tenant.tenant_id, action="login_failed", object_type="authentication",
            result="failure", reason="rate_limited", request=request,
        )
        raise AuthenticationFailure("rate_limited", 429)

    user = TenantAuthRepository(session, tenant.tenant_id).user_by_login(normalized)
    password_ok = verify_password(user.password_hash if user else None, password)
    locked = bool(user and user.lockout_until and user.lockout_until > moment)
    enabled = bool(user and _active(user.status) and not user.is_service_account)
    if not user or not password_ok or locked or not enabled:
        reason = "invalid_credentials"
        _attempt(
            session, tenant_id=tenant.tenant_id, username=normalized,
            user_id=user.app_user_id if user else None, success=False, reason=reason, request=request, now=moment,
        )
        failures = _failed_count(session, tenant.tenant_id, normalized, metadata["client_ip"], since)
        if user and failures >= settings.auth_max_failed_attempts:
            user.lockout_until = moment + timedelta(minutes=settings.auth_lockout_minutes)
        record_security_event(
            session, tenant_id=tenant.tenant_id, app_user_id=user.app_user_id if user else None,
            action="login_failed", object_type="authentication", object_id=user.app_user_id if user else None,
            result="failure", reason=reason, request=request,
        )
        raise AuthenticationFailure(reason)

    raw_token = new_session_token()
    csrf_token = derive_csrf_token(raw_token, settings.session_hash_secret)
    absolute_expiry = moment + timedelta(hours=settings.session_absolute_timeout_hours)
    idle_expiry = min(moment + timedelta(minutes=settings.session_idle_timeout_minutes), absolute_expiry)
    app_session = AppSession(
        session_id=uuid.uuid4(), tenant_id=tenant.tenant_id, app_user_id=user.app_user_id,
        session_token_hash=token_hash(raw_token, settings.session_hash_secret),
        csrf_token_hash=token_hash(csrf_token, settings.session_hash_secret, "csrf"),
        last_seen_at=moment, expires_at=idle_expiry, absolute_expires_at=absolute_expiry,
        client_ip=metadata["client_ip"], user_agent=metadata["user_agent"], status="active",
        created_by=user.app_user_id,
    )
    session.add(app_session)
    _attempt(session, tenant_id=tenant.tenant_id, username=normalized, user_id=user.app_user_id, success=True, reason=None, request=request, now=moment)
    user.last_login_at = moment
    user.lockout_until = None
    roles, permissions = role_permission_codes(session, tenant.tenant_id, user.app_user_id, moment)
    record_security_event(
        session, tenant_id=tenant.tenant_id, app_user_id=user.app_user_id,
        action="login_success", object_type="app_session", object_id=app_session.session_id,
        result="success", request=request, actor_user_id=user.app_user_id,
    )
    context = AuthContext(app_session, user, tenant, roles, permissions, raw_token, csrf_token)
    return LoginResult(context=context, raw_session_token=raw_token)


def load_auth_context(
    session: Session,
    settings: Settings,
    raw_token: str,
    now: datetime | None = None,
    touch: bool = True,
) -> AuthContext | None:
    if not raw_token:
        return None
    try:
        digest = token_hash(raw_token, settings.session_hash_secret)
    except Exception:
        return None
    app_session = session.scalar(select(AppSession).where(AppSession.session_token_hash == digest))
    if app_session is None or app_session.status != "active":
        return None
    moment = now or utcnow()
    user = session.scalar(select(AppUser).where(
        AppUser.app_user_id == app_session.app_user_id,
        AppUser.tenant_id == app_session.tenant_id,
    ))
    tenant = session.get(AppTenant, app_session.tenant_id)
    if user is None or tenant is None or not _active(user.status) or user.is_service_account or not _active(tenant.status):
        app_session.status = "revoked"
        app_session.revoked_at = moment
        return None
    if moment >= app_session.expires_at or moment >= app_session.absolute_expires_at:
        app_session.status = "expired"
        app_session.revoked_at = moment
        return None
    if touch and moment - app_session.last_seen_at >= timedelta(seconds=60):
        app_session.last_seen_at = moment
        app_session.expires_at = min(
            moment + timedelta(minutes=settings.session_idle_timeout_minutes),
            app_session.absolute_expires_at,
        )
    roles, permissions = role_permission_codes(session, app_session.tenant_id, user.app_user_id, moment)
    csrf_token = derive_csrf_token(raw_token, settings.session_hash_secret)
    return AuthContext(app_session, user, tenant, roles, permissions, raw_token, csrf_token)


def csrf_matches(context: AuthContext, candidate: str | None, settings: Settings) -> bool:
    if not candidate:
        return False
    try:
        digest = token_hash(candidate, settings.session_hash_secret, "csrf")
    except Exception:
        return False
    return hmac.compare_digest(context.app_session.csrf_token_hash, digest)


def revoke_session(
    session: Session,
    context: AuthContext,
    target_session_id: uuid.UUID,
    request: Request | None = None,
) -> bool:
    target = TenantAuthRepository(session, context.tenant_id).session_record(target_session_id, context.user.app_user_id)
    if target is None or target.status != "active":
        return False
    target.status = "revoked"
    target.revoked_at = utcnow()
    target.revoked_by = context.user.app_user_id
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=context.user.app_user_id,
        action="session_revoked", object_type="app_session", object_id=target.session_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    return True


def revoke_other_sessions(session: Session, context: AuthContext, request: Request | None = None) -> int:
    moment = utcnow()
    result = session.execute(update(AppSession).where(
        AppSession.tenant_id == context.tenant_id,
        AppSession.app_user_id == context.user.app_user_id,
        AppSession.session_id != context.app_session.session_id,
        AppSession.status == "active",
    ).values(status="revoked", revoked_at=moment, revoked_by=context.user.app_user_id))
    count = int(result.rowcount or 0)
    if count:
        record_security_event(
            session, tenant_id=context.tenant_id, app_user_id=context.user.app_user_id,
            action="session_revoked", object_type="app_session", object_id="other_sessions",
            result="success", reason=f"revoked_count={count}", request=request, actor_user_id=context.user.app_user_id,
        )
    return count


def change_password(
    session: Session,
    context: AuthContext,
    current_password: str,
    new_password: str,
    request: Request | None = None,
    history_limit: int = 5,
) -> None:
    user = context.user
    if not verify_password(user.password_hash, current_password):
        raise ValueError("Current password is incorrect")
    if verify_password(user.password_hash, new_password):
        raise ValueError("New password must be different")
    previous = list(session.scalars(select(AppPasswordHistory).where(
        AppPasswordHistory.tenant_id == context.tenant_id,
        AppPasswordHistory.app_user_id == user.app_user_id,
    ).order_by(AppPasswordHistory.created_at.desc()).limit(history_limit)))
    if any(verify_password(item.password_hash, new_password) for item in previous):
        raise ValueError("New password was used recently")
    moment = utcnow()
    if user.password_hash:
        session.add(AppPasswordHistory(
            password_history_id=uuid.uuid4(), tenant_id=context.tenant_id,
            app_user_id=user.app_user_id, password_hash=user.password_hash,
            reason="password_changed", created_by=user.app_user_id,
        ))
    user.password_hash = hash_password(new_password)
    user.password_changed_at = moment
    user.must_change_password = False
    user.auth_version += 1
    revoke_other_sessions(session, context, request)
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user.app_user_id,
        action="password_changed", object_type="app_user", object_id=user.app_user_id,
        result="success", request=request, actor_user_id=user.app_user_id,
    )


def context_payload(context: AuthContext) -> dict:
    return {
        "user": {
            "app_user_id": str(context.user.app_user_id),
            "login_name": context.user.login_name,
            "display_name": context.user.display_name,
            "email": context.user.email,
            "must_change_password": context.user.must_change_password,
        },
        "tenant": {
            "tenant_id": str(context.tenant.tenant_id),
            "tenant_code": context.tenant.tenant_code,
            "tenant_name": context.tenant.tenant_name,
        },
        "roles": list(context.roles),
        "permissions": sorted(context.permissions),
        "csrf_token": context.csrf_token,
    }
