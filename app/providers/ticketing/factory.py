"""Ticketing provider factory — selects adapter from TICKETING_PROVIDER env."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.cache.ticketing_read_cache import TicketingReadCache, build_ticketing_read_cache
from app.core.dedup.store import DedupStore
from app.core.dedup.ticket_creation_store import build_ticket_creation_dedup_store
from app.providers.ticketing.deduping_adapter import DedupingTicketingProvider
from app.providers.ticketing.base import TicketingProvider
from app.providers.ticketing.caching_adapter import CachingTicketingProvider
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter

ProviderBuilder = Callable[[Settings], TicketingProvider]

_REGISTRY: dict[str, ProviderBuilder] = {
    "chatwoot": lambda settings: ChatwootAdapter(settings),
}


class UnknownTicketingProviderError(ValueError):
    """Raised when TICKETING_PROVIDER is not registered."""


def create_ticketing_provider(
    settings: Settings,
    *,
    read_cache: TicketingReadCache | None = None,
    dedup_store: DedupStore | None = None,
) -> TicketingProvider:
    """Instantiate the configured ticketing adapter with dedup + read-through Redis cache."""
    name = settings.ticketing_provider
    builder = _REGISTRY.get(name)
    if builder is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise UnknownTicketingProviderError(
            f"Unknown ticketing provider {name!r}. Supported: {supported}"
        )
    inner = builder(settings)
    store = dedup_store or build_ticket_creation_dedup_store(settings)
    deduped = DedupingTicketingProvider(
        inner,
        store,
        ttl_seconds=settings.request_dedup_ttl_seconds,
        dedup_metadata_keys=tuple(settings.ticket_dedup_metadata_key_list()),
        in_progress_poll_seconds=settings.request_dedup_in_progress_poll_seconds,
        in_progress_max_wait_seconds=settings.request_dedup_in_progress_max_wait_seconds,
    )
    cache = read_cache or build_ticketing_read_cache(settings)
    return CachingTicketingProvider(deduped, cache)


@lru_cache
def get_ticketing_provider() -> TicketingProvider:
    """Cached singleton for request-scoped FastAPI dependency injection."""
    return create_ticketing_provider(get_settings())


def clear_ticketing_provider_cache() -> None:
    """Reset cached provider — use in tests after env overrides."""
    get_ticketing_provider.cache_clear()
