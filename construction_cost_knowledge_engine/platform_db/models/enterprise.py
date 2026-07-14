from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AuditMixin, Base, EnterpriseQuotaState, EnterpriseReviewStatus, LifecycleStatus, TenantMixin


class EnterprisePriceSourceDocument(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_price_source_document"
    __table_args__ = (
        UniqueConstraint("tenant_id", "absolute_path", "sha256", name="uq_enterprise_price_source_document_path_hash"),
        CheckConstraint("record_count >= 0", name="record_count_nonnegative"),
        CheckConstraint("length(sha256) = 64", name="sha256_valid"),
        CheckConstraint(
            "source_role IN ('enterprise_price_source_candidate', "
            "'enterprise_historical_observation', 'market_reference', 'unknown_price_source')",
            name="source_role_allowed",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    source_price_document_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    absolute_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    record_count: Mapped[int] = mapped_column(nullable=False)
    resource_code_status: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name_status: Mapped[str] = mapped_column(String(64), nullable=False)
    specification_status: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_status: Mapped[str] = mapped_column(String(64), nullable=False)
    price_status: Mapped[str] = mapped_column(String(96), nullable=False)
    tax_mode_status: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_date_status: Mapped[str] = mapped_column(String(64), nullable=False)
    region_status: Mapped[str] = mapped_column(String(64), nullable=False)
    source_role: Mapped[str] = mapped_column(String(64), nullable=False)
    authority_status: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False)


class EnterpriseResource(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_resource"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", "specification", "unit"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_reference_resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT"))
    resource_code: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    resource_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    specification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class EnterpriseResourceReferenceLink(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_resource_reference_link"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "enterprise_resource_id", "reference_resource_id",
            name="uq_enterprise_resource_reference_link_pair",
        ),
        CheckConstraint("match_score >= 0 AND match_score <= 1", name="match_score_range"),
        CheckConstraint(
            "match_method IN ('exact_code', 'normalized_code', 'exact_name_spec_unit', "
            "'semantic_candidate', 'manual_link', 'unmatched')",
            name="match_method_allowed",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_enterprise_resource_reference_link_reference", "reference_resource_id"),
    )
    link_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False
    )
    reference_resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT"), nullable=False
    )
    reference_resource_code: Mapped[str] = mapped_column(String(128), nullable=False)
    match_method: Mapped[str] = mapped_column(String(64), nullable=False)
    match_score: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    name_match_status: Mapped[str] = mapped_column(String(64), nullable=False)
    specification_match_status: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_match_status: Mapped[str] = mapped_column(String(64), nullable=False)
    category_match_status: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")


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
        CheckConstraint(
            "version_type IN ('legacy', 'provincial_reference_fallback', 'enterprise_manual_price_draft')",
            name="version_type_allowed",
        ),
        CheckConstraint(
            "price_source_type IN ('legacy', 'provincial_reference_fallback', 'enterprise_manual_price')",
            name="source_type_allowed",
        ),
        CheckConstraint(
            "pricing_review_status IN ('pending_manual_pricing', 'reviewed_fallback_accepted', "
            "'manual_price_draft', 'manual_price_reviewed', 'returned_for_revision')",
            name="pricing_review_status_allowed",
        ),
        CheckConstraint("source_hash IS NULL OR length(source_hash) = 64", name="source_hash_valid"),
        CheckConstraint(
            "(is_fallback = false) OR (price_source_type = 'provincial_reference_fallback' "
            "AND reference_resource_id IS NOT NULL AND reference_release_id IS NOT NULL)",
            name="fallback_consistent",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_price_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False)
    source_price_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_price_source_document.source_price_document_id", ondelete="RESTRICT")
    )
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT"))
    version_no: Mapped[int] = mapped_column(nullable=False)
    price_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    price_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(128))
    supplier_or_source: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Numeric(8, 6))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    review_status: Mapped[EnterpriseReviewStatus] = mapped_column(Enum(EnterpriseReviewStatus, name="enterprise_review_status", create_type=False), nullable=False)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    version_type: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    reference_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT")
    )
    reference_release_id: Mapped[str | None] = mapped_column(
        ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT")
    )
    reference_resource_code: Mapped[str | None] = mapped_column(String(128))
    price_source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fallback_reason: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    pricing_review_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending_manual_pricing")


