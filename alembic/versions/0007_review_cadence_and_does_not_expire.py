"""Add review cadence, does_not_expire, last_reviewed_at, and reminder_type

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── resources table ──────────────────────────────────────────────────────
    res_cols = [c["name"] for c in inspector.get_columns("resources")]

    if "does_not_expire" not in res_cols:
        op.add_column(
            "resources",
            sa.Column("does_not_expire", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "last_reviewed_at" not in res_cols:
        op.add_column(
            "resources",
            sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        )

    # Make expiration_date nullable (requires batch mode on SQLite)
    with op.batch_alter_table("resources") as batch_op:
        batch_op.alter_column(
            "expiration_date",
            existing_type=sa.Date(),
            nullable=True,
        )

    # ── admin_settings table ─────────────────────────────────────────────────
    adm_cols = [c["name"] for c in inspector.get_columns("admin_settings")]

    if "review_cadence_months" not in adm_cols:
        op.add_column(
            "admin_settings",
            sa.Column("review_cadence_months", sa.Integer(), nullable=True),
        )

    # ── reminder_logs table ──────────────────────────────────────────────────
    rem_cols = [c["name"] for c in inspector.get_columns("reminder_logs")]

    if "reminder_type" not in rem_cols:
        op.add_column(
            "reminder_logs",
            sa.Column("reminder_type", sa.String(20), nullable=False, server_default="expiry"),
        )


def downgrade() -> None:
    op.drop_column("reminder_logs", "reminder_type")
    op.drop_column("admin_settings", "review_cadence_months")

    with op.batch_alter_table("resources") as batch_op:
        batch_op.alter_column(
            "expiration_date",
            existing_type=sa.Date(),
            nullable=False,
        )

    op.drop_column("resources", "last_reviewed_at")
    op.drop_column("resources", "does_not_expire")
