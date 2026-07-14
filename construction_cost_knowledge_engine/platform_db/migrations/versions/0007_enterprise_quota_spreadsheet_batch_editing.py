"""Allow one idempotent batch to change the same field on multiple components.

Revision ID: 0007_quota_spreadsheet_batch
Revises: 0006_component_editing_mvp
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0007_quota_spreadsheet_batch"
down_revision: str | None = "0006_component_editing_mvp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_component_change_tenant_idempotency_field",
        "enterprise_quota_component_change",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_component_change_tenant_idempotency_component_field",
        "enterprise_quota_component_change",
        ["tenant_id", "idempotency_key", "component_id", "field_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_component_change_tenant_idempotency_component_field",
        "enterprise_quota_component_change",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_component_change_tenant_idempotency_field",
        "enterprise_quota_component_change",
        ["tenant_id", "idempotency_key", "field_name"],
    )
