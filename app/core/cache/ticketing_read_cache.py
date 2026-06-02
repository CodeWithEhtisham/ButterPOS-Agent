"""Ticket and contact read caches — hot path in Redis (Task 1.5.1)."""

from __future__ import annotations

from functools import lru_cache

from app.core.cache.json_blob_cache import InMemoryJsonBlobCache, JsonBlobCache, RedisJsonBlobCache
from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.models.standard import CreateContactRequest, StandardContact, StandardTicket

logger = get_logger("app.cache.ticketing")


def contact_lookup_key(request: CreateContactRequest) -> str | None:
    """Stable lookup key aligned with Chatwoot contact filter order."""
    if request.external_user_id:
        return f"uid:{request.external_user_id}"
    if request.email:
        return f"email:{request.email.strip().lower()}"
    if request.phone:
        return f"phone:{request.phone.strip()}"
    return None


class TicketingReadCache:
    """Redis read-through cache for get_ticket and get_or_create_contact."""

    def __init__(
        self,
        blob_cache: JsonBlobCache,
        *,
        ticket_prefix: str,
        contact_prefix: str,
        ticket_ttl_seconds: int,
        contact_ttl_seconds: int,
    ) -> None:
        self._cache = blob_cache
        self._ticket_prefix = ticket_prefix
        self._contact_prefix = contact_prefix
        self._ticket_ttl = ticket_ttl_seconds
        self._contact_ttl = contact_ttl_seconds

    def _ticket_key(self, provider_ticket_id: str) -> str:
        return f"{self._ticket_prefix}{provider_ticket_id}"

    def _contact_pid_key(self, provider_contact_id: str) -> str:
        return f"{self._contact_prefix}pid:{provider_contact_id}"

    def _contact_lookup_key(self, lookup_key: str) -> str:
        return f"{self._contact_prefix}lookup:{lookup_key}"

    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket | None:
        raw = await self._cache.get(self._ticket_key(provider_ticket_id))
        if raw is None:
            return None
        return StandardTicket.model_validate(raw)

    async def set_ticket(self, ticket: StandardTicket) -> None:
        await self._cache.set(
            self._ticket_key(ticket.provider_ticket_id),
            ticket.model_dump(mode="json"),
            ttl_seconds=self._ticket_ttl,
        )

    async def invalidate_ticket(self, provider_ticket_id: str) -> None:
        await self._cache.delete(self._ticket_key(provider_ticket_id))
        logger.debug(
            "ticket_read_cache_invalidated provider_ticket_id=%s",
            provider_ticket_id,
            extra={"ticket_id": provider_ticket_id},
        )

    async def get_contact_by_lookup(self, lookup_key: str) -> StandardContact | None:
        raw = await self._cache.get(self._contact_lookup_key(lookup_key))
        if raw is None:
            return None
        return StandardContact.model_validate(raw)

    async def set_contact(
        self,
        contact: StandardContact,
        *,
        lookup_key: str | None,
    ) -> None:
        payload = contact.model_dump(mode="json")
        await self._cache.set(
            self._contact_pid_key(contact.provider_contact_id),
            payload,
            ttl_seconds=self._contact_ttl,
        )
        if lookup_key is not None:
            await self._cache.set(
                self._contact_lookup_key(lookup_key),
                payload,
                ttl_seconds=self._contact_ttl,
            )

    async def invalidate_contact(self, provider_contact_id: str) -> None:
        await self._cache.delete(self._contact_pid_key(provider_contact_id))
        logger.debug(
            "contact_read_cache_invalidated provider_contact_id=%s",
            provider_contact_id,
        )

    async def invalidate_for_webhook(
        self,
        *,
        provider_ticket_id: str,
        sender_provider_contact_id: str | None = None,
    ) -> None:
        """Drop cached reads affected by an inbound webhook event."""
        await self.invalidate_ticket(provider_ticket_id)
        if sender_provider_contact_id:
            await self.invalidate_contact(sender_provider_contact_id)


def build_ticketing_read_cache(
    settings: Settings,
    *,
    blob_cache: JsonBlobCache | None = None,
) -> TicketingReadCache:
    cache = blob_cache or RedisJsonBlobCache(settings.redis_url)
    return TicketingReadCache(
        cache,
        ticket_prefix=settings.ticket_read_cache_redis_prefix,
        contact_prefix=settings.contact_read_cache_redis_prefix,
        ticket_ttl_seconds=settings.ticket_read_cache_ttl_seconds,
        contact_ttl_seconds=settings.contact_read_cache_ttl_seconds,
    )


@lru_cache
def get_ticketing_read_cache() -> TicketingReadCache:
    return build_ticketing_read_cache(get_settings())


def clear_ticketing_read_cache() -> None:
    get_ticketing_read_cache.cache_clear()
