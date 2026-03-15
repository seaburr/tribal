"""Add certificate_url and auto_refresh_expiry to resources

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resources",
        sa.Column("certificate_url", sa.String(1000), nullable=True),
    )
    op.add_column(
        "resources",
        sa.Column("auto_refresh_expiry", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("resources", "auto_refresh_expiry")
    op.drop_column("resources", "certificate_url")
