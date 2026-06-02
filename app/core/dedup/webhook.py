"""Webhook idempotency hot-path — Redis layer before Postgres."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.dedup.store import DedupStore, InMemoryDedupStore, RedisDedupStore


class WebhookHotDedupStore:
    """Fast duplicate detection for webhook idempotency keys."""

    def __init__(self, store: DedupStore, *, ttl_seconds: int) -> None:
        self._store = store
        self._ttl_seconds = ttl_seconds

    async def is_duplicate(self, idempotency_key: str) -> bool:
        return await self._store.get(idempotency_key) is not None

    async def remember(self, idempotency_key: str) -> None:
        await self._store.store(
            idempotency_key,
            {"seen": True},
            ttl_seconds=self._ttl_seconds,
        )


def build_webhook_hot_dedup_store(
    settings: Settings,
    *,
    store: DedupStore | None = None,
) -> WebhookHotDedupStore:
    dedup_store = store or RedisDedupStore(
        settings.redis_url,
        key_prefix=settings.webhook_hot_dedup_redis_prefix,
    )
    return WebhookHotDedupStore(dedup_store, ttl_seconds=settings.webhook_hot_dedup_ttl_seconds)


@lru_cache
def get_webhook_hot_dedup_store() -> WebhookHotDedupStore:
    return build_webhook_hot_dedup_store(get_settings())


def clear_webhook_hot_dedup_store_cache() -> None:
    get_webhook_hot_dedup_store.cache_clear()
