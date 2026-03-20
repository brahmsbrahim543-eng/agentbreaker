from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis_pool: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis | None:
    global _redis_pool
    redis_url = get_settings().REDIS_URL
    if not redis_url:
        return None
    _redis_pool = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


async def get_redis() -> AsyncGenerator[aioredis.Redis | None, None]:
    yield _redis_pool


def get_redis_pool() -> aioredis.Redis | None:
    return _redis_pool
