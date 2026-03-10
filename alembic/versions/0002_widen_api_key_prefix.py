"""Widen api_keys.key_prefix from 16 to 32 characters

The stored prefix format is "tribal_sk_XXXX..." (17 chars) which exceeded
the original VARCHAR(16) on MySQL.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "api_keys",
        "key_prefix",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "api_keys",
        "key_prefix",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )
