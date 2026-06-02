"""Redis-backed webhook dead letter queue — retry buffer separate from Celery broker."""

from __future__ import annotations

import json
import time
from functools import lru_cache

import redis

from app.core.config import Settings, get_settings
from app.schemas.webhook_dlq import WebhookDlqPayload


class WebhookDlqStore:
    """Sorted-set DLQ — score is next_retry_at unix timestamp."""

    def __init__(self, redis_url: str, *, key: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._key = key

    def enqueue(self, entry: WebhookDlqPayload) -> None:
        payload = entry.model_dump(mode="json")
        self._redis.zadd(self._key, {json.dumps(payload): entry.next_retry_at})

    def pop_ready(self, *, limit: int = 50) -> list[WebhookDlqPayload]:
        now = time.time()
        raw_items = self._redis.zrangebyscore(self._key, "-inf", now, start=0, num=limit)
        entries: list[WebhookDlqPayload] = []
        for raw in raw_items:
            self._redis.zrem(self._key, raw)
            entries.append(WebhookDlqPayload.model_validate(json.loads(raw)))
        return entries

    def close(self) -> None:
        self._redis.close()


class InMemoryWebhookDlqStore:
    """Test double — same interface as Redis store without network."""

    def __init__(self) -> None:
        self._items: list[tuple[float, WebhookDlqPayload]] = []

    def enqueue(self, entry: WebhookDlqPayload) -> None:
        self._items.append((entry.next_retry_at, entry))

    def pop_ready(self, *, limit: int = 50) -> list[WebhookDlqPayload]:
        now = time.time()
        ready = [entry for retry_at, entry in self._items if retry_at <= now]
        self._items = [(retry_at, entry) for retry_at, entry in self._items if retry_at > now]
        return ready[:limit]

    def close(self) -> None:
        return None


@lru_cache
def get_webhook_dlq_store() -> WebhookDlqStore:
    settings = get_settings()
    return WebhookDlqStore(
        settings.redis_url,
        key=settings.webhook_dlq_redis_key,
    )


def build_webhook_dlq_store(settings: Settings) -> WebhookDlqStore:
    """Non-cached factory for worker tasks (fresh settings)."""
    return WebhookDlqStore(
        settings.redis_url,
        key=settings.webhook_dlq_redis_key,
    )


def clear_webhook_dlq_store_cache() -> None:
    get_webhook_dlq_store.cache_clear()
