"""Repair schema for MySQL instances where alembic_version was stamped but tables were not created

If the database had its tables dropped while alembic_version remained (e.g. a managed MySQL
instance was recreated), this migration recreates any missing tables and columns so that
subsequent migrations have a consistent baseline to build on.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 0001: base tables ────────────────────────────────────────────────────
    if not _table_exists(inspector, "teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index(op.f("ix_teams_id"), "teams", ["id"], unique=False)

    if not _table_exists(inspector, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=True),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False),
            sa.Column("is_account_creator", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
        op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    if not _table_exists(inspector, "admin_settings"):
        op.create_table(
            "admin_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_name", sa.String(255), nullable=True),
            sa.Column("reminder_days", sa.JSON(), nullable=False),
            sa.Column("notify_hour", sa.Integer(), nullable=False),
            sa.Column("slack_webhook", sa.String(500), nullable=True),
            sa.Column("alert_on_overdue", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists(inspector, "audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_email", sa.String(255), nullable=True),
            sa.Column("resource_id", sa.Integer(), nullable=True),
            sa.Column("resource_name", sa.String(255), nullable=True),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)

    if not _table_exists(inspector, "api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("key_prefix", sa.String(32), nullable=False),  # already at 0002 width
            sa.Column("key_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key_hash"),
        )
        op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False)

    if not _table_exists(inspector, "resources"):
        op.create_table(
            "resources",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("dri", sa.String(255), nullable=False),
            sa.Column("expiration_date", sa.Date(), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=False),
            sa.Column("generation_instructions", sa.Text(), nullable=False),
            sa.Column("secret_manager_link", sa.String(1000), nullable=True),
            sa.Column("slack_webhook", sa.String(500), nullable=False),
            sa.Column("type", sa.String(50), nullable=False, server_default=sa.text("'Other'")),
            sa.Column("team_id", sa.Integer(), nullable=True),
            sa.Column("public_key_pem", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            # 0004 columns included here so fresh tables are fully up-to-date
            sa.Column("certificate_url", sa.String(1000), nullable=True),
            sa.Column("auto_refresh_expiry", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_resources_id"), "resources", ["id"], unique=False)

    if not _table_exists(inspector, "reminder_logs"):
        op.create_table(
            "reminder_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("expiration_date", sa.Date(), nullable=False),
            sa.Column("days_before", sa.Integer(), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_reminder_logs_id"), "reminder_logs", ["id"], unique=False)

    # ── 0002: widen api_keys.key_prefix ──────────────────────────────────────
    # Only needed on databases that already had api_keys from 0001 (narrow column).
    if _table_exists(inspector, "api_keys"):
        col = next(
            (c for c in inspector.get_columns("api_keys") if c["name"] == "key_prefix"), None
        )
        if col is not None and col["type"].length < 32:
            op.alter_column(
                "api_keys", "key_prefix",
                existing_type=sa.String(col["type"].length),
                type_=sa.String(32),
                existing_nullable=False,
            )

    # ── 0003: admin_settings.alert_on_delete ─────────────────────────────────
    if _table_exists(inspector, "admin_settings") and not _column_exists(
        inspector, "admin_settings", "alert_on_delete"
    ):
        op.add_column(
            "admin_settings",
            sa.Column("alert_on_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # ── 0004: resources.certificate_url / auto_refresh_expiry ────────────────
    if _table_exists(inspector, "resources"):
        if not _column_exists(inspector, "resources", "certificate_url"):
            op.add_column(
                "resources",
                sa.Column("certificate_url", sa.String(1000), nullable=True),
            )
        if not _column_exists(inspector, "resources", "auto_refresh_expiry"):
            op.add_column(
                "resources",
                sa.Column("auto_refresh_expiry", sa.Boolean(), nullable=False, server_default=sa.false()),
            )


def downgrade() -> None:
    # Downgrade is intentionally a no-op: this migration only adds missing structure
    # and cannot know which tables/columns were originally absent vs present.
    pass
