"""Request dedup and inbound PII integration tests — Task 1.5.3."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import Settings
from app.core.dedup.ticket_creation_store import extract_ticket_creation_dedup_key
from app.core.dedup.store import InMemoryDedupStore
from app.core.dedup.webhook import WebhookHotDedupStore
from app.providers.ticketing.deduping_adapter import DedupingTicketingProvider
from app.core.pii.detector import RegexPiiDetector
from app.core.pii.masker import PIIMasker
from app.core.pii.store import InMemoryPiiTokenStore
from app.models.standard import (
    CreateTicketRequest,
    StandardEvent,
    StandardEventType,
    StandardStatus,
    StandardTicket,
)
from app.services.inbound_pii_service import InboundPiiService
from app.services.webhook_service import WebhookService
from app.services.webhook_dispatch import NoOpWebhookDispatcher
from tests.support.idempotency_memory_session import IdempotencyMemorySession


def _ticket(ticket_id: str = "99") -> StandardTicket:
    return StandardTicket(
        provider_ticket_id=ticket_id,
        status=StandardStatus.OPEN,
        provider_contact_id="101",
    )


def test_extract_ticket_creation_dedup_key_prefers_client_request_id() -> None:
    assert extract_ticket_creation_dedup_key({"source_id": "a", "client_request_id": "tap-1"}) == "tap-1"


def test_extract_ticket_creation_dedup_key_returns_none_without_metadata() -> None:
    assert extract_ticket_creation_dedup_key({}) is None


def test_deduping_provider_returns_cached_ticket_on_replay() -> None:
    store = InMemoryDedupStore()
    inner = MagicMock()
    inner.provider_name = "chatwoot"
    inner.create_ticket = AsyncMock(return_value=_ticket("555"))
    provider = DedupingTicketingProvider(inner, store, ttl_seconds=3600)
    request = CreateTicketRequest(
        provider_contact_id="101",
        metadata={"client_request_id": "double-tap-1"},
    )

    async def _run() -> None:
        first = await provider.create_ticket(request)
        second = await provider.create_ticket(request)
        assert first.provider_ticket_id == "555"
        assert second.provider_ticket_id == "555"
        inner.create_ticket.assert_awaited_once()

    asyncio.run(_run())


def test_deduping_provider_creates_without_dedup_key() -> None:
    store = InMemoryDedupStore()
    inner = MagicMock()
    inner.provider_name = "chatwoot"
    inner.create_ticket = AsyncMock(return_value=_ticket("1"))
    provider = DedupingTicketingProvider(inner, store, ttl_seconds=3600)
    request = CreateTicketRequest(provider_contact_id="101")

    async def _run() -> None:
        await provider.create_ticket(request)
        await provider.create_ticket(request)
        assert inner.create_ticket.await_count == 2

    asyncio.run(_run())


def test_webhook_hot_dedup_skips_postgres_on_replay() -> None:
    store = InMemoryDedupStore()
    hot = WebhookHotDedupStore(store, ttl_seconds=3600)
    provider = MagicMock()
    provider.provider_name = "chatwoot"
    provider.verify_webhook = AsyncMock(return_value=True)
    event = StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="1",
        provider_ticket_id="5678",
        occurred_at=datetime.now(tz=UTC),
        idempotency_key="message_created:1",
    )
    provider.parse_webhook = AsyncMock(return_value=event)
    session = IdempotencyMemorySession()

    async def _run() -> None:
        service = WebhookService(
            provider,
            session,
            settings=Settings(_env_file=None),
            dispatcher=NoOpWebhookDispatcher(),
            hot_dedup=hot,
            rate_limiter=MagicMock(check=AsyncMock()),
        )
        first = await service.receive_chatwoot(b"{}", {})
        second = await service.receive_chatwoot(b"{}", {})
        assert first.status == "accepted"
        assert second.status == "duplicate"
        assert len(session._rows) == 1

    asyncio.run(_run())


def test_inbound_pii_service_masks_incoming_message_body() -> None:
    masker = PIIMasker(store=InMemoryPiiTokenStore(), detector=RegexPiiDetector())
    service = InboundPiiService(masker)
    event = StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="1",
        provider_ticket_id="5678",
        occurred_at=datetime.now(tz=UTC),
        message_body="Email ali@restaurant.pk please",
        message_direction="incoming",
    )

    async def _run() -> None:
        masked = await service.mask_event_for_processing(event)
        assert masked.message_body is not None
        assert "ali@restaurant.pk" not in masked.message_body
        assert "[PII:EMAIL_ADDRESS:" in masked.message_body

    asyncio.run(_run())


def test_inbound_pii_service_skips_outgoing_messages() -> None:
    masker = PIIMasker(store=InMemoryPiiTokenStore(), detector=RegexPiiDetector())
    service = InboundPiiService(masker)
    event = StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="1",
        provider_ticket_id="5678",
        occurred_at=datetime.now(tz=UTC),
        message_body="ali@restaurant.pk",
        message_direction="outgoing",
    )

    async def _run() -> None:
        result = await service.mask_event_for_processing(event)
        assert result.message_body == "ali@restaurant.pk"

    asyncio.run(_run())
