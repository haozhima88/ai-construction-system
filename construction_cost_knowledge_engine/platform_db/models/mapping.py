from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AuditMixin, Base, LifecycleStatus, NoApprovedReviewStatus, ReleaseStatus, TenantMixin


class MappingRelease(AuditMixin, Base):
    __tablename__ = "mapping_release"
    __table_args__ = (
        UniqueConstraint("reference_release_id", "semantic_version"),
        UniqueConstraint("mapping_release_id", "reference_release_id"),
        CheckConstraint("length(mapping_hash_manifest) = 64", name="mapping_hash_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    mapping_release_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    reference_release_id: Mapped[str] = mapped_column(ForeignKey("reference_release.reference_release_id", ondelete="RESTRICT"), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(64), nullable=False)
    release_status: Mapped[ReleaseStatus] = mapped_column(Enum(ReleaseStatus, name="release_status", create_type=False), nullable=False)
    mapping_hash_manifest: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_version: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_mapping_release_id: Mapped[str | None] = mapped_column(ForeignKey("mapping_release.mapping_release_id", ondelete="RESTRICT"))


class MappingWorkspace(TenantMixin, AuditMixin, Base):
    __tablename__ = "mapping_workspace"
    __table_args__ = (
        UniqueConstraint("mapping_workspace_id", "mapping_release_id"),
        UniqueConstraint("tenant_id", "mapping_release_id", "workspace_name"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    mapping_workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    mapping_release_id: Mapped[str] = mapped_column(ForeignKey("mapping_release.mapping_release_id", ondelete="RESTRICT"), nullable=False)
    workspace_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_status: Mapped[LifecycleStatus] = mapped_column(Enum(LifecycleStatus, name="lifecycle_status", create_type=False), nullable=False)


class MappingCandidateEdge(AuditMixin, Base):
    __tablename__ = "mapping_candidate_edge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mapping_release_id", "reference_release_id"],
            ["mapping_release.mapping_release_id", "mapping_release.reference_release_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reference_bill_item_id", "reference_release_id"],
            ["reference_bill_item.reference_bill_item_id", "reference_bill_item.reference_release_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reference_quota_item_id", "reference_release_id"],
            ["reference_quota_item.reference_quota_item_id", "reference_quota_item.reference_release_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("mapping_candidate_edge_id", "mapping_release_id"),
        UniqueConstraint("mapping_release_id", "source_key", name="uq_mapping_edge_release_source"),
        UniqueConstraint(
            "mapping_release_id", "reference_bill_item_id", "reference_quota_item_id", "mapping_role",
            name="uq_mapping_edge_release_pair_role",
        ),
        CheckConstraint("length(payload_sha256) = 64", name="payload_sha256_valid"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_mapping_edge_bill_rank", "mapping_release_id", "reference_bill_item_id", "candidate_rank"),
        Index("ix_mapping_edge_quota", "mapping_release_id", "reference_quota_item_id"),
    )
    mapping_candidate_edge_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    mapping_release_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reference_release_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reference_bill_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    reference_quota_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_role: Mapped[str] = mapped_column(String(128), nullable=False)
    routing_class: Mapped[str] = mapped_column(String(128), nullable=False)
    semantic_score: Mapped[float | None] = mapped_column(Float)
    source_evidence_status: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_reason: Mapped[str | None] = mapped_column(Text)
    ai_mapping_explanation: Mapped[str | None] = mapped_column(Text)
    candidate_rank: Mapped[int] = mapped_column(nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class MappingDraftEdge(TenantMixin, AuditMixin, Base):
    __tablename__ = "mapping_draft_edge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mapping_workspace_id", "mapping_release_id"],
            ["mapping_workspace.mapping_workspace_id", "mapping_workspace.mapping_release_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["mapping_candidate_edge_id", "mapping_release_id"],
            ["mapping_candidate_edge.mapping_candidate_edge_id", "mapping_candidate_edge.mapping_release_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("mapping_workspace_id", "source_draft_key"),
        CheckConstraint("revision_no > 0", name="revision_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_mapping_draft_workspace_status", "mapping_workspace_id", "draft_status"),
    )
    mapping_draft_edge_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    mapping_workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    mapping_release_id: Mapped[str] = mapped_column(String(160), nullable=False)
    mapping_candidate_edge_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_bill_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_bill_item.reference_bill_item_id", ondelete="RESTRICT"))
    source_draft_key: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    operation_reason: Mapped[str | None] = mapped_column(Text)
    revision_no: Mapped[int] = mapped_column(nullable=False, default=1)
    prior_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mapping_draft_edge.mapping_draft_edge_id", ondelete="RESTRICT"))
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class MappingReviewState(TenantMixin, AuditMixin, Base):
    __tablename__ = "mapping_review_state"
    __table_args__ = (
        CheckConstraint("(mapping_candidate_edge_id IS NULL) <> (mapping_draft_edge_id IS NULL)", name="single_subject"),
        UniqueConstraint("tenant_id", "subject_type", "subject_id", "review_cycle"),
        CheckConstraint("review_cycle > 0", name="review_cycle_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    mapping_review_state_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    mapping_candidate_edge_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mapping_candidate_edge.mapping_candidate_edge_id", ondelete="RESTRICT"))
    mapping_draft_edge_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mapping_draft_edge.mapping_draft_edge_id", ondelete="RESTRICT"))
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    review_cycle: Mapped[int] = mapped_column(nullable=False)
    review_status: Mapped[NoApprovedReviewStatus] = mapped_column(Enum(NoApprovedReviewStatus, name="no_approved_review_status", create_type=False), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"))
    comment: Mapped[str | None] = mapped_column(Text)


class MappingAuditEvent(TenantMixin, AuditMixin, Base):
    __tablename__ = "mapping_audit_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_audit_key"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index("ix_mapping_audit_order", "tenant_id", "mapping_workspace_id", "event_at"),
    )
    mapping_audit_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    mapping_workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mapping_workspace.mapping_workspace_id", ondelete="RESTRICT"), nullable=False)
    mapping_draft_edge_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mapping_draft_edge.mapping_draft_edge_id", ondelete="RESTRICT"))
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.app_user_id", ondelete="RESTRICT"), nullable=False)
    source_audit_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_at: Mapped[str] = mapped_column(String(64), nullable=False)
    before_payload: Mapped[dict | None] = mapped_column(JSONB)
    after_payload: Mapped[dict | None] = mapped_column(JSONB)
