"""Create durable automatic transcription tasks.

Revision ID: 0007_transcription_tasks
Revises: 0006_audio_favorites
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_transcription_tasks"
down_revision: Union[str, Sequence[str], None] = "0006_audio_favorites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcription_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audio_resource_id", sa.Integer(), sa.ForeignKey("audio_resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="openai"),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("segments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_transcription_tasks_audio_resource_id", "transcription_tasks", ["audio_resource_id"])
    op.create_index("ix_transcription_tasks_owner_id", "transcription_tasks", ["owner_id"])
    op.create_index("ix_transcription_tasks_owner_created", "transcription_tasks", ["owner_id", "created_at"])
    op.create_index("ix_transcription_tasks_resource_created", "transcription_tasks", ["audio_resource_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_transcription_tasks_resource_created", table_name="transcription_tasks")
    op.drop_index("ix_transcription_tasks_owner_created", table_name="transcription_tasks")
    op.drop_index("ix_transcription_tasks_owner_id", table_name="transcription_tasks")
    op.drop_index("ix_transcription_tasks_audio_resource_id", table_name="transcription_tasks")
    op.drop_table("transcription_tasks")
