"""Ticketing provider adapters."""

from app.providers.ticketing.base import TicketingProvider
from app.providers.ticketing.caching_adapter import CachingTicketingProvider
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter
from app.providers.ticketing.factory import (
    UnknownTicketingProviderError,
    clear_ticketing_provider_cache,
    create_ticketing_provider,
    get_ticketing_provider,
)

__all__ = [
    "ChatwootAdapter",
    "TicketingProvider",
    "UnknownTicketingProviderError",
    "clear_ticketing_provider_cache",
    "create_ticketing_provider",
    "get_ticketing_provider",
]
