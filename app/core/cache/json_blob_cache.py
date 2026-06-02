"""Async JSON blob cache — Redis production, in-memory for tests."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

import redis.asyncio as aioredis


class JsonBlobCache(ABC):
    """Key/value JSON cache with TTL."""

    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        """Return parsed JSON object or None if missing/expired."""

    @abstractmethod
    async def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int) -> None:
        """Store JSON-serializable dict with TTL."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a single cache entry."""

    async def aclose(self) -> None:
        """Release connections — no-op for in-memory."""


class RedisJsonBlobCache(JsonBlobCache):
    """Production cache using redis.asyncio."""

    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None

    async def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int) -> None:
        await self._redis.setex(key, ttl_seconds, json.dumps(value))

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def aclose(self) -> None:
        await self._redis.aclose()


class InMemoryJsonBlobCache(JsonBlobCache):
    """Test double — TTL enforced on read."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, dict[str, Any]]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() >= expires_at:
            del self._entries[key]
            return None
        return value

    async def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int) -> None:
        self._entries[key] = (time.time() + ttl_seconds, value)

    async def delete(self, key: str) -> None:
        self._entries.pop(key, None)
