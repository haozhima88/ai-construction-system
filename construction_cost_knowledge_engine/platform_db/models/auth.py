from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import AuditMixin, Base, LifecycleStatus, TenantMixin


class AppSession(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_session"
    __table_args__ = (
        UniqueConstraint("session_token_hash", name="uq_app_session_token_hash"),
        CheckConstraint("length(session_token_hash) = 64", name="session_token_hash_valid"),
        CheckConstraint("length(csrf_token_hash) = 64", name="csrf_token_hash_valid"),
        CheckConstraint("expires_at <= absolute_expires_at", name="session_expiry_valid"),
        CheckConstraint("status IN ('active','revoked','expired')", name="session_status_valid"),
        ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_app_session_user_tenant", ondelete="RESTRICT",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_app_session_active_user", "tenant_id", "app_user_id", "status", "expires_at"),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    app_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class AppLoginAttempt(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_login_attempt"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_login_attempt_user_tenant", ondelete="RESTRICT",
        ),
        Index("ix_login_attempt_username_window", "tenant_id", "username_normalized", "attempt_at"),
        Index("ix_login_attempt_ip_window", "tenant_id", "client_ip", "attempt_at"),
    )
    login_attempt_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    username_normalized: Mapped[str] = mapped_column(String(128), nullable=False)
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(1024))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(64))


class AppPasswordHistory(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_password_history"
    __table_args__ = (
        CheckConstraint("length(password_hash) >= 80", name="password_hash_format"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_password_history_user_tenant", ondelete="RESTRICT",
        ),
        Index("ix_password_history_user_created", "tenant_id", "app_user_id", "created_at"),
    )
    password_history_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    app_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)


class AppPermission(AuditMixin, Base):
    __tablename__ = "app_permission"
    permission_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    permission_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    permission_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LifecycleStatus] = mapped_column(String(32), nullable=False)


class AppRolePermission(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_role_permission"
    __table_args__ = (
        UniqueConstraint("tenant_id", "app_role_id", "permission_id", name="uq_role_permission_tenant_role_permission"),
        CheckConstraint("status IN ('active','inactive')", name="role_permission_status_valid"),
        ForeignKeyConstraint(
            ["granted_by", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_role_permission_granter_tenant", ondelete="RESTRICT",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_role_permission_active", "tenant_id", "app_role_id", "status"),
    )
    role_permission_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    app_role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_role.app_role_id", ondelete="RESTRICT"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_permission.permission_id", ondelete="RESTRICT"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class AppSecurityEvent(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_security_event"
    __table_args__ = (
        CheckConstraint("result IN ('success','failure','denied','override')", name="security_event_result_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_security_event_user_tenant", ondelete="RESTRICT",
        ),
        Index("ix_security_event_tenant_created", "tenant_id", "created_at"),
        Index("ix_security_event_action_created", "action", "created_at"),
    )
    security_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(128), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(255))
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(512))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(1024))
    request_id: Mapped[str | None] = mapped_column(String(128))