class EnterprisePriceChangeSet(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_price_change_set"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_enterprise_price_change_set_tenant_idempotency"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_enterprise_price_change_set_resource", "enterprise_resource_id", "changed_at"),
    )
    enterprise_price_change_set_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False
    )
    previous_price_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT")
    )
    new_price_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT"), nullable=False
    )
    previous_price: Mapped[float | None] = mapped_column(Numeric(20, 6))
    new_price: Mapped[float | None] = mapped_column(Numeric(20, 6))
    change_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    change_percentage: Mapped[float | None] = mapped_column(Numeric(20, 6))
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)


class EnterpriseQuotaHistoricalObservation(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_historical_observation"
    __table_args__ = (
        UniqueConstraint("source_document_id", "source_row_no", name="uq_enterprise_quota_observation_document_row"),
        CheckConstraint("length(payload_hash) = 64", name="payload_hash_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_enterprise_quota_historical_observation_quota", "quota_code"),
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_price_source_document.source_price_document_id", ondelete="RESTRICT"), nullable=False
    )
    source_row_no: Mapped[int] = mapped_column(nullable=False)
    quota_code: Mapped[str | None] = mapped_column(String(128))
    quota_name: Mapped[str] = mapped_column(String(512), nullable=False)
    labor_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    material_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    machine_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    management_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    total_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    observation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    project_context: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(128))
    tax_mode: Mapped[str | None] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False)


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
    snapshot_type: Mapped[str] = mapped_column(String(32), nullable=False, default="preview")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    calculation_rule_version: Mapped[str] = mapped_column(String(64), nullable=False, default="enterprise_decimal_v1")


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
    enterprise_price_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT"))
    price_value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    price_type: Mapped[str | None] = mapped_column(String(64))
    price_source: Mapped[str | None] = mapped_column(String(255))
    source_price_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_price_source_document.source_price_document_id", ondelete="RESTRICT")
    )
    resource_reference_link_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_resource_reference_link.link_id", ondelete="RESTRICT")
    )
    calculation_rule_version: Mapped[str] = mapped_column(String(64), nullable=False, default="enterprise_decimal_v1")
    mapping_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


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
    unit: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class EnterpriseQuotaChangeSet(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_change_set"
    __table_args__ = (
        UniqueConstraint("enterprise_quota_id", "change_set_no"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_enterprise_quota_change_set_tenant_idempotency"),
        CheckConstraint("change_set_no > 0", name="change_set_no_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_change_set_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota.enterprise_quota_id", ondelete="RESTRICT"), nullable=False)
    change_set_no: Mapped[int] = mapped_column(nullable=False)
    business_reason: Mapped[str] = mapped_column(Text, nullable=False)
    change_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    before_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    after_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[str | None] = mapped_column(String(180))


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
    source_quota_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    source_quota_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_quota_version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    work_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enterprise_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    calculation_rule_version: Mapped[str] = mapped_column(String(64), nullable=False, default="enterprise_decimal_v1")
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
        CheckConstraint("consumption IS NULL OR consumption >= 0", name="consumption_nonnegative"),
        CheckConstraint(
            "calculation_basis IN ('quantity_unit_price', 'direct_amount', 'rate_based', 'formula_based')",
            name="calculation_basis_allowed",
        ),
        CheckConstraint(
            "component_status IN ('inherited', 'quantity_modified', 'amount_modified', 'resource_added', "
            "'resource_replaced', 'resource_removed', 'restored')",
            name="component_status_allowed",
        ),
        CheckConstraint("lifecycle_status IN ('active', 'removed')", name="lifecycle_status_allowed"),
        CheckConstraint("enterprise_direct_amount IS NULL OR enterprise_direct_amount >= 0", name="direct_amount_nonnegative"),
        CheckConstraint("enterprise_rate IS NULL OR enterprise_rate >= 0", name="enterprise_rate_nonnegative"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    enterprise_quota_component_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    enterprise_quota_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_quota_version.enterprise_quota_version_id", ondelete="RESTRICT"), nullable=False)
    enterprise_resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_resource.enterprise_resource_id", ondelete="RESTRICT"), nullable=False)
    source_enterprise_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "enterprise_resource.enterprise_resource_id", ondelete="RESTRICT",
            name="fk_enterprise_quota_component_source_enterprise_resource",
        )
    )
    source_reference_resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT"))
    line_no: Mapped[int] = mapped_column(nullable=False)
    consumption: Mapped[float | None] = mapped_column(Numeric(20, 8))
    source_consumption: Mapped[float | None] = mapped_column(Numeric(20, 8))
    provincial_unit_price: Mapped[float | None] = mapped_column(Numeric(20, 6))
    provincial_component_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    enterprise_price_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_price_version.enterprise_price_version_id", ondelete="RESTRICT")
    )
    selected_enterprise_price: Mapped[float | None] = mapped_column(Numeric(20, 6))
    selected_price_type: Mapped[str | None] = mapped_column(String(64))
    enterprise_component_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    amount_source: Mapped[str] = mapped_column(String(64), nullable=False, default="enterprise_price_missing")
    override_reason: Mapped[str | None] = mapped_column(Text)
    calculation_basis: Mapped[str] = mapped_column(String(32), nullable=False, default="quantity_unit_price")
    source_direct_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    enterprise_direct_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    calculation_base: Mapped[float | None] = mapped_column(Numeric(20, 6))
    enterprise_rate: Mapped[float | None] = mapped_column(Numeric(20, 8))
    formula_code: Mapped[str | None] = mapped_column(String(128))
    formula_version: Mapped[str | None] = mapped_column(String(64))
    component_status: Mapped[str] = mapped_column(String(32), nullable=False, default="inherited")
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    specification_override: Mapped[str | None] = mapped_column(Text)


