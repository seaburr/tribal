"""Add provider column to resources for auto-detected key type

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _col_exists("resources", "provider"):
        with op.batch_alter_table("resources", schema=None) as batch_op:
            batch_op.add_column(sa.Column("provider", sa.String(100), nullable=True))


def downgrade() -> None:
    if _col_exists("resources", "provider"):
        with op.batch_alter_table("resources", schema=None) as batch_op:
            batch_op.drop_column("provider")
