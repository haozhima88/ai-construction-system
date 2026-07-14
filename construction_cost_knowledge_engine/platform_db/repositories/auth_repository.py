from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from platform_db.models import AppSession, AppUser, AppUserRoleAssignment


class TenantAuthRepository:
    """Tenant-scoped identity access; tenant_id never comes from HTTP payloads."""

    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    def user(self, user_id: uuid.UUID) -> AppUser | None:
        return self.session.scalar(select(AppUser).where(
            AppUser.tenant_id == self.tenant_id,
            AppUser.app_user_id == user_id,
        ))

    def user_by_login(self, normalized_login: str) -> AppUser | None:
        return self.session.scalar(select(AppUser).where(
            AppUser.tenant_id == self.tenant_id,
            AppUser.login_name_normalized == normalized_login,
            AppUser.is_service_account.is_(False),
        ))

    def users(self, page: int = 1, page_size: int = 100) -> tuple[list[AppUser], int]:
        base = select(AppUser).where(
            AppUser.tenant_id == self.tenant_id,
            AppUser.is_service_account.is_(False),
        )
        total = int(self.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = list(self.session.scalars(
            base.order_by(AppUser.login_name_normalized).offset((page - 1) * page_size).limit(page_size)
        ))
        return rows, total

    def sessions(self, user_id: uuid.UUID) -> list[AppSession]:
        return list(self.session.scalars(select(AppSession).where(
            AppSession.tenant_id == self.tenant_id,
            AppSession.app_user_id == user_id,
        ).order_by(AppSession.created_at.desc())))

    def session_record(self, session_id: uuid.UUID, user_id: uuid.UUID | None = None) -> AppSession | None:
        statement = select(AppSession).where(
            AppSession.tenant_id == self.tenant_id,
            AppSession.session_id == session_id,
        )
        if user_id is not None:
            statement = statement.where(AppSession.app_user_id == user_id)
        return self.session.scalar(statement)

    def active_role_assignment(self, user_id: uuid.UUID, role_id: uuid.UUID, now: datetime) -> AppUserRoleAssignment | None:
        return self.session.scalar(select(AppUserRoleAssignment).where(
            AppUserRoleAssignment.tenant_id == self.tenant_id,
            AppUserRoleAssignment.app_user_id == user_id,
            AppUserRoleAssignment.app_role_id == role_id,
            AppUserRoleAssignment.status == "active",
            AppUserRoleAssignment.effective_from <= now,
            (AppUserRoleAssignment.effective_to.is_(None) | (AppUserRoleAssignment.effective_to > now)),
        ))
