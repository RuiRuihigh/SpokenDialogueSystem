"""Create audio favorites.

Revision ID: 0006_audio_favorites
Revises: 0005_admin_roles
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_audio_favorites"
down_revision: Union[str, Sequence[str], None] = "0005_admin_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "audio_resource_id", sa.Integer(), sa.ForeignKey("audio_resources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "audio_resource_id", name="uq_audio_favorites_user_resource"),
    )
    op.create_index("ix_audio_favorites_user_id", "audio_favorites", ["user_id"])
    op.create_index("ix_audio_favorites_audio_resource_id", "audio_favorites", ["audio_resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audio_favorites_audio_resource_id", table_name="audio_favorites")
    op.drop_index("ix_audio_favorites_user_id", table_name="audio_favorites")
    op.drop_table("audio_favorites")
