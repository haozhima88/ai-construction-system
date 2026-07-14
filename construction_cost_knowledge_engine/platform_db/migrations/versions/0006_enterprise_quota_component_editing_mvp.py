"""Add component calculation basis and governed Draft editing.

Revision ID: 0006_component_editing_mvp
Revises: 0005_price_fallback_a111
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_component_editing_mvp"
down_revision: str | None = "0005_price_fallback_a111"
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
    op.add_column("enterprise_quota_component_version", sa.Column("source_enterprise_resource_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("calculation_basis", sa.String(32), server_default="quantity_unit_price", nullable=False))
    op.add_column("enterprise_quota_component_version", sa.Column("source_direct_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("enterprise_direct_amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("calculation_base", sa.Numeric(20, 6), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("enterprise_rate", sa.Numeric(20, 8), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("formula_code", sa.String(128), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("formula_version", sa.String(64), nullable=True))
    op.add_column("enterprise_quota_component_version", sa.Column("component_status", sa.String(32), server_default="inherited", nullable=False))
    op.add_column("enterprise_quota_component_version", sa.Column("lifecycle_status", sa.String(32), server_default="active", nullable=False))
    op.add_column("enterprise_quota_component_version", sa.Column("specification_override", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_enterprise_quota_component_source_enterprise_resource"),
        "enterprise_quota_component_version", "enterprise_resource",
        ["source_enterprise_resource_id"], ["enterprise_resource_id"], ondelete="RESTRICT",
    )
    op.execute("UPDATE enterprise_quota_component_version SET source_enterprise_resource_id = enterprise_resource_id")
    op.alter_column("enterprise_quota_component_version", "consumption", existing_type=sa.Numeric(20, 8), nullable=True)
    op.alter_column("enterprise_quota_component_version", "source_consumption", existing_type=sa.Numeric(20, 8), nullable=True)
    op.drop_constraint(
        op.f("ck_enterprise_quota_component_version_consumption_nonnegative"),
        "enterprise_quota_component_version", type_="check",
    )
    op.create_check_constraint(
        "consumption_nonnegative",
        "enterprise_quota_component_version", "consumption IS NULL OR consumption >= 0",
    )
    op.create_check_constraint(
        "calculation_basis_allowed",
        "enterprise_quota_component_version",
        "calculation_basis IN ('quantity_unit_price', 'direct_amount', 'rate_based', 'formula_based')",
    )
    op.create_check_constraint(
        "component_status_allowed",
        "enterprise_quota_component_version",
        "component_status IN ('inherited', 'quantity_modified', 'amount_modified', 'resource_added', "
        "'resource_replaced', 'resource_removed', 'restored')",
    )
    op.create_check_constraint(
        "lifecycle_status_allowed",
        "enterprise_quota_component_version", "lifecycle_status IN ('active', 'removed')",
    )
    op.create_check_constraint(
        "direct_amount_nonnegative",
        "enterprise_quota_component_version", "enterprise_direct_amount IS NULL OR enterprise_direct_amount >= 0",
    )
    op.create_check_constraint(
        "enterprise_rate_nonnegative",
        "enterprise_quota_component_version", "enterprise_rate IS NULL OR enterprise_rate >= 0",
    )
    for column in ("calculation_basis", "component_status", "lifecycle_status"):
        op.alter_column("enterprise_quota_component_version", column, server_default=None)

    op.create_table(
        "enterprise_component_calculation_profile",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reference_resource_id", sa.Uuid(), nullable=False),
        sa.Column("resource_code", sa.String(128), nullable=True),
        sa.Column("resource_name", sa.String(512), nullable=False),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("calculation_basis", sa.String(32), nullable=False),
        sa.Column("classification_reason", sa.Text(), nullable=False),
        sa.Column("source_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("review_status", sa.String(64), nullable=False),
        *audit_columns(),
        sa.CheckConstraint(
            "calculation_basis IN ('quantity_unit_price', 'direct_amount', 'rate_based', 'formula_based')",
            name="calculation_basis_allowed",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["app_tenant.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reference_resource_id"], ["reference_quota_resource.reference_quota_resource_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("profile_id"),
        sa.UniqueConstraint("tenant_id", "reference_resource_id", name="uq_component_calculation_profile_tenant_reference"),
    )
    op.create_index("ix_enterprise_component_calculation_profile_tenant_id", "enterprise_component_calculation_profile", ["tenant_id"])
    op.create_index("ix_enterprise_component_calculation_profile_basis", "enterprise_component_calculation_profile", ["calculation_basis"])

    op.create_table(
        "enterprise_quota_component_change",
        sa.Column("component_change_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("quota_version_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("before_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("review_status", sa.String(64), nullable=False),
        *audit_columns(),
        sa.CheckConstraint(
            "change_type IN ('quantity_modified', 'amount_modified', 'resource_added', 'resource_replaced', "
            "'resource_removed', 'restored', 'specification_modified')",
            name="change_type_allowed",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["app_tenant.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["quota_version_id"], ["enterprise_quota_version.enterprise_quota_version_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["component_id"], ["enterprise_quota_component_version.enterprise_quota_component_version_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["change_set_id"], ["enterprise_quota_change_set.enterprise_quota_change_set_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["changed_by"], ["app_user.app_user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("component_change_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", "field_name", name="uq_component_change_tenant_idempotency_field"),
    )
    op.create_index("ix_enterprise_quota_component_change_tenant_id", "enterprise_quota_component_change", ["tenant_id"])
    op.create_index("ix_enterprise_quota_component_change_version", "enterprise_quota_component_change", ["quota_version_id", "changed_at"])

    op.execute("""
    CREATE TRIGGER trg_enterprise_component_calculation_profile_row_version
      BEFORE UPDATE ON enterprise_component_calculation_profile
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    CREATE TRIGGER trg_enterprise_quota_component_change_row_version
      BEFORE UPDATE ON enterprise_quota_component_change
      FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version();
    """)


def downgrade() -> None:
    op.drop_index("ix_enterprise_quota_component_change_version", table_name="enterprise_quota_component_change")
    op.drop_index("ix_enterprise_quota_component_change_tenant_id", table_name="enterprise_quota_component_change")
    op.drop_table("enterprise_quota_component_change")
    op.drop_index("ix_enterprise_component_calculation_profile_basis", table_name="enterprise_component_calculation_profile")
    op.drop_index("ix_enterprise_component_calculation_profile_tenant_id", table_name="enterprise_component_calculation_profile")
    op.drop_table("enterprise_component_calculation_profile")
    for name in (
        "enterprise_rate_nonnegative",
        "direct_amount_nonnegative",
        "lifecycle_status_allowed",
        "component_status_allowed",
        "calculation_basis_allowed",
        "consumption_nonnegative",
    ):
        op.drop_constraint(name, "enterprise_quota_component_version", type_="check")
    op.create_check_constraint(
        "consumption_nonnegative",
        "enterprise_quota_component_version", "consumption >= 0",
    )
    op.alter_column("enterprise_quota_component_version", "source_consumption", existing_type=sa.Numeric(20, 8), nullable=False)
    op.alter_column("enterprise_quota_component_version", "consumption", existing_type=sa.Numeric(20, 8), nullable=False)
    op.drop_constraint(op.f("fk_enterprise_quota_component_source_enterprise_resource"), "enterprise_quota_component_version", type_="foreignkey")
    for column in (
        "specification_override", "lifecycle_status", "component_status", "formula_version", "formula_code",
        "enterprise_rate", "calculation_base", "enterprise_direct_amount", "source_direct_amount",
        "calculation_basis", "source_enterprise_resource_id",
    ):
        op.drop_column("enterprise_quota_component_version", column)
