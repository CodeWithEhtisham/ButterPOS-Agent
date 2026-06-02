"""Redis cursor for webhook polling fallback — last successful sync timestamp."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

import redis

from app.core.config import Settings, get_settings


class PollingCursorStore:
    """Stores last platform poll timestamp in Redis."""

    def __init__(self, redis_url: str, *, key: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._key = key

    def get_last_sync(self) -> datetime | None:
        raw = self._redis.get(self._key)
        if raw is None:
            return None
        return datetime.fromtimestamp(float(raw), tz=UTC)

    def set_last_sync(self, when: datetime) -> None:
        ts = when.timestamp()
        self._redis.set(self._key, str(ts))

    def close(self) -> None:
        self._redis.close()


class InMemoryPollingCursorStore:
    """Test double for polling cursor."""

    def __init__(self) -> None:
        self._value: datetime | None = None

    def get_last_sync(self) -> datetime | None:
        return self._value

    def set_last_sync(self, when: datetime) -> None:
        self._value = when

    def close(self) -> None:
        return None


@lru_cache
def get_polling_cursor_store() -> PollingCursorStore:
    settings = get_settings()
    return PollingCursorStore(
        settings.redis_url,
        key=settings.webhook_polling_cursor_redis_key,
    )


def build_polling_cursor_store(settings: Settings) -> PollingCursorStore:
    return PollingCursorStore(
        settings.redis_url,
        key=settings.webhook_polling_cursor_redis_key,
    )


def clear_polling_cursor_store_cache() -> None:
    get_polling_cursor_store.cache_clear()
