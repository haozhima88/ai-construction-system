"""Add provincial fallback and manual Enterprise Price governance.

Revision ID: 0005_price_fallback_a111
Revises: 0004_enterprise_price_a111_pilot
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_price_fallback_a111"
down_revision: str | None = "0004_enterprise_price_a111_pilot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
    ]


def upgrade() -> None:
    op.add_column("enterprise_price_version", sa.Column("version_type", sa.String(64), server_default="legacy", nullable=False))
    op.add_column("enterprise_price_version", sa.Column("reference_resource_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("reference_release_id", sa.String(160), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("reference_resource_code", sa.String(128), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("price_source_type", sa.String(64), server_default="legacy", nullable=False))
    op.add_column("enterprise_price_version", sa.Column("is_fallback", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("enterprise_price_version", sa.Column("requires_manual_review", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("enterprise_price_version", sa.Column("fallback_reason", sa.Text(), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("source_hash", sa.String(64), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("pricing_review_status", sa.String(64), server_default="pending_manual_pricing", nullable=False))
    op.create_foreign_key(
        "fk_enterprise_price_version_reference_resource",
        "enterprise_price_version", "reference_quota_resource",
        ["reference_resource_id"], ["reference_quota_resource_id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_enterprise_price_version_reference_release",
        "enterprise_price_version", "reference_release",
        ["reference_release_id"], ["reference_release_id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "enterprise_price_version_type_allowed", "enterprise_price_version",
        "version_type IN ('legacy', 'provincial_reference_fallback', 'enterprise_manual_price_draft')",
    )
    op.create_check_constraint(
        "enterprise_price_source_type_allowed", "enterprise_price_version",
        "price_source_type IN ('legacy', 'provincial_reference_fallback', 'enterprise_manual_price')",
    )
    op.create_check_constraint(
        "enterprise_price_pricing_review_status_allowed", "enterprise_price_version",
        "pricing_review_status IN ('pending_manual_pricing', 'reviewed_fallback_accepted', "
        "'manual_price_draft', 'manual_price_reviewed', 'returned_for_revision')",
    )
    op.create_check_constraint(
        "enterprise_price_source_hash_valid", "enterprise_price_version",
        "source_hash IS NULL OR length(source_hash) = 64",
    )
    op.create_check_constraint(
        "enterprise_price_fallback_consistent", "enterprise_price_version",
        "(is_fallback = false) OR (price_source_type = 'provincial_reference_fallback' "
        "AND reference_resource_id IS NOT NULL AND reference_release_id IS NOT NULL)",
    )

    op.create_table(
        "enterprise_price_change_set",
        sa.Column("enterprise_price_change_set_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("enterprise_resource_id", sa.Uuid(), nullable=False),
        sa.Column("previous_price_version_id", sa.Uuid(), nullable=True),
        sa.Column("new_price_version_id", sa.Uuid(), nullable=False),
        sa.Column("previous_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("new_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("change_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("change_percentage", sa.Numeric(20, 6), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        *audit_columns(),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["app_tenant.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["enterprise_resource_id"], ["enterprise_resource.enterprise_resource_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_price_version_id"], ["enterprise_price_version.enterprise_price_version_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_price_version_id"], ["enterprise_price_version.enterprise_price_version_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["changed_by"], ["app_user.app_user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("enterprise_price_change_set_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_enterprise_price_change_set_tenant_idempotency"),
    )
    op.create_index("ix_enterprise_price_change_set_tenant_id", "enterprise_price_change_set", ["tenant_id"])
    op.create_index("ix_enterprise_price_change_set_resource", "enterprise_price_change_set", ["enterprise_resource_id", "changed_at"])

    op.create_table(
        "enterprise_quota_historical_observation",
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_no", sa.Integer(), nullable=False),
        sa.Column("quota_code", sa.String(128), nullable=True),
        sa.Column("quota_name", sa.String(512), nullable=False),
        sa.Column("labor_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("material_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("machine_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("management_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("total_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("observation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_context", sa.Text(), nullable=True),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("tax_mode", sa.String(64), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(64), nullable=False),
        *audit_columns(),
        sa.CheckConstraint("length(payload_hash) = 64", name="payload_hash_valid"),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["app_tenant.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["enterprise_price_source_document.source_price_document_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("observation_id"),
        sa.UniqueConstraint("source_document_id", "source_row_no", name="uq_enterprise_quota_observation_document_row"),
    )
    op.create_index("ix_enterprise_quota_historical_observation_tenant_id", "enterprise_quota_historical_observation", ["tenant_id"])
    op.create_index("ix_enterprise_quota_historical_observation_quota", "enterprise_quota_historical_observation", ["quota_code"])

    op.execute("""
    CREATE TRIGGER trg_enterprise_price_change_set_row_version
      BEFORE UPDATE ON enterprise_price_change_set
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    CREATE TRIGGER trg_enterprise_quota_historical_observation_row_version
      BEFORE UPDATE ON enterprise_quota_historical_observation
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    """)


def downgrade() -> None:
    op.drop_index("ix_enterprise_quota_historical_observation_quota", table_name="enterprise_quota_historical_observation")
    op.drop_index("ix_enterprise_quota_historical_observation_tenant_id", table_name="enterprise_quota_historical_observation")
    op.drop_table("enterprise_quota_historical_observation")
    op.drop_index("ix_enterprise_price_change_set_resource", table_name="enterprise_price_change_set")
    op.drop_index("ix_enterprise_price_change_set_tenant_id", table_name="enterprise_price_change_set")
    op.drop_table("enterprise_price_change_set")
    for name in (
        "enterprise_price_fallback_consistent", "enterprise_price_source_hash_valid",
        "enterprise_price_pricing_review_status_allowed", "enterprise_price_source_type_allowed",
        "enterprise_price_version_type_allowed",
    ):
        op.drop_constraint(name, "enterprise_price_version", type_="check")
    op.drop_constraint("fk_enterprise_price_version_reference_release", "enterprise_price_version", type_="foreignkey")
    op.drop_constraint("fk_enterprise_price_version_reference_resource", "enterprise_price_version", type_="foreignkey")
    for column in (
        "pricing_review_status", "source_hash", "fallback_reason", "requires_manual_review", "is_fallback",
        "price_source_type", "reference_resource_code", "reference_release_id", "reference_resource_id", "version_type",
    ):
        op.drop_column("enterprise_price_version", column)
