"""Read-through Redis cache wrapper for TicketingProvider (Task 1.5.1)."""

from __future__ import annotations

from datetime import datetime

from app.core.cache.ticketing_read_cache import TicketingReadCache, contact_lookup_key
from app.models.standard import (
    AddCommentRequest,
    AddCustomerMessageRequest,
    AddNoteRequest,
    AddTagsRequest,
    AssignAgentRequest,
    CreateContactRequest,
    CreateTicketRequest,
    ProviderHealth,
    StandardContact,
    StandardEvent,
    StandardTicket,
    UpdateStatusRequest,
)
from app.providers.ticketing.base import TicketingProvider


class CachingTicketingProvider(TicketingProvider):
    """Decorator — caches ticket/contact reads; invalidates on writes and webhooks."""

    def __init__(self, inner: TicketingProvider, read_cache: TicketingReadCache) -> None:
        self._inner = inner
        self._cache = read_cache
        self.provider_name = inner.provider_name

    @property
    def inner(self) -> TicketingProvider:
        return self._inner

    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket:
        cached = await self._cache.get_ticket(provider_ticket_id)
        if cached is not None:
            return cached
        ticket = await self._inner.get_ticket(provider_ticket_id)
        await self._cache.set_ticket(ticket)
        return ticket

    async def get_or_create_contact(self, request: CreateContactRequest) -> StandardContact:
        lookup = contact_lookup_key(request)
        if lookup is not None:
            cached = await self._cache.get_contact_by_lookup(lookup)
            if cached is not None:
                return cached
        contact = await self._inner.get_or_create_contact(request)
        await self._cache.set_contact(contact, lookup_key=lookup)
        return contact

    async def create_ticket(self, request: CreateTicketRequest) -> StandardTicket:
        ticket = await self._inner.create_ticket(request)
        await self._cache.set_ticket(ticket)
        return ticket

    async def update_status(self, request: UpdateStatusRequest) -> StandardTicket:
        ticket = await self._inner.update_status(request)
        await self._cache.set_ticket(ticket)
        return ticket

    async def assign_agent(self, request: AssignAgentRequest) -> StandardTicket:
        ticket = await self._inner.assign_agent(request)
        await self._cache.set_ticket(ticket)
        return ticket

    async def add_tags(self, request: AddTagsRequest) -> StandardTicket:
        ticket = await self._inner.add_tags(request)
        await self._cache.set_ticket(ticket)
        return ticket

    async def add_comment(self, request: AddCommentRequest) -> str | None:
        message_id = await self._inner.add_comment(request)
        await self._cache.invalidate_ticket(request.provider_ticket_id)
        return message_id

    async def add_customer_message(self, request: AddCustomerMessageRequest) -> str | None:
        message_id = await self._inner.add_customer_message(request)
        await self._cache.invalidate_ticket(request.provider_ticket_id)
        return message_id

    async def add_note(self, request: AddNoteRequest) -> None:
        await self._inner.add_note(request)
        await self._cache.invalidate_ticket(request.provider_ticket_id)

    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return await self._inner.verify_webhook(raw_body, headers)

    async def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        return await self._inner.parse_webhook(raw_body, headers)

    async def list_tickets_updated_since(self, since: datetime) -> list[StandardTicket]:
        return await self._inner.list_tickets_updated_since(since)

    async def health_check(self) -> ProviderHealth:
        return await self._inner.health_check()
