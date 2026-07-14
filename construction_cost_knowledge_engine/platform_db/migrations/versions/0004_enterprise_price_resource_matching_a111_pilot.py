"""Add governed enterprise price/resource matching and A1.1 quota pilot fields.

Revision ID: 0004_enterprise_price_a111_pilot
Revises: 0003_postgres_review_cutover
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_enterprise_price_a111_pilot"
down_revision: str | None = "0003_postgres_review_cutover"
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
    op.create_table(
        "enterprise_price_source_document",
        sa.Column("source_price_document_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("absolute_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("resource_code_status", sa.String(64), nullable=False),
        sa.Column("resource_name_status", sa.String(64), nullable=False),
        sa.Column("specification_status", sa.String(64), nullable=False),
        sa.Column("unit_status", sa.String(64), nullable=False),
        sa.Column("price_status", sa.String(96), nullable=False),
        sa.Column("tax_mode_status", sa.String(64), nullable=False),
        sa.Column("effective_date_status", sa.String(64), nullable=False),
        sa.Column("region_status", sa.String(64), nullable=False),
        sa.Column("source_role", sa.String(64), nullable=False),
        sa.Column("authority_status", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(64), nullable=False),
        *audit_columns(),
        sa.CheckConstraint("record_count >= 0", name="record_count_nonnegative"),
        sa.CheckConstraint("length(sha256) = 64", name="sha256_valid"),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.CheckConstraint(
            "source_role IN ('enterprise_price_source_candidate', "
            "'enterprise_historical_observation', 'market_reference', 'unknown_price_source')",
            name="source_role_allowed",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["app_tenant.tenant_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("source_price_document_id"),
        sa.UniqueConstraint("tenant_id", "absolute_path", "sha256", name="uq_enterprise_price_source_document_path_hash"),
    )
    op.create_index("ix_enterprise_price_source_document_tenant_id", "enterprise_price_source_document", ["tenant_id"])

    op.add_column("enterprise_resource", sa.Column("resource_code", sa.String(128), server_default="", nullable=False))
    op.add_column("enterprise_resource", sa.Column("resource_category", sa.String(64), server_default="other", nullable=False))

    op.create_table(
        "enterprise_resource_reference_link",
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("enterprise_resource_id", sa.Uuid(), nullable=False),
        sa.Column("reference_resource_id", sa.Uuid(), nullable=False),
        sa.Column("reference_resource_code", sa.String(128), nullable=False),
        sa.Column("match_method", sa.String(64), nullable=False),
        sa.Column("match_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("name_match_status", sa.String(64), nullable=False),
        sa.Column("specification_match_status", sa.String(64), nullable=False),
        sa.Column("unit_match_status", sa.String(64), nullable=False),
        sa.Column("category_match_status", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(64), nullable=False),
        sa.Column("risk_reason", sa.Text(), nullable=False),
        *audit_columns(),
        sa.CheckConstraint("match_score >= 0 AND match_score <= 1", name="match_score_range"),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.CheckConstraint(
            "match_method IN ('exact_code', 'normalized_code', 'exact_name_spec_unit', "
            "'semantic_candidate', 'manual_link', 'unmatched')",
            name="match_method_allowed",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["app_tenant.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["enterprise_resource_id"], ["enterprise_resource.enterprise_resource_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reference_resource_id"], ["reference_quota_resource.reference_quota_resource_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("link_id"),
        sa.UniqueConstraint("tenant_id", "enterprise_resource_id", "reference_resource_id", name="uq_enterprise_resource_reference_link_pair"),
    )
    op.create_index("ix_enterprise_resource_reference_link_tenant_id", "enterprise_resource_reference_link", ["tenant_id"])
    op.create_index("ix_enterprise_resource_reference_link_reference", "enterprise_resource_reference_link", ["reference_resource_id"])

    op.add_column("enterprise_price_version", sa.Column("source_price_document_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("project_type", sa.String(128), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("supplier_or_source", sa.String(255), nullable=True))
    op.add_column("enterprise_price_version", sa.Column("confidence", sa.Numeric(8, 6), nullable=True))
    op.create_foreign_key(
        "fk_enterprise_price_version_source_price_document",
        "enterprise_price_version", "enterprise_price_source_document",
        ["source_price_document_id"], ["source_price_document_id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "confidence_range", "enterprise_price_version",
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
    )

    op.add_column("enterprise_quota", sa.Column("unit", sa.String(64), server_default="", nullable=False))

    op.add_column("enterprise_quota_change_set", sa.Column("before_value", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("enterprise_quota_change_set", sa.Column("after_value", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("enterprise_quota_change_set", sa.Column("change_type", sa.String(64), server_default="legacy", nullable=False))
    op.add_column("enterprise_quota_change_set", sa.Column("change_reason", sa.Text(), server_default="legacy", nullable=False))
    op.add_column("enterprise_quota_change_set", sa.Column("changed_by", sa.Uuid(), nullable=True))
    op.add_column("enterprise_quota_change_set", sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("enterprise_quota_change_set", sa.Column("request_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_quota_change_set", sa.Column("idempotency_key", sa.String(180), nullable=True))
    op.create_foreign_key(
        "fk_enterprise_quota_change_set_changed_by_app_user",
        "enterprise_quota_change_set", "app_user", ["changed_by"], ["app_user_id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_enterprise_quota_change_set_tenant_idempotency",
        "enterprise_quota_change_set", ["tenant_id", "idempotency_key"],
    )

    op.add_column("enterprise_quota_version", sa.Column("source_quota_uid", sa.String(255), server_default="", nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("source_quota_code", sa.String(128), server_default="", nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("source_quota_version_hash", sa.String(64), server_default=("0" * 64), nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("unit", sa.String(64), server_default="", nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("work_content", sa.Text(), server_default="", nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("enterprise_note", sa.Text(), server_default="", nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("change_reason", sa.Text(), server_default="fork_from_reference", nullable=False))
    op.add_column("enterprise_quota_version", sa.Column("calculation_rule_version", sa.String(64), server_default="enterprise_decimal_v1", nullable=False))
    op.create_check_constraint(
        "source_quota_version_hash_valid", "enterprise_quota_version",
        "length(source_quota_version_hash) = 64",
    )

    op.add_column("enterprise_quota_component_version", sa.Column("source_consumption", sa.Numeric(20, 8), server_default="0", nullable=False))
    op.add_column("enterprise_quota_component_version", sa.Column("provincial_unit_price", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("provincial_component_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("enterprise_price_version_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("selected_enterprise_price", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("selected_price_type", sa.String(64), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("enterprise_component_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("amount_source", sa.String(64), server_default="enterprise_price_missing", nullable=False))
    op.create_foreign_key(
        "fk_enterprise_quota_component_version_price_version",
        "enterprise_quota_component_version", "enterprise_price_version",
        ["enterprise_price_version_id"], ["enterprise_price_version_id"], ondelete="RESTRICT",
    )

    op.add_column("enterprise_price_snapshot", sa.Column("snapshot_type", sa.String(32), server_default="preview", nullable=False))
    op.add_column("enterprise_price_snapshot", sa.Column("status", sa.String(32), server_default="draft", nullable=False))
    op.add_column("enterprise_price_snapshot", sa.Column("calculation_rule_version", sa.String(64), server_default="enterprise_decimal_v1", nullable=False))
    op.create_check_constraint("snapshot_type_allowed", "enterprise_price_snapshot", "snapshot_type IN ('preview', 'frozen')")

    op.alter_column("enterprise_price_snapshot_line", "enterprise_price_version_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("enterprise_price_snapshot_line", "price_value", existing_type=sa.Numeric(20, 6), nullable=True)
    op.alter_column("enterprise_price_snapshot_line", "effective_from", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.add_column("enterprise_price_snapshot_line", sa.Column("price_type", sa.String(64), nullable=True))
    op.add_column("enterprise_price_snapshot_line", sa.Column("price_source", sa.String(255), nullable=True))
    op.add_column("enterprise_price_snapshot_line", sa.Column("source_price_document_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_price_snapshot_line", sa.Column("resource_reference_link_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_price_snapshot_line", sa.Column("calculation_rule_version", sa.String(64), server_default="enterprise_decimal_v1", nullable=False))
    op.add_column("enterprise_price_snapshot_line", sa.Column("mapping_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.create_foreign_key(
        "fk_enterprise_price_snapshot_line_source_document",
        "enterprise_price_snapshot_line", "enterprise_price_source_document",
        ["source_price_document_id"], ["source_price_document_id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_enterprise_price_snapshot_line_resource_link",
        "enterprise_price_snapshot_line", "enterprise_resource_reference_link",
        ["resource_reference_link_id"], ["link_id"], ondelete="RESTRICT",
    )

    op.execute("""
    CREATE OR REPLACE FUNCTION platform_guard_price_snapshot_immutable() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'Enterprise Price Snapshot history is immutable' USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION platform_guard_price_version_immutable() RETURNS trigger AS $$
    BEGIN
      IF OLD.review_status IN ('approved', 'published', 'superseded') THEN
        RAISE EXCEPTION 'approved or published Enterprise Price Version is immutable' USING ERRCODE = '55000';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER trg_enterprise_price_source_document_immutable
      BEFORE UPDATE OR DELETE ON enterprise_price_source_document
      FOR EACH ROW EXECUTE FUNCTION platform_guard_price_snapshot_immutable();
    CREATE TRIGGER trg_enterprise_price_snapshot_immutable
      BEFORE UPDATE OR DELETE ON enterprise_price_snapshot
      FOR EACH ROW EXECUTE FUNCTION platform_guard_price_snapshot_immutable();
    CREATE TRIGGER trg_enterprise_price_snapshot_line_immutable
      BEFORE UPDATE OR DELETE ON enterprise_price_snapshot_line
      FOR EACH ROW EXECUTE FUNCTION platform_guard_price_snapshot_immutable();
    CREATE TRIGGER trg_enterprise_price_version_immutable
      BEFORE UPDATE OR DELETE ON enterprise_price_version
      FOR EACH ROW EXECUTE FUNCTION platform_guard_price_version_immutable();

    CREATE TRIGGER trg_enterprise_resource_reference_link_row_version
      BEFORE UPDATE ON enterprise_resource_reference_link
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    CREATE TRIGGER trg_enterprise_quota_version_row_version
      BEFORE UPDATE ON enterprise_quota_version
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    CREATE TRIGGER trg_enterprise_quota_component_version_row_version
      BEFORE UPDATE ON enterprise_quota_component_version
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    CREATE TRIGGER trg_enterprise_quota_rule_version_row_version
      BEFORE UPDATE ON enterprise_quota_rule_version
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS platform_guard_price_version_immutable() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS platform_guard_price_snapshot_immutable() CASCADE")
    op.drop_constraint("fk_enterprise_price_snapshot_line_resource_link", "enterprise_price_snapshot_line", type_="foreignkey")
    op.drop_constraint("fk_enterprise_price_snapshot_line_source_document", "enterprise_price_snapshot_line", type_="foreignkey")
    for column in (
        "mapping_snapshot", "calculation_rule_version", "resource_reference_link_id",
        "source_price_document_id", "price_source", "price_type",
    ):
        op.drop_column("enterprise_price_snapshot_line", column)
    op.alter_column("enterprise_price_snapshot_line", "effective_from", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("enterprise_price_snapshot_line", "price_value", existing_type=sa.Numeric(20, 6), nullable=False)
    op.alter_column("enterprise_price_snapshot_line", "enterprise_price_version_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint("snapshot_type_allowed", "enterprise_price_snapshot", type_="check")
    for column in ("calculation_rule_version", "status", "snapshot_type"):
        op.drop_column("enterprise_price_snapshot", column)
    op.drop_constraint(
        "fk_enterprise_quota_component_version_price_version",
        "enterprise_quota_component_version", type_="foreignkey",
    )
    for column in (
        "amount_source", "enterprise_component_amount", "selected_price_type", "selected_enterprise_price",
        "enterprise_price_version_id", "provincial_component_amount", "provincial_unit_price", "source_consumption",
    ):
        op.drop_column("enterprise_quota_component_version", column)
    op.drop_constraint("source_quota_version_hash_valid", "enterprise_quota_version", type_="check")
    for column in (
        "calculation_rule_version", "change_reason", "enterprise_note", "work_content",
        "unit", "source_quota_version_hash", "source_quota_code", "source_quota_uid",
    ):
        op.drop_column("enterprise_quota_version", column)
    op.drop_constraint("uq_enterprise_quota_change_set_tenant_idempotency", "enterprise_quota_change_set", type_="unique")
    op.drop_constraint("fk_enterprise_quota_change_set_changed_by_app_user", "enterprise_quota_change_set", type_="foreignkey")
    for column in (
        "idempotency_key", "request_id", "changed_at", "changed_by", "change_reason",
        "change_type", "after_value", "before_value",
    ):
        op.drop_column("enterprise_quota_change_set", column)
    op.drop_column("enterprise_quota", "unit")
    op.drop_constraint("confidence_range", "enterprise_price_version", type_="check")
    op.drop_constraint("fk_enterprise_price_version_source_price_document", "enterprise_price_version", type_="foreignkey")
    for column in ("confidence", "supplier_or_source", "project_type", "source_price_document_id"):
        op.drop_column("enterprise_price_version", column)
    op.drop_index("ix_enterprise_resource_reference_link_reference", table_name="enterprise_resource_reference_link")
    op.drop_index("ix_enterprise_resource_reference_link_tenant_id", table_name="enterprise_resource_reference_link")
    op.drop_table("enterprise_resource_reference_link")
    op.drop_column("enterprise_resource", "resource_category")
    op.drop_column("enterprise_resource", "resource_code")
    op.drop_index("ix_enterprise_price_source_document_tenant_id", table_name="enterprise_price_source_document")
    op.drop_table("enterprise_price_source_document")
