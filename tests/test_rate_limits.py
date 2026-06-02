"""Inbound message rate limit tests — Task 1.5 sub-step 2."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import Settings
from app.core.dedup.store import InMemoryDedupStore
from app.core.dedup.webhook import WebhookHotDedupStore
from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit.inbound_message_limits import (
    InboundMessageRateLimiter,
    build_inbound_message_rate_limiter,
    extract_restaurant_rate_limit_key,
    extract_user_rate_limit_key,
    should_rate_limit_inbound_message,
)
from app.core.rate_limit.sliding_window import InMemorySlidingWindowRateLimiter
from app.models.standard import StandardEvent, StandardEventType
from app.repositories.webhook_event_repository import record_webhook_event
from app.services.webhook_dispatch import NoOpWebhookDispatcher
from app.services.webhook_service import WebhookService
from tests.support.idempotency_memory_session import IdempotencyMemorySession

RESTAURANT_ATTRS = ("restaurant_id", "butterpos_restaurant_id")


def _incoming_event(
    *,
    contact_id: str = "101",
    restaurant_id: str | None = "rest-1",
    message_id: str = "1",
) -> StandardEvent:
    custom_attributes = {"restaurant_id": restaurant_id} if restaurant_id else {}
    return StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id=message_id,
        provider_ticket_id="5678",
        occurred_at=datetime.now(tz=UTC),
        message_body="hello",
        message_direction="incoming",
        sender_provider_contact_id=contact_id,
        raw_payload={
            "event": "message_created",
            "id": int(message_id),
            "conversation": {"id": 5678, "custom_attributes": custom_attributes},
        },
        idempotency_key=f"message_created:{message_id}",
    )


def test_should_rate_limit_incoming_message_only() -> None:
    assert should_rate_limit_inbound_message(_incoming_event()) is True
    outgoing = _incoming_event().model_copy(update={"message_direction": "outgoing"})
    assert should_rate_limit_inbound_message(outgoing) is False


def test_extract_rate_limit_keys() -> None:
    event = _incoming_event(contact_id="42", restaurant_id="99")
    assert extract_user_rate_limit_key(event) == "42"
    assert extract_restaurant_rate_limit_key(event, attribute_names=RESTAURANT_ATTRS) == "99"


def test_sliding_window_blocks_after_limit() -> None:
    async def _run() -> None:
        limiter = InMemorySlidingWindowRateLimiter(limit=2, window_seconds=3600)
        assert await limiter.allow("user-1") is True
        assert await limiter.allow("user-1") is True
        assert await limiter.allow("user-1") is False

    asyncio.run(_run())


def test_inbound_rate_limiter_enforces_user_quota() -> None:
    user = InMemorySlidingWindowRateLimiter(limit=2, window_seconds=3600)
    restaurant = InMemorySlidingWindowRateLimiter(limit=100, window_seconds=86400)
    limiter = InboundMessageRateLimiter(user, restaurant, restaurant_attribute_names=RESTAURANT_ATTRS)

    async def _run() -> None:
        event = _incoming_event(restaurant_id=None)
        await limiter.check(event)
        await limiter.check(_incoming_event(message_id="2", restaurant_id=None))
        with pytest.raises(RateLimitExceededError, match="User"):
            await limiter.check(_incoming_event(message_id="3", restaurant_id=None))

    asyncio.run(_run())


def test_inbound_rate_limiter_enforces_restaurant_quota() -> None:
    user = InMemorySlidingWindowRateLimiter(limit=100, window_seconds=3600)
    restaurant = InMemorySlidingWindowRateLimiter(limit=1, window_seconds=86400)
    limiter = InboundMessageRateLimiter(user, restaurant, restaurant_attribute_names=RESTAURANT_ATTRS)

    async def _run() -> None:
        await limiter.check(_incoming_event(message_id="1", contact_id="a"))
        with pytest.raises(RateLimitExceededError, match="Restaurant"):
            await limiter.check(_incoming_event(message_id="2", contact_id="b"))

    asyncio.run(_run())


def test_webhook_service_returns_rate_limited_without_dispatch() -> None:
    user = InMemorySlidingWindowRateLimiter(limit=1, window_seconds=3600)
    restaurant = InMemorySlidingWindowRateLimiter(limit=100, window_seconds=86400)
    rate_limiter = InboundMessageRateLimiter(
        user,
        restaurant,
        restaurant_attribute_names=RESTAURANT_ATTRS,
    )

    provider = MagicMock()
    provider.provider_name = "chatwoot"
    provider.verify_webhook = AsyncMock(return_value=True)
    event = _incoming_event()
    provider.parse_webhook = AsyncMock(return_value=event)

    session = IdempotencyMemorySession()

    async def _run() -> None:
        service = WebhookService(
            provider,
            session,
            settings=Settings(_env_file=None),
            dispatcher=NoOpWebhookDispatcher(),
            rate_limiter=rate_limiter,
            hot_dedup=WebhookHotDedupStore(InMemoryDedupStore(), ttl_seconds=3600),
        )
        first = await service.receive_chatwoot(b"{}", {})
        provider.parse_webhook = AsyncMock(
            return_value=_incoming_event(message_id="2"),
        )
        second = await service.receive_chatwoot(b"{}", {})
        assert first.status == "accepted"
        assert second.status == "rate_limited"
        row = session._rows["message_created:1"]
        assert row.status == "received"
        row2 = session._rows["message_created:2"]
        assert row2.status == "failed"

    asyncio.run(_run())
