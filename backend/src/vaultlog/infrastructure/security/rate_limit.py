from __future__ import annotations

import time
import uuid

import redis.asyncio as redis
from redis.exceptions import RedisError

from vaultlog.domain.identity.exceptions import ServiceUnavailableError
from vaultlog.domain.identity.ports import RateLimitGate


class RedisRateLimiter(RateLimitGate):
    """Sliding-window counter backed by Redis sorted sets.

    Each key is a ZSET of request timestamps. On check:
      1. drop entries older than the window,
      2. count what remains,
      3. if under the limit, add this request and allow.
    All four commands run in ONE pipeline (MULTI/EXEC), so concurrent
    instances cannot interleave between count and add.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    async def check(
        self,
        key: str,
        *,
        capacity: int,
        window_seconds: int,
        fail_closed: bool = False,
    ) -> bool:
        try:
            return await self._check(key, capacity=capacity, window_seconds=window_seconds)
        except RedisError as exc:
            if fail_closed:
                raise ServiceUnavailableError("Service unavailable") from exc
            return True

    async def _check(self, key: str, *, capacity: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds
        member = f"{now}:{uuid.uuid4()}"

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds)
            _, count, _, _ = await pipe.execute()

        if count >= capacity:
            await self._redis.zrem(key, member)
            return False
        return True
