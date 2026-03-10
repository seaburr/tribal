"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_teams_id"), "teams", ["id"], unique=False)

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

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False)

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
        sa.Column("type", sa.String(50), nullable=False, server_default="Other"),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("public_key_pem", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resources_id"), "resources", ["id"], unique=False)

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


def downgrade() -> None:
    op.drop_table("reminder_logs")
    op.drop_table("resources")
    op.drop_table("api_keys")
    op.drop_table("audit_logs")
    op.drop_table("admin_settings")
    op.drop_table("users")
    op.drop_table("teams")
