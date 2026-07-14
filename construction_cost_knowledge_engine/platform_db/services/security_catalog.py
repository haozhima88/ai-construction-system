from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from platform_db.config import Settings
from platform_db.importers.common import stable_uuid
from platform_db.importers.rc1 import SYSTEM_USER_KEY
from platform_db.models import AppPermission, AppRole, AppRolePermission, AppTenant, AppUser, AppUserRoleAssignment
from platform_db.security import hash_password, normalize_username

from .security_audit import record_security_event


PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("reference.read", "Read reference data", "reference"),
    ("mapping.read", "Read candidate mappings", "mapping"),
    ("mapping_draft.read", "Read mapping drafts", "mapping_draft"),
    ("mapping_draft.create", "Create mapping drafts", "mapping_draft"),
    ("mapping_draft.update", "Update mapping drafts", "mapping_draft"),
    ("mapping_draft.exclude", "Exclude mapping candidates", "mapping_draft"),
    ("mapping_review.read", "Read mapping review", "mapping_review"),
    ("mapping_review.update", "Update mapping review", "mapping_review"),
    ("release.read", "Read releases", "release"),
    ("enterprise_price.read", "Read enterprise prices", "enterprise_price"),
    ("enterprise_price.edit", "Edit enterprise price drafts", "enterprise_price"),
    ("enterprise_price.review", "Review enterprise prices", "enterprise_price"),
    ("enterprise_price.approve", "Approve enterprise prices", "enterprise_price"),
    ("enterprise_price.publish", "Publish enterprise prices", "enterprise_price"),
    ("enterprise_quota.read", "Read enterprise quotas", "enterprise_quota"),
    ("enterprise_quota.create", "Create enterprise quota drafts", "enterprise_quota"),
    ("enterprise_quota.edit", "Edit enterprise quota drafts", "enterprise_quota"),
    ("enterprise_quota.submit", "Submit enterprise quota versions", "enterprise_quota"),
    ("enterprise_quota.review", "Review enterprise quotas", "enterprise_quota"),
    ("enterprise_quota.approve", "Approve enterprise quotas", "enterprise_quota"),
    ("enterprise_quota.publish", "Publish enterprise quotas", "enterprise_quota"),
    ("user.read", "Read tenant users", "identity"),
    ("user.create", "Create tenant users", "identity"),
    ("user.update", "Update tenant users", "identity"),
    ("user.disable", "Disable tenant users", "identity"),
    ("role.assign", "Assign tenant roles", "identity"),
    ("audit.read", "Read security audit", "audit"),
    ("system.manage", "Manage platform security", "system"),
)

DOMAIN_READ = {
    "reference.read", "mapping.read", "mapping_draft.read", "mapping_review.read", "release.read",
    "enterprise_price.read", "enterprise_quota.read",
}
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": DOMAIN_READ,
    "editor": DOMAIN_READ | {
        "mapping_draft.create", "mapping_draft.update", "mapping_draft.exclude",
        "enterprise_price.edit", "enterprise_quota.create", "enterprise_quota.edit",
    },
    "reviewer": DOMAIN_READ | {
        "mapping_review.update", "enterprise_price.review", "enterprise_quota.review",
    },
    "approver": DOMAIN_READ | {
        "enterprise_price.approve", "enterprise_price.publish",
        "enterprise_quota.approve", "enterprise_quota.publish",
    },
    "administrator": DOMAIN_READ | {
        "user.read", "user.create", "user.update", "user.disable", "role.assign", "audit.read", "system.manage",
    },
}


