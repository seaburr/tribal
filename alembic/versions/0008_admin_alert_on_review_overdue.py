"""Add alert_on_review_overdue to admin_settings

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _col_exists("admin_settings", "alert_on_review_overdue"):
        with op.batch_alter_table("admin_settings", schema=None) as batch_op:
            batch_op.add_column(sa.Column("alert_on_review_overdue", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    if _col_exists("admin_settings", "alert_on_review_overdue"):
        with op.batch_alter_table("admin_settings", schema=None) as batch_op:
            batch_op.drop_column("alert_on_review_overdue")
