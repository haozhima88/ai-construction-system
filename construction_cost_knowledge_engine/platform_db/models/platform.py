from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AuditMixin, Base, ImportItemStatus, ImportJobStatus, LifecycleStatus, TenantMixin


class AppTenant(AuditMixin, Base):
    __tablename__ = "app_tenant"
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    tenant_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tenant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status"), nullable=False)


class AppUser(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("tenant_id", "login_name", name="uq_app_user_tenant_login"),
        UniqueConstraint("tenant_id", "login_name_normalized", name="uq_app_user_tenant_login_normalized"),
        UniqueConstraint("tenant_id", "email", name="uq_app_user_tenant_email"),
        UniqueConstraint("app_user_id", "tenant_id", name="uq_app_user_id_tenant"),
        CheckConstraint("auth_version > 0", name="auth_version_positive"),
        CheckConstraint("is_service_account OR password_hash IS NOT NULL", name="password_required_for_local_user"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    app_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    login_name: Mapped[str] = mapped_column(String(128), nullable=False)
    login_name_normalized: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(512))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_service_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lockout_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_version: Mapped[int] = mapped_column(nullable=False, default=1)


class AppRole(AuditMixin, Base):
    __tablename__ = "app_role"
    app_role_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    role_name: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class AppUserRoleAssignment(TenantMixin, AuditMixin, Base):
    __tablename__ = "app_user_role_assignment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "app_user_id", "app_role_id", "effective_from"),
        ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_role_assignment_user_tenant", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assigned_by", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_role_assignment_assigner_tenant", ondelete="RESTRICT",
        ),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="effective_period_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_role_assignment_active", "tenant_id", "app_user_id", "app_role_id", "status"),
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    app_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    app_role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_role.app_role_id", ondelete="RESTRICT"), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class ReleaseManifest(AuditMixin, Base):
    __tablename__ = "release_manifest"
    release_manifest_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    manifest_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    application_version: Mapped[str] = mapped_column(String(128), nullable=False)
    database_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    reference_release_id: Mapped[str | None] = mapped_column(String(160))
    mapping_release_id: Mapped[str | None] = mapped_column(String(160))
    enterprise_price_release_id: Mapped[str | None] = mapped_column(String(160))
    enterprise_quota_release_id: Mapped[str | None] = mapped_column(String(160))
    source_hash_manifest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    docker_image_tag: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_manifest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release_manifest.release_manifest_id", ondelete="RESTRICT"))


class ReleaseArtifact(AuditMixin, Base):
    __tablename__ = "release_artifact"
    __table_args__ = (
        UniqueConstraint("release_manifest_id", "artifact_id", "artifact_path"),
        CheckConstraint("length(sha256) = 64", name="sha256_required"),
        CheckConstraint("file_size_bytes >= 0", name="file_size_nonnegative"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    release_artifact_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    release_manifest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("release_manifest.release_manifest_id", ondelete="RESTRICT"), nullable=False)
    artifact_group: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_role: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    record_count: Mapped[int | None] = mapped_column(BigInteger)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class SchemaMigration(AuditMixin, Base):
    __tablename__ = "schema_migration"
    schema_migration_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    release_manifest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release_manifest.release_manifest_id", ondelete="RESTRICT"))
    migration_version: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    migration_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SystemAuditEvent(TenantMixin, AuditMixin, Base):
    __tablename__ = "system_audit_event"
    system_audit_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    release_manifest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release_manifest.release_manifest_id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(255))
    before_payload: Mapped[dict | None] = mapped_column(JSONB)
    after_payload: Mapped[dict | None] = mapped_column(JSONB)


class PlatformImportJob(TenantMixin, AuditMixin, Base):
    __tablename__ = "platform_import_job"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint("record_count >= 0 AND success_count >= 0 AND failure_count >= 0", name="counts_nonnegative"),
        CheckConstraint("success_count + failure_count <= record_count", name="counts_within_total"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    import_job_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    import_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_release_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(Enum(ImportJobStatus, name="import_job_status"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class PlatformImportJobItem(AuditMixin, Base):
    __tablename__ = "platform_import_job_item"
    __table_args__ = (
        UniqueConstraint("import_job_id", "source_entity", "source_key"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    import_job_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    import_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_import_job.import_job_id", ondelete="RESTRICT"), nullable=False)
    source_entity: Mapped[str] = mapped_column(String(128), nullable=False)
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    target_entity: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    status: Mapped[ImportItemStatus] = mapped_column(Enum(ImportItemStatus, name="import_item_status"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
