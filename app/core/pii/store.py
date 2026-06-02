"""PII token storage for reversible masking."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import redis.asyncio as aioredis


class PiiTokenStore(ABC):
    """Maps opaque mask tokens back to original PII values."""

    @abstractmethod
    async def put(self, token_id: str, original: str, entity_type: str) -> None:
        """Store original value for a mask token."""

    @abstractmethod
    async def get(self, token_id: str) -> str | None:
        """Retrieve original value; None if expired or unknown."""


class InMemoryPiiTokenStore(PiiTokenStore):
    """In-process store for unit tests."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    async def put(self, token_id: str, original: str, entity_type: str) -> None:
        del entity_type  # not needed for in-memory tests
        self._values[token_id] = original

    async def get(self, token_id: str) -> str | None:
        return self._values.get(token_id)


class RedisPiiTokenStore(PiiTokenStore):
    """Redis-backed store with TTL (default 24h)."""

    def __init__(self, redis_url: str, *, ttl_seconds: int, key_prefix: str = "pii:token:") -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds
        self._key_prefix = key_prefix

    def _key(self, token_id: str) -> str:
        return f"{self._key_prefix}{token_id}"

    async def put(self, token_id: str, original: str, entity_type: str) -> None:
        payload = json.dumps({"original": original, "entity_type": entity_type})
        await self._redis.setex(self._key(token_id), self._ttl_seconds, payload)

    async def get(self, token_id: str) -> str | None:
        raw = await self._redis.get(self._key(token_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return str(data.get("original", ""))

    async def aclose(self) -> None:
        await self._redis.aclose()
