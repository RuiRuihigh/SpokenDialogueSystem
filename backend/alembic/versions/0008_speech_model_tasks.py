"""Create SpeechLLM inference tasks.

Revision ID: 0008_speech_model_tasks
Revises: 0007_transcription_tasks
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0008_speech_model_tasks"
down_revision: Union[str, Sequence[str], None] = "0007_transcription_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "speech_model_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audio_resource_id", sa.Integer(), sa.ForeignKey("audio_resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="huggingface"),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_speech_model_tasks_audio_resource_id", "speech_model_tasks", ["audio_resource_id"])
    op.create_index("ix_speech_model_tasks_owner_id", "speech_model_tasks", ["owner_id"])
    op.create_index("ix_speech_model_tasks_owner_created", "speech_model_tasks", ["owner_id", "created_at"])
    op.create_index("ix_speech_model_tasks_resource_created", "speech_model_tasks", ["audio_resource_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_speech_model_tasks_resource_created", table_name="speech_model_tasks")
    op.drop_index("ix_speech_model_tasks_owner_created", table_name="speech_model_tasks")
    op.drop_index("ix_speech_model_tasks_owner_id", table_name="speech_model_tasks")
    op.drop_index("ix_speech_model_tasks_audio_resource_id", table_name="speech_model_tasks")
    op.drop_table("speech_model_tasks")
