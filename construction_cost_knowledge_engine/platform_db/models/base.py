from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, MetaData, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class NoApprovedReviewStatus(str, enum.Enum):
    pending = "pending"
    not_reviewed = "not_reviewed"
    reviewed = "reviewed"
    reviewed_candidate = "reviewed_candidate"
    needs_followup = "needs_followup"
    reviewed_mismatch = "reviewed_mismatch"
    rejected = "rejected"


class ReleaseStatus(str, enum.Enum):
    assembled = "assembled"
    validated = "validated"
    published = "published"
    superseded = "superseded"


class SourceRole(str, enum.Enum):
    authority_source = "authority_source"
    extraction_proxy = "extraction_proxy"


class LifecycleStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    inactive = "inactive"
    archived = "archived"
    retired = "retired"
    disabled = "disabled"


class ImportJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    completed_idempotent = "completed_idempotent"
    failed = "failed"


class ImportItemStatus(str, enum.Enum):
    imported = "imported"
    unchanged = "unchanged"
    failed = "failed"


class EnterpriseReviewStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    reviewed = "reviewed"
    approved = "approved"
    rejected = "rejected"
    published = "published"
    superseded = "superseded"


class EnterpriseQuotaState(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    reviewed = "reviewed"
    approved = "approved"
    published = "published"
    superseded = "superseded"


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    row_version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    @declared_attr.directive
    def __table_args__(cls):  # type: ignore[no-untyped-def]
        return (CheckConstraint("row_version > 0", name="row_version_positive"),)


class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_tenant.tenant_id", ondelete="RESTRICT"), nullable=False, index=True
    )


def text_id(length: int = 160) -> Mapped[str]:
    return mapped_column(String(length), nullable=False)  # type: ignore[return-value]
