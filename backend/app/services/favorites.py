from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_favorite import AudioFavorite
from app.models.audio_resource import AudioResource
from app.models.user import User
from app.services.resource_access import get_readable_resource
from app.utils.exceptions import AppError


async def favorite_status(session: AsyncSession, user: User, audio_id: int) -> bool:
    await get_readable_resource(session, audio_id, user)
    return (await session.scalar(
        select(AudioFavorite.id).where(AudioFavorite.user_id == user.id, AudioFavorite.audio_resource_id == audio_id)
    )) is not None


async def add_favorite(session: AsyncSession, user: User, audio_id: int) -> bool:
    await get_readable_resource(session, audio_id, user)
    exists = await session.scalar(
        select(AudioFavorite.id).where(AudioFavorite.user_id == user.id, AudioFavorite.audio_resource_id == audio_id)
    )
    if exists is None:
        session.add(AudioFavorite(user_id=user.id, audio_resource_id=audio_id))
        await session.flush()
    return True


async def remove_favorite(session: AsyncSession, user: User, audio_id: int) -> None:
    favorite = await session.scalar(
        select(AudioFavorite).where(AudioFavorite.user_id == user.id, AudioFavorite.audio_resource_id == audio_id)
    )
    if favorite is None:
        raise AppError(404, "收藏记录不存在")
    await session.delete(favorite)


async def list_favorites(session: AsyncSession, user: User, page: int, page_size: int) -> tuple[list[tuple[AudioFavorite, AudioResource]], int]:
    filters = [AudioFavorite.user_id == user.id]
    total = await session.scalar(select(func.count()).select_from(AudioFavorite).where(*filters))
    rows = await session.execute(
        select(AudioFavorite, AudioResource)
        .join(AudioResource, AudioFavorite.audio_resource_id == AudioResource.id)
        .where(*filters)
        .order_by(AudioFavorite.created_at.desc(), AudioFavorite.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total or 0


async def clear_favorites(session: AsyncSession, user: User) -> int:
    result = await session.execute(delete(AudioFavorite).where(AudioFavorite.user_id == user.id))
    return result.rowcount or 0
