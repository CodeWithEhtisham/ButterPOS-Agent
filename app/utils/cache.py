"""Caching decorators / helpers using Redis."""

import functools
import json
from typing import Callable

from app.utils.redis_client import get_redis_client


def cached(prefix: str, ttl: int = 300):
    """Decorator that caches function results in Redis with a TTL."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client = await get_redis_client()
            cache_key = f"{prefix}:{json.dumps(args)}:{json.dumps(kwargs, sort_keys=True)}"
            cached_value = await client.get(cache_key)
            if cached_value is not None:
                return json.loads(cached_value)
            result = await func(*args, **kwargs)
            await client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
