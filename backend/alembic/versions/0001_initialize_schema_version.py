"""Initialize Alembic migration tracking.

Revision ID: 0001_initialize_schema_version
Revises:
Create Date: 2026-06-23
"""

from typing import Sequence, Union


revision: str = "0001_initialize_schema_version"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Domain tables are introduced in dedicated, reviewable migrations.
    pass


def downgrade() -> None:
    pass
