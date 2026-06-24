from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_resource import AudioResource
from app.models.user import User
from app.utils.exceptions import AppError


async def list_users(session: AsyncSession, page: int, page_size: int) -> tuple[list[User], int]:
    total = await session.scalar(select(func.count()).select_from(User))
    users = await session.scalars(
        select(User).order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(users), total or 0


async def set_user_active(session: AsyncSession, *, target_id: int, is_active: bool, actor: User) -> User:
    target = await session.get(User, target_id)
    if target is None:
        raise AppError(404, "用户不存在")
    if target.id == actor.id and not is_active:
        raise AppError(400, "管理员不能禁用自己的账号")
    target.is_active = is_active
    await session.flush()
    return target


async def dataset_statistics(session: AsyncSession, dataset_name: str) -> dict[str, object]:
    total = await session.scalar(
        select(func.count()).select_from(AudioResource).where(
            AudioResource.source_type == "dataset", AudioResource.dataset_name == dataset_name
        )
    )
    split_rows = await session.execute(
        select(AudioResource.dataset_split, func.count())
        .where(AudioResource.source_type == "dataset", AudioResource.dataset_name == dataset_name)
        .group_by(AudioResource.dataset_split)
        .order_by(AudioResource.dataset_split)
    )
    return {
        "name": dataset_name,
        "audioCount": total or 0,
        "splits": {split: count for split, count in split_rows},
    }
