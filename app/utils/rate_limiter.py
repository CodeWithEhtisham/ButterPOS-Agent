"""Sliding window rate limiter using Redis."""

import time

from app.utils.redis_client import get_redis_client


class RateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets."""

    def __init__(self, key_prefix: str, max_requests: int, window_seconds: int):
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self, identifier: str) -> bool:
        client = await get_redis_client()
        key = f"ratelimit:{self.key_prefix}:{identifier}"
        now = time.time()
        window_start = now - self.window_seconds

        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window_seconds)
        results = await pipe.execute()

        current_count = results[1]
        return current_count < self.max_requests

    async def remaining(self, identifier: str) -> int:
        client = await get_redis_client()
        key = f"ratelimit:{self.key_prefix}:{identifier}"
        now = time.time()
        window_start = now - self.window_seconds

        await client.zremrangebyscore(key, 0, window_start)
        current_count = await client.zcard(key)
        return max(0, self.max_requests - current_count)