def seed_security_catalog(session: Session, settings: Settings) -> dict[str, int | str]:
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
    if tenant is None:
        raise RuntimeError("Platform tenant must exist before security catalog initialization")
    system_user = session.scalar(select(AppUser).where(
        AppUser.tenant_id == tenant.tenant_id,
        AppUser.login_name_normalized == SYSTEM_USER_KEY,
        AppUser.is_service_account.is_(True),
    ))
    if system_user is None:
        raise RuntimeError("Platform system account must exist before security catalog initialization")

    now = datetime.now(timezone.utc)
    for code, name, group in PERMISSIONS:
        session.execute(pg_insert(AppPermission).values(
            permission_id=stable_uuid("app_permission", code),
            permission_code=code,
            permission_name=name,
            resource_group=group,
            description=f"Platform permission: {code}",
            status="active",
            created_by=system_user.app_user_id,
        ).on_conflict_do_update(
            index_elements=[AppPermission.permission_code],
            set_={"permission_name": name, "resource_group": group, "description": f"Platform permission: {code}", "status": "active"},
        ))
    permission_ids = dict(session.execute(select(AppPermission.permission_code, AppPermission.permission_id)).all())
    roles = {role.role_code: role for role in session.scalars(select(AppRole)).all()}
    missing_roles = set(ROLE_PERMISSIONS) - set(roles)
    if missing_roles:
        raise RuntimeError(f"Missing platform roles: {sorted(missing_roles)}")
    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        for permission_code in permission_codes:
            key = f"{tenant.tenant_id}:{role_code}:{permission_code}"
            session.execute(pg_insert(AppRolePermission).values(
                role_permission_id=stable_uuid("app_role_permission", key),
                tenant_id=tenant.tenant_id,
                app_role_id=roles[role_code].app_role_id,
                permission_id=permission_ids[permission_code],
                granted_at=now,
                granted_by=system_user.app_user_id,
                status="active",
                created_by=system_user.app_user_id,
            ).on_conflict_do_update(
                constraint="uq_role_permission_tenant_role_permission",
                set_={"status": "active", "updated_by": system_user.app_user_id},
            ))
    session.flush()
    return {
        "permission_count": int(session.scalar(select(func.count()).select_from(AppPermission)) or 0),
        "role_count": len(roles),
        "role_permission_count": int(session.scalar(select(func.count()).select_from(AppRolePermission).where(AppRolePermission.tenant_id == tenant.tenant_id)) or 0),
    }


def bootstrap_initial_administrator(session: Session, settings: Settings) -> dict[str, str | bool]:
    tenant = session.scalar(select(AppTenant).where(AppTenant.tenant_code == settings.tenant_code))
    if tenant is None:
        raise RuntimeError("Platform tenant must exist before administrator bootstrap")
    existing_local_count = int(session.scalar(
        select(func.count()).select_from(AppUser).where(AppUser.tenant_id == tenant.tenant_id, AppUser.is_service_account.is_(False))
    ) or 0)
    if existing_local_count:
        return {"status": "skipped_existing_local_user", "created": False}
    username = normalize_username(settings.bootstrap_admin_username)
    password = settings.bootstrap_admin_password
    if not username or not password or username.startswith("replace_with_") or password.startswith("replace_with_"):
        return {"status": "pending_environment", "created": False}
    system_user = session.scalar(select(AppUser).where(
        AppUser.tenant_id == tenant.tenant_id, AppUser.is_service_account.is_(True),
    ))
    administrator = session.scalar(select(AppRole).where(AppRole.role_code == "administrator"))
    if system_user is None or administrator is None:
        raise RuntimeError("System account and administrator role are required")
    now = datetime.now(timezone.utc)
    user_id = uuid.uuid4()
    user = AppUser(
        app_user_id=user_id,
        tenant_id=tenant.tenant_id,
        login_name=settings.bootstrap_admin_username.strip(),
        login_name_normalized=username,
        display_name=settings.bootstrap_admin_display_name.strip() or "Platform Administrator",
        status="active",
        password_hash=hash_password(password),
        password_changed_at=now,
        must_change_password=True,
        is_service_account=False,
        auth_version=1,
        created_by=system_user.app_user_id,
    )
    session.add(user)
    session.flush()
    session.add(AppUserRoleAssignment(
        assignment_id=uuid.uuid4(), tenant_id=tenant.tenant_id, app_user_id=user_id,
        app_role_id=administrator.app_role_id, effective_from=now, assigned_by=system_user.app_user_id,
        status="active", created_by=system_user.app_user_id,
    ))
    record_security_event(
        session, tenant_id=tenant.tenant_id, app_user_id=user_id, action="user_created",
        object_type="app_user", object_id=user_id, result="success", reason="bootstrap_environment",
        actor_user_id=system_user.app_user_id,
    )
    session.flush()
    return {"status": "created", "created": True}
