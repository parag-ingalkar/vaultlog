"""Redis fixtures for integration and security tests."""

from __future__ import annotations

import pytest_asyncio
import redis.asyncio as redis

from vaultlog.infrastructure.security.rate_limit import RedisRateLimiter
from vaultlog.shared.config import get_settings


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def redis_client():
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=False)
    try:
        await client.ping()
    except Exception as exc:
        msg = (
            "Redis is required for tests. Start compose redis "
            f"or set REDIS_URL (current: {settings.redis_url})."
        )
        raise RuntimeError(msg) from exc
    yield client
    await client.aclose()


@pytest_asyncio.fixture()
async def limiter(redis_client):
    limiter = RedisRateLimiter(redis_client)
    yield limiter
    await redis_client.flushdb()
