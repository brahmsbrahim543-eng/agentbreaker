from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis_pool: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    global _redis_pool
    _redis_pool = aioredis.from_url(
        get_settings().REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    yield _redis_pool


def get_redis_pool() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized.")
    return _redis_pool
