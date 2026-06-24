from functools import lru_cache

from redis.asyncio import Redis, from_url

from app.config.settings import get_settings


@lru_cache
def get_redis() -> Redis:
    return from_url(get_settings().redis_url, encoding="utf-8", decode_responses=True)


async def close_redis() -> None:
    client = get_redis()
    await client.aclose()
    get_redis.cache_clear()
