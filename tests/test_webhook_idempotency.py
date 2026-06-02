"""Webhook idempotency repository tests — Task 1.4 sub-step 2."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import AppError
from app.models.standard import StandardEvent, StandardEventType
from app.repositories.webhook_event_repository import (
    compute_payload_hash,
    record_webhook_event,
)
from app.services.webhook_dispatch import NoOpWebhookDispatcher
from app.services.webhook_service import WebhookService
from sqlalchemy.exc import IntegrityError
from tests.support.idempotency_memory_session import IdempotencyMemorySession


def _event(*, key: str = "message_created:1", ticket_id: str = "5678") -> StandardEvent:
    return StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id="1",
        provider_ticket_id=ticket_id,
        occurred_at=datetime.now(tz=UTC),
        idempotency_key=key,
    )


def test_compute_payload_hash_is_sha256_hex() -> None:
    body = b'{"event":"message_created","id":1}'
    digest = compute_payload_hash(body)
    assert len(digest) == 64
    assert digest == compute_payload_hash(body)


def test_record_webhook_event_inserts_new_row() -> None:
    async def _run() -> None:
        session = IdempotencyMemorySession()
        body = b'{"event":"message_created","id":1}'
        result = await record_webhook_event(session, event=_event(), raw_body=body)
        assert result.status == "received"
        assert result.payload_hash == compute_payload_hash(body)
        assert "message_created:1" in session._rows

    asyncio.run(_run())


def test_record_webhook_event_returns_duplicate_on_replay() -> None:
    async def _run() -> None:
        session = IdempotencyMemorySession()
        body = b'{"event":"message_created","id":1}'
        first = await record_webhook_event(session, event=_event(), raw_body=body)
        second = await record_webhook_event(session, event=_event(), raw_body=body)
        assert first.status == "received"
        assert second.status == "duplicate"
        assert len(session._rows) == 1

    asyncio.run(_run())


def test_record_webhook_event_rejects_missing_idempotency_key() -> None:
    async def _run() -> None:
        session = IdempotencyMemorySession()
        event = _event().model_copy(update={"idempotency_key": None})
        with pytest.raises(AppError, match="idempotency_key"):
            await record_webhook_event(session, event=event, raw_body=b"{}")

    asyncio.run(_run())


def test_webhook_service_returns_duplicate_status() -> None:
    async def _run() -> None:
        provider = MagicMock()
        provider.provider_name = "chatwoot"
        provider.verify_webhook = AsyncMock(return_value=True)
        provider.parse_webhook = AsyncMock(return_value=_event())

        session = IdempotencyMemorySession()
        service = WebhookService(provider, session, dispatcher=NoOpWebhookDispatcher())
        body = b'{"event":"message_created","id":1}'

        first = await service.receive_chatwoot(body, {})
        second = await service.receive_chatwoot(body, {})
        assert first.status == "accepted"
        assert second.status == "duplicate"

    asyncio.run(_run())


def test_record_webhook_event_integrity_error_with_scalar_lookup() -> None:
    async def _run() -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock(side_effect=IntegrityError("", {}, Exception()))
        session.rollback = AsyncMock()
        existing = MagicMock()
        existing.payload_hash = "abc"
        session.scalar = AsyncMock(return_value=existing)

        body = b"other-body"
        result = await record_webhook_event(session, event=_event(), raw_body=body)
        assert result.status == "duplicate"
        session.rollback.assert_awaited_once()

    asyncio.run(_run())
