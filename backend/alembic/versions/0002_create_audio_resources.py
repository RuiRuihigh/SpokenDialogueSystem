"""Create imported dataset audio-resource metadata.

Revision ID: 0002_create_audio_resources
Revises: 0001_initialize_schema_version
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_create_audio_resources"
down_revision: Union[str, Sequence[str], None] = "0001_initialize_schema_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metainfo", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="dataset"),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("dataset_split", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False, server_default="audio/wav"),
        sa.Column("audio_format", sa.String(length=32), nullable=False, server_default="wav"),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("dataset_name", "storage_key", name="uq_audio_resources_dataset_storage_key"),
    )
    op.create_index(
        "ix_audio_resources_dataset_split_created",
        "audio_resources",
        ["dataset_name", "dataset_split", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audio_resources_dataset_split_created", table_name="audio_resources")
    op.drop_table("audio_resources")
