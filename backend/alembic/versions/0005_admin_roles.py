"""Add administrator roles and user activation state.

Revision ID: 0005_admin_roles
Revises: 0004_upload_dataset_nullable
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_admin_roles"
down_revision: Union[str, Sequence[str], None] = "0004_upload_dataset_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=16), nullable=False, server_default="user"))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("users", "role", server_default=None)
    op.alter_column("users", "is_active", server_default=None)
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