class EnterpriseComponentCalculationProfile(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_component_calculation_profile"
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference_resource_id", name="uq_component_calculation_profile_tenant_reference"),
        CheckConstraint(
            "calculation_basis IN ('quantity_unit_price', 'direct_amount', 'rate_based', 'formula_based')",
            name="calculation_basis_allowed",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_enterprise_component_calculation_profile_basis", "calculation_basis"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reference_resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reference_quota_resource.reference_quota_resource_id", ondelete="RESTRICT"), nullable=False
    )
    resource_code: Mapped[str | None] = mapped_column(String(128))
    resource_name: Mapped[str] = mapped_column(String(512), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64))
    calculation_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False, default="classified_draft")


class EnterpriseQuotaComponentChange(TenantMixin, AuditMixin, Base):
    __tablename__ = "enterprise_quota_component_change"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", "component_id", "field_name",
            name="uq_component_change_tenant_idempotency_component_field",
        ),
        CheckConstraint(
            "change_type IN ('quantity_modified', 'amount_modified', 'resource_added', 'resource_replaced', "
            "'resource_removed', 'restored', 'specification_modified')",
            name="change_type_allowed",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_enterprise_quota_component_change_version", "quota_version_id", "changed_at"),
    )
    component_change_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    quota_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_quota_version.enterprise_quota_version_id", ondelete="RESTRICT"), nullable=False
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_quota_component_version.enterprise_quota_component_version_id", ondelete="RESTRICT"), nullable=False
    )
    change_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_quota_change_set.enterprise_quota_change_set_id", ondelete="RESTRICT"), nullable=False
    )
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    before_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    after_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending_review")


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
