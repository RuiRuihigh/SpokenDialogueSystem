from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_resource import AudioResource
from app.models.user import User
from app.utils.exceptions import AppError


async def get_readable_resource(session: AsyncSession, resource_id: int, current_user: User) -> AudioResource:
    resource = await session.get(AudioResource, resource_id)
    if resource is None:
        raise AppError(404, "资源不存在")
    if resource.source_type == "dataset" and resource.visibility == "authenticated":
        return resource
    if resource.visibility == "private" and resource.owner_id == current_user.id:
        return resource
    # Do not disclose the protected resource's metadata or storage key.
    raise AppError(403, "无权访问该资源")


async def list_readable_resources(
    session: AsyncSession,
    current_user: User,
    *,
    scope: str,
    dataset_name: str,
    dataset_split: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AudioResource], int, list[str]]:
    if scope == "dataset":
        filters = [
            AudioResource.source_type == "dataset",
            AudioResource.visibility == "authenticated",
            AudioResource.dataset_name == dataset_name,
        ]
        available_splits = list(
            (await session.scalars(
                select(AudioResource.dataset_split)
                .where(*filters)
                .distinct()
                .order_by(AudioResource.dataset_split)
            )).all()
        )
        if dataset_split:
            filters.append(AudioResource.dataset_split == dataset_split)
    elif scope == "mine":
        filters = [
            AudioResource.source_type == "upload",
            AudioResource.visibility == "private",
            AudioResource.owner_id == current_user.id,
        ]
        available_splits = []
    else:
        raise AppError(400, "scope 必须为 dataset 或 mine")

    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        filters.append(or_(AudioResource.name.ilike(pattern), AudioResource.text.ilike(pattern)))

    total = await session.scalar(select(func.count()).select_from(AudioResource).where(*filters))
    records = await session.scalars(
        select(AudioResource)
        .where(*filters)
        .order_by(AudioResource.created_at.desc(), AudioResource.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(records), total or 0, available_splits
