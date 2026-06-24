from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models.user import User
from app.models.user_token import UserToken
from app.utils.exceptions import AppError
from app.utils.security import hash_token


bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise AppError(401, "未提供访问令牌")
    token = await session.scalar(
        select(UserToken).where(
            UserToken.token_hash == hash_token(credentials.credentials),
            UserToken.expires_at > datetime.now(timezone.utc),
        )
    )
    if token is None:
        raise AppError(401, "访问令牌无效或已过期")
    user = await session.get(User, token.user_id)
    if user is None:
        raise AppError(401, "访问令牌无效或已过期")
    if not user.is_active:
        raise AppError(403, "账号已被禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUser) -> User:
    if current_user.role != "admin":
        raise AppError(403, "需要管理员权限")
    return current_user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]
