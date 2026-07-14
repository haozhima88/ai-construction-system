from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, CheckConstraint, Enum, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AuditMixin, Base, LifecycleStatus, NoApprovedReviewStatus, ReleaseStatus, SourceRole


class StandardFamily(AuditMixin, Base):
    __tablename__ = "standard_family"
    __table_args__ = (
        UniqueConstraint("family_code", "edition"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    standard_family_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    family_code: Mapped[str] = mapped_column(String(128), nullable=False)
    family_name: Mapped[str] = mapped_column(String(255), nullable=False)
    edition: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class SourceDocument(AuditMixin, Base):
    __tablename__ = "source_document"
    __table_args__ = (
        UniqueConstraint("sha256"),
        UniqueConstraint("source_key"),
        CheckConstraint("length(sha256) = 64", name="sha256_valid"),
        CheckConstraint("source_role <> 'authority_source' OR authority_status LIKE 'official%'", name="authority_role_status"),
        CheckConstraint("source_role <> 'extraction_proxy' OR authority_status LIKE 'non_authoritative%'", name="proxy_role_status"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    standard_family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standard_family.standard_family_id", ondelete="RESTRICT"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)
    actual_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int | None] = mapped_column()
    source_role: Mapped[SourceRole] = mapped_column(Enum(SourceRole, name="source_role"), nullable=False)
    authority_status: Mapped[str] = mapped_column(String(128), nullable=False)
    readable_status: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status"), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class SourcePageEvidence(AuditMixin, Base):
    __tablename__ = "source_page_evidence"
    __table_args__ = (
        UniqueConstraint("source_document_id", "source_key"),
        CheckConstraint("page_no IS NULL OR page_no > 0", name="page_no_positive"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_source_page_evidence_locator", "source_document_id", "page_no", "evidence_type"),
    )
    source_page_evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_document.source_document_id", ondelete="RESTRICT"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    page_no: Mapped[int | None] = mapped_column()
    printed_page_no: Mapped[str | None] = mapped_column(String(64))
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_locator: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_payload: Mapped[dict | None] = mapped_column(JSONB)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ReferenceRelease(AuditMixin, Base):
    __tablename__ = "reference_release"
    __table_args__ = (
        UniqueConstraint("standard_family_id", "semantic_version"),
        CheckConstraint("length(source_hash_manifest) = 64", name="source_hash_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    reference_release_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    standard_family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standard_family.standard_family_id", ondelete="RESTRICT"), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(64), nullable=False)
    release_status: Mapped[ReleaseStatus] = mapped_column(Enum(ReleaseStatus, name="release_status"), nullable=False)
    source_hash_manifest: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_release_id: Mapped[str | None] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"))


class ReferenceBillItem(AuditMixin, Base):
    __tablename__ = "reference_bill_item"
    __table_args__ = (
        UniqueConstraint("reference_release_id", "bill_code_9", name="uq_reference_bill_release_code"),
        UniqueConstraint("reference_bill_item_id", "reference_release_id"),
        UniqueConstraint("reference_release_id", "source_key", name="uq_reference_bill_release_source"),
        CheckConstraint("bill_code_9 ~ '^[0-9]{9}$'", name="bill_code_9_valid"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_reference_bill_search", "reference_release_id", "appendix_code", "section_code"),
    )
    reference_bill_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_document.source_document_id", ondelete="RESTRICT"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    bill_code_9: Mapped[str] = mapped_column(String(9), nullable=False)
    bill_name: Mapped[str] = mapped_column(String(512), nullable=False)
    appendix_code: Mapped[str] = mapped_column(String(16), nullable=False)
    appendix_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_code: Mapped[str] = mapped_column(String(64), nullable=False)
    section_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    project_feature_raw: Mapped[str | None] = mapped_column(Text)
    quantity_calculation_rule: Mapped[str | None] = mapped_column(Text)
    work_content_raw: Mapped[str | None] = mapped_column(Text)
    source_heading_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_table_index: Mapped[int | None] = mapped_column()
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ReferenceQuotaItem(AuditMixin, Base):
    __tablename__ = "reference_quota_item"
    __table_args__ = (
        UniqueConstraint("reference_release_id", "volume_code", "source_code", name="uq_reference_quota_release_code"),
        UniqueConstraint("reference_quota_item_id", "reference_release_id"),
        UniqueConstraint("reference_release_id", "source_key", name="uq_reference_quota_release_source"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_reference_quota_search", "reference_release_id", "volume_code", "chapter_code", "section_code"),
    )
    reference_quota_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_document.source_document_id", ondelete="RESTRICT"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    quota_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    volume_code: Mapped[str] = mapped_column(String(16), nullable=False)
    source_code: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_name: Mapped[str] = mapped_column(String(512), nullable=False)
    specification: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(64))
    chapter_code: Mapped[str | None] = mapped_column(String(64))
    section_code: Mapped[str | None] = mapped_column(String(64))
    pdf_page_no: Mapped[int | None] = mapped_column()
    labor_fee: Mapped[float | None] = mapped_column(Numeric(20, 6))
    material_fee: Mapped[float | None] = mapped_column(Numeric(20, 6))
    machine_fee: Mapped[float | None] = mapped_column(Numeric(20, 6))
    management_fee: Mapped[float | None] = mapped_column(Numeric(20, 6))
    total_fee: Mapped[float | None] = mapped_column(Numeric(20, 6))
    source_role: Mapped[SourceRole] = mapped_column(Enum(SourceRole, name="source_role", create_type=False), nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    parse_confidence: Mapped[float | None] = mapped_column(Float)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ReferenceQuotaResource(AuditMixin, Base):
    __tablename__ = "reference_quota_resource"
    __table_args__ = (
        UniqueConstraint("reference_release_id", "source_key"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_reference_resource_quota", "reference_quota_item_id", "source_row_order"),
    )
    reference_quota_resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    reference_quota_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reference_quota_item.reference_quota_item_id", ondelete="RESTRICT"), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_document.source_document_id", ondelete="RESTRICT"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_category: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_code: Mapped[str | None] = mapped_column(String(128))
    resource_name: Mapped[str] = mapped_column(String(512), nullable=False)
    specification: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(64))
    consumption: Mapped[float | None] = mapped_column(Numeric(20, 8))
    unit_price: Mapped[float | None] = mapped_column(Numeric(20, 6))
    component_amount: Mapped[float | None] = mapped_column(Numeric(20, 6))
    source_page_no: Mapped[int | None] = mapped_column()
    source_row_order: Mapped[int | None] = mapped_column()
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ReferenceRuleBlock(AuditMixin, Base):
    __tablename__ = "reference_rule_block"
    __table_args__ = (
        UniqueConstraint("reference_release_id", "source_key"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_reference_rule_locator", "reference_release_id", "rule_type", "pdf_page_no"),
    )
    reference_rule_block_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_document.source_document_id", ondelete="RESTRICT"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_code: Mapped[str | None] = mapped_column(String(128))
    rule_title: Mapped[str | None] = mapped_column(Text)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_page_no: Mapped[int | None] = mapped_column()
    source_locator: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ReferenceScopeLink(AuditMixin, Base):
    __tablename__ = "reference_scope_link"
    __table_args__ = (
        UniqueConstraint("reference_release_id", "source_key"),
        CheckConstraint("reference_quota_item_id IS NOT NULL OR reference_bill_item_id IS NOT NULL OR scope_type <> 'item'", name="scope_target_present"),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_reference_scope_rule", "reference_rule_block_id", "scope_type"),
    )
    reference_scope_link_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    reference_rule_block_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reference_rule_block.reference_rule_block_id", ondelete="RESTRICT"), nullable=False)
    reference_quota_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_quota_item.reference_quota_item_id", ondelete="RESTRICT"))
    reference_bill_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_bill_item.reference_bill_item_id", ondelete="RESTRICT"))
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_start_code: Mapped[str | None] = mapped_column(String(128))
    scope_end_code: Mapped[str | None] = mapped_column(String(128))
    scope_confidence: Mapped[float | None] = mapped_column(Float)
    scope_status: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
