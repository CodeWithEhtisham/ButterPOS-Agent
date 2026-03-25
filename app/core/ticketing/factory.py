"""
Factory that loads the correct ticketing adapter based on config.
This is the ONLY place where platform-specific adapters are imported.
"""

from app.config import settings
from .interface import TicketingProvider


def get_ticketing_provider() -> TicketingProvider:
    """
    Returns the configured ticketing provider adapter.
    Change TICKETING_PROVIDER env var to switch platforms.
    """
    provider = settings.TICKETING_PROVIDER.lower()

    if provider == "zoho":
        from .adapters.zoho.adapter import ZohoAdapter
        return ZohoAdapter()

    # Future adapters:
    # elif provider == "freshdesk":
    #     from .adapters.freshdesk.adapter import FreshdeskAdapter
    #     return FreshdeskAdapter()
    # elif provider == "chatwoot":
    #     from .adapters.chatwoot.adapter import ChatwootAdapter
    #     return ChatwootAdapter()

    else:
        raise ValueError(
            f"Unknown ticketing provider: '{provider}'. "
            f"Supported: zoho. Set TICKETING_PROVIDER env var."
        )
