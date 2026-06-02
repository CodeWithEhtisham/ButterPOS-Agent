"""Ticketing read cache tests — Task 1.5 sub-step 1."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.cache.json_blob_cache import InMemoryJsonBlobCache
from app.core.cache.ticketing_read_cache import (
    TicketingReadCache,
    build_ticketing_read_cache,
    contact_lookup_key,
)
from app.core.config import Settings
from app.core.cache.ticketing_read_cache import clear_ticketing_read_cache
from app.models.standard import (
    CreateContactRequest,
    StandardContact,
    StandardStatus,
    StandardTicket,
)
from app.providers.ticketing.caching_adapter import CachingTicketingProvider
from app.services.webhook_processor import process_webhook_event
from app.models.standard import StandardEvent, StandardEventType


def _settings(**overrides: object) -> Settings:
    base = {
        "_env_file": None,
        "ticket_read_cache_ttl_seconds": 60,
        "contact_read_cache_ttl_seconds": 86400,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ticket(ticket_id: str = "100") -> StandardTicket:
    return StandardTicket(
        provider_ticket_id=ticket_id,
        status=StandardStatus.OPEN,
        subject="Help",
        provider_contact_id="7",
    )


def _contact() -> StandardContact:
    return StandardContact(
        provider_contact_id="7",
        name="Branch User",
        email="user@example.com",
    )


def test_contact_lookup_key_prefers_external_user_id() -> None:
    key = contact_lookup_key(
        CreateContactRequest(external_user_id="staff-42", email="a@b.com")
    )
    assert key == "uid:staff-42"


def test_ticket_cache_get_set_and_invalidate() -> None:
    async def _run() -> None:
        cache = build_ticketing_read_cache(_settings(), blob_cache=InMemoryJsonBlobCache())
        assert await cache.get_ticket("100") is None
        await cache.set_ticket(_ticket())
        assert (await cache.get_ticket("100")).status == StandardStatus.OPEN
        await cache.invalidate_ticket("100")
        assert await cache.get_ticket("100") is None

    asyncio.run(_run())


def test_contact_cache_by_lookup() -> None:
    async def _run() -> None:
        cache = build_ticketing_read_cache(_settings(), blob_cache=InMemoryJsonBlobCache())
        await cache.set_contact(_contact(), lookup_key="uid:staff-1")
        found = await cache.get_contact_by_lookup("uid:staff-1")
        assert found is not None
        assert found.provider_contact_id == "7"

    asyncio.run(_run())


def test_caching_provider_returns_cached_ticket_without_inner_call() -> None:
    inner = MagicMock()
    inner.provider_name = "chatwoot"
    inner.get_ticket = AsyncMock(return_value=_ticket())
    blob = InMemoryJsonBlobCache()
    read_cache = build_ticketing_read_cache(_settings(), blob_cache=blob)
    provider = CachingTicketingProvider(inner, read_cache)

    async def _run() -> None:
        first = await provider.get_ticket("100")
        second = await provider.get_ticket("100")
        assert first.provider_ticket_id == "100"
        assert second.provider_ticket_id == "100"
        inner.get_ticket.assert_awaited_once()

    asyncio.run(_run())


def test_caching_provider_invalidates_ticket_on_add_comment() -> None:
    inner = MagicMock()
    inner.provider_name = "chatwoot"
    inner.get_ticket = AsyncMock(return_value=_ticket())
    inner.add_comment = AsyncMock()
    read_cache = build_ticketing_read_cache(_settings(), blob_cache=InMemoryJsonBlobCache())
    provider = CachingTicketingProvider(inner, read_cache)

    async def _run() -> None:
        from app.models.standard import AddCommentRequest

        await provider.get_ticket("100")
        await provider.add_comment(
            AddCommentRequest(provider_ticket_id="100", body="hello"),
        )
        await provider.get_ticket("100")
        assert inner.get_ticket.await_count == 2

    asyncio.run(_run())


def test_webhook_processor_invalidates_read_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = InMemoryJsonBlobCache()
    read_cache = build_ticketing_read_cache(_settings(), blob_cache=blob)

    async def _run() -> None:
        await read_cache.set_ticket(_ticket("5678"))
        assert await read_cache.get_ticket("5678") is not None

        monkeypatch.setattr(
            "app.services.webhook_processor.get_ticketing_read_cache",
            lambda: read_cache,
        )
        event = StandardEvent(
            event_type=StandardEventType.MESSAGE_CREATED,
            provider_event_id="1",
            provider_ticket_id="5678",
            occurred_at=datetime.now(tz=UTC),
            sender_provider_contact_id="99",
        )
        await process_webhook_event(event)
        assert await read_cache.get_ticket("5678") is None

    asyncio.run(_run())
