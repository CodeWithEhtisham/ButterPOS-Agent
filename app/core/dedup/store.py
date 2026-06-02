"""Generic Redis dedup store — result cache + in-flight lock."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import redis.asyncio as aioredis


class DedupClaimResult(str, Enum):
    """Outcome of attempting to claim a dedup key."""

    CLAIMED = "claimed"
    EXISTS = "exists"
    IN_PROGRESS = "in_progress"


class DedupStore(ABC):
    """Maps opaque request keys to cached JSON results."""

    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        """Return stored result dict, or None if unknown."""

    @abstractmethod
    async def claim(self, key: str, *, ttl_seconds: int) -> DedupClaimResult:
        """Try to start work — EXISTS if result ready, IN_PROGRESS if another worker holds lock."""

    @abstractmethod
    async def store(self, key: str, result: dict[str, Any], *, ttl_seconds: int) -> None:
        """Persist completed result and release in-flight lock."""

    @abstractmethod
    async def release(self, key: str) -> None:
        """Drop in-flight lock after failure so callers may retry."""


class RedisDedupStore(DedupStore):
    """Production dedup — separate Redis keys for lock and result."""

    def __init__(self, redis_url: str, *, key_prefix: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    def _result_key(self, key: str) -> str:
        return f"{self._key_prefix}{key}:result"

    def _lock_key(self, key: str) -> str:
        return f"{self._key_prefix}{key}:lock"

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._result_key(key))
        if raw is None:
            return None
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None

    async def claim(self, key: str, *, ttl_seconds: int) -> DedupClaimResult:
        existing = await self.get(key)
        if existing is not None:
            return DedupClaimResult.EXISTS

        lock_ttl = min(ttl_seconds, 60)
        acquired = await self._redis.set(self._lock_key(key), "1", nx=True, ex=lock_ttl)
        if acquired:
            return DedupClaimResult.CLAIMED
        if await self.get(key) is not None:
            return DedupClaimResult.EXISTS
        return DedupClaimResult.IN_PROGRESS

    async def store(self, key: str, result: dict[str, Any], *, ttl_seconds: int) -> None:
        await self._redis.setex(self._result_key(key), ttl_seconds, json.dumps(result))
        await self._redis.delete(self._lock_key(key))

    async def release(self, key: str) -> None:
        await self._redis.delete(self._lock_key(key))

    async def aclose(self) -> None:
        await self._redis.aclose()


class InMemoryDedupStore(DedupStore):
    """Test double — no TTL enforcement."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}
        self._locks: set[str] = set()

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._results.get(key)

    async def claim(self, key: str, *, ttl_seconds: int) -> DedupClaimResult:
        del ttl_seconds
        if key in self._results:
            return DedupClaimResult.EXISTS
        if key in self._locks:
            return DedupClaimResult.IN_PROGRESS
        self._locks.add(key)
        return DedupClaimResult.CLAIMED

    async def store(self, key: str, result: dict[str, Any], *, ttl_seconds: int) -> None:
        del ttl_seconds
        self._results[key] = result
        self._locks.discard(key)

    async def release(self, key: str) -> None:
        self._locks.discard(key)
