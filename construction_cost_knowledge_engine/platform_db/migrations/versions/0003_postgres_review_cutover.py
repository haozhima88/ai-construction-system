"""Add explicit non-approved mapping review states used by the PostgreSQL Web overlay.

Revision ID: 0003_postgres_review_cutover
Revises: 0002_authentication_session_rbac
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0003_postgres_review_cutover"
down_revision: str | None = "0002_authentication_session_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE no_approved_review_status ADD VALUE IF NOT EXISTS 'reviewed_candidate'")
    op.execute("ALTER TYPE no_approved_review_status ADD VALUE IF NOT EXISTS 'reviewed_mismatch'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while preserving existing rows.
    # A downgrade requires an explicit data review and enum rebuild outside this migration.
    pass
