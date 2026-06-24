"""Allow upload resources to omit dataset identity.

Revision ID: 0004_upload_dataset_nullable
Revises: 0003_users_tokens_access
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_upload_dataset_nullable"
down_revision: Union[str, Sequence[str], None] = "0003_users_tokens_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("audio_resources", "dataset_name", existing_type=sa.String(length=128), nullable=True)
    op.execute("UPDATE audio_resources SET dataset_name = NULL WHERE source_type = 'upload'")


def downgrade() -> None:
    op.execute("UPDATE audio_resources SET dataset_name = 'upload' WHERE dataset_name IS NULL")
    op.alter_column("audio_resources", "dataset_name", existing_type=sa.String(length=128), nullable=False)
