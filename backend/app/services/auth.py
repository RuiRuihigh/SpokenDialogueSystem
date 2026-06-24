from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.user import User
from app.models.user_token import UserToken
from app.utils.exceptions import AppError
from app.utils.security import create_raw_token, hash_password, hash_token, verify_password


async def register_user(session: AsyncSession, username: str, password: str) -> tuple[User, str]:
    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(400, "用户名已存在") from exc
    token = await _issue_token(session, user)
    await session.commit()
    return user, token


async def login_user(session: AsyncSession, username: str, password: str) -> tuple[User, str]:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(401, "用户名或密码错误")
    if not user.is_active:
        raise AppError(403, "账号已被禁用")
    token = await _issue_token(session, user)
    await session.commit()
    return user, token


async def _issue_token(session: AsyncSession, user: User) -> str:
    raw_token = create_raw_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=get_settings().access_token_expire_minutes)
    session.add(UserToken(user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at))
    return raw_token


def user_payload(user: User) -> dict[str, object | None]:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "bio": user.bio,
        "role": user.role,
    }
