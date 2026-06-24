"""Add users, persistent bearer tokens, and resource ownership.

Revision ID: 0003_users_tokens_access
Revises: 0002_create_audio_resources
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_users_tokens_access"
down_revision: Union[str, Sequence[str], None] = "0002_create_audio_resources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=128), nullable=True),
        sa.Column("avatar", sa.String(length=1024), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("token_hash", name="uq_user_tokens_token_hash"),
    )
    op.create_index("ix_user_tokens_token_hash_expires_at", "user_tokens", ["token_hash", "expires_at"])
    op.add_column(
        "audio_resources",
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="authenticated"),
    )
    op.add_column("audio_resources", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_index("ix_audio_resources_owner_id", "audio_resources", ["owner_id"])
    op.create_foreign_key("fk_audio_resources_owner_id_users", "audio_resources", "users", ["owner_id"], ["id"], ondelete="SET NULL")
    op.alter_column("audio_resources", "visibility", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_audio_resources_owner_id_users", "audio_resources", type_="foreignkey")
    op.drop_index("ix_audio_resources_owner_id", table_name="audio_resources")
    op.drop_column("audio_resources", "owner_id")
    op.drop_column("audio_resources", "visibility")
    op.drop_index("ix_user_tokens_token_hash_expires_at", table_name="user_tokens")
    op.drop_table("user_tokens")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
