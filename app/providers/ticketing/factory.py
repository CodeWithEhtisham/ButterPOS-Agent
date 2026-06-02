"""Ticketing provider factory — selects adapter from TICKETING_PROVIDER env."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.ticketing.base import TicketingProvider
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter

ProviderBuilder = Callable[[Settings], TicketingProvider]

_REGISTRY: dict[str, ProviderBuilder] = {
    "chatwoot": lambda settings: ChatwootAdapter(settings),
}


class UnknownTicketingProviderError(ValueError):
    """Raised when TICKETING_PROVIDER is not registered."""


def create_ticketing_provider(settings: Settings) -> TicketingProvider:
    """Instantiate the configured ticketing adapter."""
    name = settings.ticketing_provider
    builder = _REGISTRY.get(name)
    if builder is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise UnknownTicketingProviderError(
            f"Unknown ticketing provider {name!r}. Supported: {supported}"
        )
    return builder(settings)


@lru_cache
def get_ticketing_provider() -> TicketingProvider:
    """Cached singleton for request-scoped FastAPI dependency injection."""
    return create_ticketing_provider(get_settings())


def clear_ticketing_provider_cache() -> None:
    """Reset cached provider — use in tests after env overrides."""
    get_ticketing_provider.cache_clear()
