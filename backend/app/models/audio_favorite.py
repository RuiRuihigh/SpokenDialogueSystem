from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AudioFavorite(Base):
    __tablename__ = "audio_favorites"
    __table_args__ = (UniqueConstraint("user_id", "audio_resource_id", name="uq_audio_favorites_user_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    audio_resource_id: Mapped[int] = mapped_column(
        ForeignKey("audio_resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
