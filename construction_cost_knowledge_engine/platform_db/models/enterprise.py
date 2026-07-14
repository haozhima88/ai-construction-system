from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AuditMixin, Base, EnterpriseQuotaState, EnterpriseReviewStatus, LifecycleStatus, TenantMixin


class EnterpriseResource(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_resource"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", "specification", "unit"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_reference_resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT"))
    resource_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    specification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class EnterprisePriceObservation(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_price_observation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "supplier_or_source", "external_key", "observed_at"),
        CheckConstraint("price_value >= 0", name="price_nonnegative"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_price_observation_resource_time", "enterprise_resource_id", "observed_at"),
    )
    enterprise_price_observation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_document.source_document_id", ondelete="RESTRICT"))
    external_key: Mapped[str] = mapped_column(String(255), nullable=False)
    price_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    price_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(128))
    supplier_or_source: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[EnterpriseReviewStatus] = mapped_column(Enum(EnterpriseReviewStatus, name="enterprise_review_status"), nullable=False)


class EnterprisePriceVersion(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_price_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "enterprise_resource_id", "version_no"),
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint("price_value >= 0", name="price_nonnegative"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="effective_period_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_price_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False)
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT"))
    version_no: Mapped[int] = mapped_column(nullable=False)
    price_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    price_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    review_status: Mapped[EnterpriseReviewStatus] = mapped_column(Enum(EnterpriseReviewStatus, name="enterprise_review_status", create_type=False), nullable=False)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))


class EnterprisePriceApproval(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_price_approval"
    __table_args__ = (
        UniqueConstraint("enterprise_price_version_id", "approval_round"),
        CheckConstraint("approval_round > 0", name="approval_round_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_price_approval_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_price_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT"), nullable=False)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    approval_round: Mapped[int] = mapped_column(nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)


class EnterprisePriceSnapshot(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_price_snapshot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_code"),
        CheckConstraint("length(snapshot_sha256) = 64", name="snapshot_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_price_snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    price_release_id: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_code: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_release_id: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class EnterprisePriceSnapshotLine(AuditMixin, Base):
    __tablename__ = "enterprise_price_snapshot_line"
    __table_args__ = (
        UniqueConstraint("enterprise_price_snapshot_id", "enterprise_resource_id"),
        CheckConstraint("price_value >= 0", name="price_nonnegative"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    snapshot_line_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_price_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_price_snapshot.enterprise_price_snapshot_id", ondelete="RESTRICT"), nullable=False)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False)
    enterprise_price_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT"), nullable=False)
    price_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)


class EnterpriseQuota(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota"
    __table_args__ = (
        UniqueConstraint("tenant_id", "enterprise_quota_code"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    standard_family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standard_family.standard_family_id", ondelete="RESTRICT"), nullable=False)
    source_reference_quota_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_quota_item.reference_quota_item_id", ondelete="RESTRICT"))
    enterprise_quota_code: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class EnterpriseQuotaChangeSet(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_change_set"
    __table_args__ = (
        UniqueConstraint("enterprise_quota_id", "change_set_no"),
        CheckConstraint("change_set_no > 0", name="change_set_no_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_change_set_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota.enterprise_quota_id", ondelete="RESTRICT"), nullable=False)
    change_set_no: Mapped[int] = mapped_column(nullable=False)
    business_reason: Mapped[str] = mapped_column(Text, nullable=False)
    change_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class EnterpriseQuotaVersion(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_version"
    __table_args__ = (
        UniqueConstraint("enterprise_quota_id", "version_no"),
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_enterprise_quota_version_state", "tenant_id", "state"),
    )
    enterprise_quota_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota.enterprise_quota_id", ondelete="RESTRICT"), nullable=False)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("enterprise_quota_version.enterprise_quota_version_id", ondelete="RESTRICT"))
    change_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota_change_set.enterprise_quota_change_set_id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(nullable=False)
    state: Mapped[EnterpriseQuotaState] = mapped_column(Enum(EnterpriseQuotaState, name="enterprise_quota_state"), nullable=False)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnterpriseQuotaComponentVersion(AuditMixin, Base):
    __tablename__ = "enterprise_quota_component_version"
    __table_args__ = (
        UniqueConstraint("enterprise_quota_version_id", "line_no"),
        CheckConstraint("line_no > 0", name="line_no_positive"),
        CheckConstraint("consumption >= 0", name="consumption_nonnegative"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_component_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota_version.enterprise_quota_version_id", ondelete="RESTRICT"), nullable=False)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False)
    source_reference_resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT"))
    line_no: Mapped[int] = mapped_column(nullable=False)
    consumption: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)


class EnterpriseQuotaRuleVersion(AuditMixin, Base):
    __tablename__ = "enterprise_quota_rule_version"
    __table_args__ = (
        UniqueConstraint("enterprise_quota_version_id", "rule_type", "ordinal"),
        CheckConstraint("ordinal > 0", name="ordinal_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_rule_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota_version.enterprise_quota_version_id", ondelete="RESTRICT"), nullable=False)
    source_rule_block_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_rule_block.reference_rule_block_id", ondelete="RESTRICT"))
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    enterprise_reason: Mapped[str | None] = mapped_column(Text)


class EnterpriseQuotaReviewEvent(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_review_event"
    enterprise_quota_review_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota_version.enterprise_quota_version_id", ondelete="RESTRICT"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    evidence_payload: Mapped[dict | None] = mapped_column(JSONB)


class EnterpriseQuotaRelease(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_release"
    __table_args__ = (
        UniqueConstraint("tenant_id", "semantic_version"),
        CheckConstraint("length(release_sha256) = 64", name="release_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_release_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    release_manifest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("release_manifest.release_manifest_id", ondelete="RESTRICT"), nullable=False)
    enterprise_price_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_price_snapshot.enterprise_price_snapshot_id", ondelete="RESTRICT"), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(64), nullable=False)
    quota_version_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    release_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_release_id: Mapped[str | None] = mapped_column(ForeignKey("enterprise_quota_release.enterprise_quota_release_id", ondelete="RESTRICT"))
