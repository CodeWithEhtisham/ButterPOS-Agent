"""Redis sorted-set sliding window rate limiter."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod

import redis.asyncio as aioredis


class SlidingWindowRateLimiter(ABC):
    """Fixed-window sliding counter — allow up to `limit` events per `window_seconds`."""

    @abstractmethod
    async def allow(self, key: str) -> bool:
        """Record one event; return False if limit exceeded."""


class RedisSlidingWindowRateLimiter(SlidingWindowRateLimiter):
    """Production limiter using Redis ZSET timestamps."""

    def __init__(self, redis_url: str, *, key_prefix: str, limit: int, window_seconds: int) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix
        self._limit = limit
        self._window_seconds = window_seconds

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    async def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - self._window_seconds
        redis_key = self._full_key(key)
        member = f"{now}:{uuid.uuid4().hex[:8]}"

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, "-inf", window_start)
            pipe.zadd(redis_key, {member: now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, self._window_seconds)
            _removed, _added, count, _ttl = await pipe.execute()

        if int(count) > self._limit:
            await self._redis.zrem(redis_key, member)
            return False
        return True

    async def aclose(self) -> None:
        await self._redis.aclose()


class InMemorySlidingWindowRateLimiter(SlidingWindowRateLimiter):
    """Test double — per-key timestamp lists."""

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._events: dict[str, list[float]] = {}

    async def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - self._window_seconds
        events = [ts for ts in self._events.get(key, []) if ts > window_start]
        if len(events) >= self._limit:
            self._events[key] = events
            return False
        events.append(now)
        self._events[key] = events
        return True

    def count(self, key: str) -> int:
        now = time.time()
        window_start = now - self._window_seconds
        return len([ts for ts in self._events.get(key, []) if ts > window_start])
