from __future__ import annotations

import pytest

from vaultlog.infrastructure.security.rate_limit import RedisRateLimiter


@pytest.mark.asyncio
async def test_allows_up_to_capacity(limiter: RedisRateLimiter) -> None:
    for _ in range(5):
        assert await limiter.check("rl:test:a", capacity=5, window_seconds=60)
    assert not await limiter.check("rl:test:a", capacity=5, window_seconds=60)


@pytest.mark.asyncio
async def test_rejected_requests_do_not_consume_quota(
    limiter: RedisRateLimiter,
    redis_client,
) -> None:
    for _ in range(10):
        await limiter.check("rl:test:b", capacity=5, window_seconds=60)
    assert await redis_client.zcard("rl:test:b") == 5


@pytest.mark.asyncio
async def test_concurrent_instances_share_state(
    limiter: RedisRateLimiter,
    redis_client,
) -> None:
    other = RedisRateLimiter(redis_client)
    for _ in range(3):
        await limiter.check("rl:test:c", capacity=5, window_seconds=60)
    for _ in range(2):
        await other.check("rl:test:c", capacity=5, window_seconds=60)
    assert not await other.check("rl:test:c", capacity=5, window_seconds=60)
    assert not await limiter.check("rl:test:c", capacity=5, window_seconds=60)
