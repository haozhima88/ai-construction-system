"""Add local authentication, server sessions, tenant RBAC, and security audit.

Revision ID: 0002_authentication_session_rbac
Revises: 0001_platform_core_schema
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_authentication_session_rbac"
down_revision: str | None = "0001_platform_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
    ]


def tenant_fk(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["app_tenant.tenant_id"],
        name=f"fk_{table_name}_tenant_id_app_tenant", ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.add_column("app_user", sa.Column("login_name_normalized", sa.String(length=128), nullable=True))
    op.add_column("app_user", sa.Column("password_hash", sa.String(length=512), nullable=True))
    op.add_column("app_user", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_user", sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("app_user", sa.Column("is_service_account", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("app_user", sa.Column("lockout_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_user", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_user", sa.Column("auth_version", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.execute("UPDATE app_user SET login_name_normalized = lower(btrim(login_name))")
    op.execute("UPDATE app_user SET is_service_account = true WHERE login_name = 'platform-system-import'")
    op.alter_column("app_user", "login_name_normalized", nullable=False)
    op.create_unique_constraint("uq_app_user_tenant_login_normalized", "app_user", ["tenant_id", "login_name_normalized"])
    op.create_unique_constraint("uq_app_user_id_tenant", "app_user", ["app_user_id", "tenant_id"])
    op.create_check_constraint("ck_app_user_auth_version_positive", "app_user", "auth_version > 0")
    op.create_check_constraint(
        "ck_app_user_password_required_for_local_user", "app_user",
        "is_service_account OR password_hash IS NOT NULL",
    )
    op.create_foreign_key(
        "fk_role_assignment_user_tenant", "app_user_role_assignment", "app_user",
        ["app_user_id", "tenant_id"], ["app_user_id", "tenant_id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_role_assignment_assigner_tenant", "app_user_role_assignment", "app_user",
        ["assigned_by", "tenant_id"], ["app_user_id", "tenant_id"], ondelete="RESTRICT",
    )

    op.create_table(
        "app_permission",
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("permission_code", sa.String(length=128), nullable=False),
        sa.Column("permission_name", sa.String(length=255), nullable=False),
        sa.Column("resource_group", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("permission_id", name="pk_app_permission"),
        sa.UniqueConstraint("permission_code", name="uq_app_permission_permission_code"),
        sa.CheckConstraint("row_version > 0", name="ck_app_permission_row_version_positive"),
    )

    op.create_table(
        "app_session",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("app_user_id", sa.Uuid(), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        *audit_columns(),
        tenant_fk("app_session"),
        sa.ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_app_session_user_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["revoked_by"], ["app_user.app_user_id"], name="fk_app_session_revoked_by_app_user", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("session_id", name="pk_app_session"),
        sa.UniqueConstraint("session_token_hash", name="uq_app_session_token_hash"),
        sa.CheckConstraint("length(session_token_hash) = 64", name="ck_app_session_session_token_hash_valid"),
        sa.CheckConstraint("length(csrf_token_hash) = 64", name="ck_app_session_csrf_token_hash_valid"),
        sa.CheckConstraint("expires_at <= absolute_expires_at", name="ck_app_session_session_expiry_valid"),
        sa.CheckConstraint("status IN ('active','revoked','expired')", name="ck_app_session_session_status_valid"),
        sa.CheckConstraint("row_version > 0", name="ck_app_session_row_version_positive"),
    )
    op.create_index("ix_app_session_tenant_id", "app_session", ["tenant_id"])
    op.create_index("ix_app_session_active_user", "app_session", ["tenant_id", "app_user_id", "status", "expires_at"])

    op.create_table(
        "app_login_attempt",
        sa.Column("login_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("username_normalized", sa.String(length=128), nullable=False),
        sa.Column("app_user_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
        *audit_columns(),
        tenant_fk("app_login_attempt"),
        sa.ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_login_attempt_user_tenant", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("login_attempt_id", name="pk_app_login_attempt"),
        sa.CheckConstraint("row_version > 0", name="ck_app_login_attempt_row_version_positive"),
    )
    op.create_index("ix_app_login_attempt_tenant_id", "app_login_attempt", ["tenant_id"])
    op.create_index("ix_login_attempt_username_window", "app_login_attempt", ["tenant_id", "username_normalized", "attempt_at"])
    op.create_index("ix_login_attempt_ip_window", "app_login_attempt", ["tenant_id", "client_ip", "attempt_at"])

    op.create_table(
        "app_password_history",
        sa.Column("password_history_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("app_user_id", sa.Uuid(), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        *audit_columns(),
        tenant_fk("app_password_history"),
        sa.ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_password_history_user_tenant", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("password_history_id", name="pk_app_password_history"),
        sa.CheckConstraint("length(password_hash) >= 80", name="ck_app_password_history_password_hash_format"),
        sa.CheckConstraint("row_version > 0", name="ck_app_password_history_row_version_positive"),
    )
    op.create_index("ix_app_password_history_tenant_id", "app_password_history", ["tenant_id"])
    op.create_index("ix_password_history_user_created", "app_password_history", ["tenant_id", "app_user_id", "created_at"])

    op.create_table(
        "app_role_permission",
        sa.Column("role_permission_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("app_role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *audit_columns(),
        tenant_fk("app_role_permission"),
        sa.ForeignKeyConstraint(["app_role_id"], ["app_role.app_role_id"], name="fk_app_role_permission_app_role_id_app_role", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["permission_id"], ["app_permission.permission_id"], name="fk_app_role_permission_permission_id_app_permission", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["granted_by", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_role_permission_granter_tenant", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("role_permission_id", name="pk_app_role_permission"),
        sa.UniqueConstraint("tenant_id", "app_role_id", "permission_id", name="uq_role_permission_tenant_role_permission"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_app_role_permission_role_permission_status_valid"),
        sa.CheckConstraint("row_version > 0", name="ck_app_role_permission_row_version_positive"),
    )
    op.create_index("ix_app_role_permission_tenant_id", "app_role_permission", ["tenant_id"])
    op.create_index("ix_role_permission_active", "app_role_permission", ["tenant_id", "app_role_id", "status"])

    op.create_table(
        "app_security_event",
        sa.Column("security_event_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("app_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("object_type", sa.String(length=128), nullable=False),
        sa.Column("object_id", sa.String(length=255), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        *audit_columns(),
        tenant_fk("app_security_event"),
        sa.ForeignKeyConstraint(
            ["app_user_id", "tenant_id"], ["app_user.app_user_id", "app_user.tenant_id"],
            name="fk_security_event_user_tenant", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("security_event_id", name="pk_app_security_event"),
        sa.CheckConstraint("result IN ('success','failure','denied','override')", name="ck_app_security_event_security_event_result_valid"),
        sa.CheckConstraint("row_version > 0", name="ck_app_security_event_row_version_positive"),
    )
    op.create_index("ix_app_security_event_tenant_id", "app_security_event", ["tenant_id"])
    op.create_index("ix_security_event_tenant_created", "app_security_event", ["tenant_id", "created_at"])
    op.create_index("ix_security_event_action_created", "app_security_event", ["action", "created_at"])

    for table in ("app_session", "app_permission", "app_role_permission"):
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}_row_version BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION platform_bump_row_version()"
        ))
    op.execute("""
    CREATE OR REPLACE FUNCTION platform_guard_security_append_only() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'security history is append-only' USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql;
    """)
    for table in ("app_login_attempt", "app_password_history", "app_security_event"):
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION platform_guard_security_append_only()"
        ))


def downgrade() -> None:
    # Destructive for authentication/security history. Export audit evidence before any authorized downgrade.
    for table in ("app_login_attempt", "app_password_history", "app_security_event"):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}"))
    op.execute("DROP FUNCTION IF EXISTS platform_guard_security_append_only()")
    for table in ("app_session", "app_permission", "app_role_permission"):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_row_version ON {table}"))

    op.drop_index("ix_security_event_action_created", table_name="app_security_event")
    op.drop_index("ix_security_event_tenant_created", table_name="app_security_event")
    op.drop_index("ix_app_security_event_tenant_id", table_name="app_security_event")
    op.drop_table("app_security_event")
    op.drop_index("ix_role_permission_active", table_name="app_role_permission")
    op.drop_index("ix_app_role_permission_tenant_id", table_name="app_role_permission")
    op.drop_table("app_role_permission")
    op.drop_index("ix_password_history_user_created", table_name="app_password_history")
    op.drop_index("ix_app_password_history_tenant_id", table_name="app_password_history")
    op.drop_table("app_password_history")
    op.drop_index("ix_login_attempt_ip_window", table_name="app_login_attempt")
    op.drop_index("ix_login_attempt_username_window", table_name="app_login_attempt")
    op.drop_index("ix_app_login_attempt_tenant_id", table_name="app_login_attempt")
    op.drop_table("app_login_attempt")
    op.drop_index("ix_app_session_active_user", table_name="app_session")
    op.drop_index("ix_app_session_tenant_id", table_name="app_session")
    op.drop_table("app_session")
    op.drop_table("app_permission")

    op.drop_constraint("fk_role_assignment_assigner_tenant", "app_user_role_assignment", type_="foreignkey")
    op.drop_constraint("fk_role_assignment_user_tenant", "app_user_role_assignment", type_="foreignkey")
    op.drop_constraint("ck_app_user_password_required_for_local_user", "app_user", type_="check")
    op.drop_constraint("ck_app_user_auth_version_positive", "app_user", type_="check")
    op.drop_constraint("uq_app_user_id_tenant", "app_user", type_="unique")
    op.drop_constraint("uq_app_user_tenant_login_normalized", "app_user", type_="unique")
    for column in (
        "auth_version", "last_login_at", "lockout_until", "is_service_account",
        "must_change_password", "password_changed_at", "password_hash", "login_name_normalized",
    ):
        op.drop_column("app_user", column)
