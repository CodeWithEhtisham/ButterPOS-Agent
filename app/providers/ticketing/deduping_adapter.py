"""Ticket creation request dedup decorator — Task 1.5.3."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from app.core.dedup.store import DedupClaimResult, DedupStore
from app.core.dedup.ticket_creation_store import DEDUP_METADATA_KEYS, extract_ticket_creation_dedup_key
from app.core.logging_config import get_logger
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

logger = get_logger("app.dedup")


class DedupingTicketingProvider(TicketingProvider):
    """Decorator — returns cached StandardTicket when the same client request id is replayed."""

    def __init__(
        self,
        inner: TicketingProvider,
        store: DedupStore,
        *,
        ttl_seconds: int,
        dedup_metadata_keys: tuple[str, ...] = DEDUP_METADATA_KEYS,
        in_progress_poll_seconds: float = 0.05,
        in_progress_max_wait_seconds: float = 2.0,
    ) -> None:
        self._inner = inner
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._dedup_metadata_keys = dedup_metadata_keys
        self._in_progress_poll_seconds = in_progress_poll_seconds
        self._in_progress_max_wait_seconds = in_progress_max_wait_seconds
        self.provider_name = inner.provider_name

    @property
    def inner(self) -> TicketingProvider:
        return self._inner

    async def create_ticket(self, request: CreateTicketRequest) -> StandardTicket:
        dedup_key = extract_ticket_creation_dedup_key(
            request.metadata,
            key_names=self._dedup_metadata_keys,
        )
        if dedup_key is None:
            return await self._inner.create_ticket(request)

        cached = await self._store.get(dedup_key)
        if cached is not None:
            logger.info(
                "ticket_creation_dedup_hit dedup_key=%s ticket_id=%s",
                dedup_key,
                cached.get("provider_ticket_id"),
                extra={"dedup_key": dedup_key, "ticket_id": cached.get("provider_ticket_id")},
            )
            return StandardTicket.model_validate(cached)

        claim = await self._store.claim(dedup_key, ttl_seconds=self._ttl_seconds)
        if claim is DedupClaimResult.EXISTS:
            cached = await self._store.get(dedup_key)
            if cached is not None:
                return StandardTicket.model_validate(cached)
        elif claim is DedupClaimResult.IN_PROGRESS:
            ticket = await self._wait_for_peer_result(dedup_key)
            if ticket is not None:
                return ticket

        try:
            ticket = await self._inner.create_ticket(request)
        except Exception:
            await self._store.release(dedup_key)
            raise

        await self._store.store(
            dedup_key,
            ticket.model_dump(mode="json"),
            ttl_seconds=self._ttl_seconds,
        )
        logger.info(
            "ticket_creation_dedup_stored dedup_key=%s ticket_id=%s",
            dedup_key,
            ticket.provider_ticket_id,
            extra={"dedup_key": dedup_key, "ticket_id": ticket.provider_ticket_id},
        )
        return ticket

    async def _wait_for_peer_result(self, dedup_key: str) -> StandardTicket | None:
        deadline = time.monotonic() + self._in_progress_max_wait_seconds
        while time.monotonic() < deadline:
            cached = await self._store.get(dedup_key)
            if cached is not None:
                return StandardTicket.model_validate(cached)
            await asyncio.sleep(self._in_progress_poll_seconds)
        return None

    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket:
        return await self._inner.get_ticket(provider_ticket_id)

    async def get_or_create_contact(self, request: CreateContactRequest) -> StandardContact:
        return await self._inner.get_or_create_contact(request)

    async def update_status(self, request: UpdateStatusRequest) -> StandardTicket:
        return await self._inner.update_status(request)

    async def assign_agent(self, request: AssignAgentRequest) -> StandardTicket:
        return await self._inner.assign_agent(request)

    async def add_tags(self, request: AddTagsRequest) -> StandardTicket:
        return await self._inner.add_tags(request)

    async def add_comment(self, request: AddCommentRequest) -> str | None:
        return await self._inner.add_comment(request)

    async def add_customer_message(self, request: AddCustomerMessageRequest) -> str | None:
        return await self._inner.add_customer_message(request)

    async def add_note(self, request: AddNoteRequest) -> None:
        await self._inner.add_note(request)

    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return await self._inner.verify_webhook(raw_body, headers)

    async def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        return await self._inner.parse_webhook(raw_body, headers)

    async def list_tickets_updated_since(self, since: datetime) -> list[StandardTicket]:
        return await self._inner.list_tickets_updated_since(since)

    async def health_check(self) -> ProviderHealth:
        return await self._inner.health_check()
