"""Add login/app announcement banner fields to admin_settings

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    with op.batch_alter_table("admin_settings", schema=None) as batch_op:
        if not _col_exists("admin_settings", "login_banner_enabled"):
            batch_op.add_column(sa.Column("login_banner_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        if not _col_exists("admin_settings", "login_banner_message"):
            batch_op.add_column(sa.Column("login_banner_message", sa.String(length=500), nullable=True))
        if not _col_exists("admin_settings", "login_banner_level"):
            batch_op.add_column(sa.Column("login_banner_level", sa.String(length=20), nullable=False, server_default="warning"))
        if not _col_exists("admin_settings", "app_banner_enabled"):
            batch_op.add_column(sa.Column("app_banner_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        if not _col_exists("admin_settings", "app_banner_message"):
            batch_op.add_column(sa.Column("app_banner_message", sa.String(length=500), nullable=True))
        if not _col_exists("admin_settings", "app_banner_level"):
            batch_op.add_column(sa.Column("app_banner_level", sa.String(length=20), nullable=False, server_default="info"))


def downgrade() -> None:
    with op.batch_alter_table("admin_settings", schema=None) as batch_op:
        for col in ("app_banner_level", "app_banner_message", "app_banner_enabled",
                    "login_banner_level", "login_banner_message", "login_banner_enabled"):
            if _col_exists("admin_settings", col):
                batch_op.drop_column(col)
