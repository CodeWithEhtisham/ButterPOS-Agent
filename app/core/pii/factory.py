"""PII masker factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.pii.masker import PIIMasker
from app.core.pii.store import PiiTokenStore, RedisPiiTokenStore


def create_pii_store(settings: Settings) -> PiiTokenStore:
    return RedisPiiTokenStore(
        settings.redis_url,
        ttl_seconds=settings.pii_token_ttl_seconds,
        key_prefix=settings.pii_redis_key_prefix,
    )


def create_pii_masker(settings: Settings, store: PiiTokenStore | None = None) -> PIIMasker:
    return PIIMasker(store=store or create_pii_store(settings))


@lru_cache
def get_pii_masker() -> PIIMasker:
    return create_pii_masker(get_settings())


def clear_pii_masker_cache() -> None:
    get_pii_masker.cache_clear()
