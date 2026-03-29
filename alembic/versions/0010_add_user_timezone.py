"""Add timezone preference to users

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _col_exists("users", "timezone"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("timezone", sa.String(100), nullable=True))


def downgrade() -> None:
    if _col_exists("users", "timezone"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("timezone")
