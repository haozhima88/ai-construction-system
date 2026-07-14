from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from platform_db.models import AppPasswordHistory, AppPermission, AppRole, AppRolePermission, AppSession, AppUser, AppUserRoleAssignment
from platform_db.repositories import TenantAuthRepository
from platform_db.security import hash_password, normalize_username

from .authentication import AuthContext
from .security_audit import record_security_event


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _role_codes(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
    now = utcnow()
    return list(session.scalars(
        select(AppRole.role_code)
        .join(AppUserRoleAssignment, AppUserRoleAssignment.app_role_id == AppRole.app_role_id)
        .where(
            AppUserRoleAssignment.tenant_id == tenant_id,
            AppUserRoleAssignment.app_user_id == user_id,
            AppUserRoleAssignment.status == "active",
            AppUserRoleAssignment.effective_from <= now,
            or_(AppUserRoleAssignment.effective_to.is_(None), AppUserRoleAssignment.effective_to > now),
        ).order_by(AppRole.role_code)
    ))


def user_payload(session: Session, tenant_id: uuid.UUID, user: AppUser) -> dict:
    return {
        "app_user_id": str(user.app_user_id),
        "login_name": user.login_name,
        "display_name": user.display_name,
        "email": user.email,
        "status": getattr(user.status, "value", user.status),
        "must_change_password": user.must_change_password,
        "locked_until": user.lockout_until,
        "last_login_at": user.last_login_at,
        "roles": _role_codes(session, tenant_id, user.app_user_id),
        "row_version": user.row_version,
    }


def list_users(session: Session, context: AuthContext, page: int, page_size: int) -> dict:
    users, total = TenantAuthRepository(session, context.tenant_id).users(page, page_size)
    return {"items": [user_payload(session, context.tenant_id, user) for user in users], "page": page, "page_size": page_size, "total": total}


def create_user(
    session: Session,
    context: AuthContext,
    *,
    login_name: str,
    display_name: str,
    password: str,
    email: str | None = None,
    request: Request | None = None,
) -> AppUser:
    normalized = normalize_username(login_name)
    if not normalized:
        raise ValueError("Username is required")
    repository = TenantAuthRepository(session, context.tenant_id)
    if repository.user_by_login(normalized):
        raise ValueError("Username is already in use")
    user = AppUser(
        app_user_id=uuid.uuid4(), tenant_id=context.tenant_id,
        login_name=login_name.strip(), login_name_normalized=normalized,
        display_name=display_name.strip() or login_name.strip(), email=email.strip() if email else None,
        status="active", password_hash=hash_password(password), password_changed_at=utcnow(),
        must_change_password=True, is_service_account=False, auth_version=1,
        created_by=context.user.app_user_id,
    )
    session.add(user)
    session.flush()
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user.app_user_id,
        action="user_created", object_type="app_user", object_id=user.app_user_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    return user


def update_user(
    session: Session,
    context: AuthContext,
    user_id: uuid.UUID,
    *,
    display_name: str | None = None,
    email: str | None = None,
    request: Request | None = None,
) -> AppUser:
    user = TenantAuthRepository(session, context.tenant_id).user(user_id)
    if user is None or user.is_service_account:
        raise LookupError("User not found")
    if display_name is not None:
        user.display_name = display_name.strip() or user.login_name
    if email is not None:
        user.email = email.strip() or None
    user.updated_by = context.user.app_user_id
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user.app_user_id,
        action="user_updated", object_type="app_user", object_id=user.app_user_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    return user


def _revoke_all(session: Session, context: AuthContext, user_id: uuid.UUID) -> int:
    now = utcnow()
    result = session.execute(update(AppSession).where(
        AppSession.tenant_id == context.tenant_id,
        AppSession.app_user_id == user_id,
        AppSession.status == "active",
    ).values(status="revoked", revoked_at=now, revoked_by=context.user.app_user_id))
    return int(result.rowcount or 0)


def set_user_enabled(
    session: Session,
    context: AuthContext,
    user_id: uuid.UUID,
    enabled: bool,
    request: Request | None = None,
) -> AppUser:
    user = TenantAuthRepository(session, context.tenant_id).user(user_id)
    if user is None or user.is_service_account:
        raise LookupError("User not found")
    if user.app_user_id == context.user.app_user_id and not enabled:
        raise ValueError("Administrator cannot disable the current account")
    user.status = "active" if enabled else "inactive"
    user.updated_by = context.user.app_user_id
    if not enabled:
        _revoke_all(session, context, user_id)
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user.app_user_id,
        action="user_enabled" if enabled else "user_disabled", object_type="app_user", object_id=user.app_user_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    return user


def reset_password(
    session: Session,
    context: AuthContext,
    user_id: uuid.UUID,
    new_password: str,
    request: Request | None = None,
) -> AppUser:
    user = TenantAuthRepository(session, context.tenant_id).user(user_id)
    if user is None or user.is_service_account:
        raise LookupError("User not found")
    if user.password_hash:
        session.add(AppPasswordHistory(
            password_history_id=uuid.uuid4(), tenant_id=context.tenant_id, app_user_id=user.app_user_id,
            password_hash=user.password_hash, reason="password_reset", created_by=context.user.app_user_id,
        ))
    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = True
    user.lockout_until = None
    user.auth_version += 1
    user.updated_by = context.user.app_user_id
    _revoke_all(session, context, user_id)
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user.app_user_id,
        action="password_reset", object_type="app_user", object_id=user.app_user_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    return user


def role_catalog(session: Session, context: AuthContext) -> list[dict]:
    roles = list(session.scalars(select(AppRole).order_by(AppRole.role_code)))
    output = []
    for role in roles:
        permissions = list(session.scalars(
            select(AppPermission.permission_code)
            .join(AppRolePermission, AppRolePermission.permission_id == AppPermission.permission_id)
            .where(
                AppRolePermission.tenant_id == context.tenant_id,
                AppRolePermission.app_role_id == role.app_role_id,
                AppRolePermission.status == "active",
            ).order_by(AppPermission.permission_code)
        ))
        output.append({
            "app_role_id": str(role.app_role_id), "role_code": role.role_code,
            "role_name": role.role_name, "permissions": permissions,
        })
    return output


def assign_role(
    session: Session,
    context: AuthContext,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    request: Request | None = None,
) -> AppUserRoleAssignment:
    repository = TenantAuthRepository(session, context.tenant_id)
    user = repository.user(user_id)
    role = session.get(AppRole, role_id)
    if user is None or user.is_service_account or role is None:
        raise LookupError("User or role not found")
    now = utcnow()
    existing = repository.active_role_assignment(user_id, role_id, now)
    if existing:
        return existing
    assignment = AppUserRoleAssignment(
        assignment_id=uuid.uuid4(), tenant_id=context.tenant_id, app_user_id=user_id,
        app_role_id=role_id, effective_from=now, assigned_by=context.user.app_user_id,
        status="active", created_by=context.user.app_user_id,
    )
    session.add(assignment)
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user_id,
        action="role_assigned", object_type="app_role", object_id=role_id,
        result="success", reason=role.role_code, request=request, actor_user_id=context.user.app_user_id,
    )
    return assignment


def remove_role(
    session: Session,
    context: AuthContext,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    request: Request | None = None,
) -> bool:
    assignment = TenantAuthRepository(session, context.tenant_id).active_role_assignment(user_id, role_id, utcnow())
    if assignment is None:
        return False
    if user_id == context.user.app_user_id:
        role = session.get(AppRole, role_id)
        if role and role.role_code == "administrator":
            raise ValueError("Administrator cannot remove the current administrator role")
    assignment.status = "inactive"
    assignment.effective_to = utcnow()
    assignment.updated_by = context.user.app_user_id
    record_security_event(
        session, tenant_id=context.tenant_id, app_user_id=user_id,
        action="role_removed", object_type="app_role", object_id=role_id,
        result="success", request=request, actor_user_id=context.user.app_user_id,
    )
    return True
