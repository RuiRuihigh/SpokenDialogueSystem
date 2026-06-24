from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AudioResource(Base):
    """One protected, playable source audio file and its imported metadata."""

    __tablename__ = "audio_resources"
    __table_args__ = (
        UniqueConstraint("dataset_name", "storage_key", name="uq_audio_resources_dataset_storage_key"),
        Index("ix_audio_resources_dataset_split_created", "dataset_name", "dataset_split", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metainfo: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="dataset")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="authenticated")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    dataset_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_split: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="audio/wav")
    audio_format: Mapped[str] = mapped_column(String(32), nullable=False, default="wav")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
