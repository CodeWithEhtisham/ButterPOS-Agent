"""Chat relay tests — Phase 2.1.3 human replies to widget sessions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.db.models.chat_session import ChatSession
from app.models.standard import StandardEvent, StandardEventType
from app.services.chat_relay_service import ChatRelayService, should_relay_outgoing_to_widget


def _event(**overrides: object) -> StandardEvent:
    base = {
        "event_type": StandardEventType.MESSAGE_CREATED,
        "provider_event_id": "200",
        "provider_ticket_id": "5678",
        "occurred_at": datetime.now(tz=UTC),
        "message_body": "Human agent here — checking your printer.",
        "message_direction": "outgoing",
        "sender_provider_contact_id": None,
        "raw_payload": {
            "message_type": "outgoing",
            "private": False,
            "sender": {"id": 5, "type": "user", "name": "Support Agent"},
        },
        "idempotency_key": "message_created:200",
    }
    base.update(overrides)
    return StandardEvent.model_validate(base)


def test_should_relay_outgoing_to_widget() -> None:
    assert should_relay_outgoing_to_widget(_event()) is True
    assert should_relay_outgoing_to_widget(_event(message_direction="incoming")) is False
    assert should_relay_outgoing_to_widget(_event(raw_payload={"private": True})) is False
    assert (
        should_relay_outgoing_to_widget(
            _event(
                raw_payload={
                    "message_type": "outgoing",
                    "private": False,
                    "sender": {"id": 99, "type": "contact", "name": "Customer"},
                },
            ),
        )
        is False
    )


def test_relay_stores_human_turn_on_linked_session() -> None:
    async def _run() -> None:
        db = AsyncMock()
        session = ChatSession(
            external_id="sess-1",
            jwt_subject="staff-1",
            source="test",
            status="escalated",
            provider_ticket_id="5678",
            messages_json=[
                {
                    "role": "user",
                    "content": "help",
                    "at": "2026-06-02T12:00:00Z",
                    "speaker": "customer",
                    "tool_calls": [],
                },
            ],
            meta={},
        )
        service = ChatRelayService()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.chat_relay_service.ChatSessionRepository.get_by_provider_ticket_id",
                AsyncMock(return_value=session),
            )
            append = AsyncMock()
            mp.setattr(
                "app.services.chat_relay_service.ChatSessionRepository.append_turns",
                append,
            )
            stored = await service.relay_outgoing_to_widget(db, _event())

        assert stored is True
        append.assert_awaited_once()
        turn = append.await_args.args[1][0]
        assert turn.speaker == "human"
        assert turn.content.startswith("Human agent here")

    asyncio.run(_run())


def test_relay_skips_middleware_echo_message_id() -> None:
    async def _run() -> None:
        session = ChatSession(
            external_id="sess-1",
            jwt_subject="staff-1",
            source="test",
            status="escalated",
            provider_ticket_id="5678",
            messages_json=[],
            meta={"middleware_message_ids": ["200"]},
        )
        service = ChatRelayService()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.chat_relay_service.ChatSessionRepository.get_by_provider_ticket_id",
                AsyncMock(return_value=session),
            )
            append = AsyncMock()
            mp.setattr(
                "app.services.chat_relay_service.ChatSessionRepository.append_turns",
                append,
            )
            stored = await service.relay_outgoing_to_widget(AsyncMock(), _event())

        assert stored is False
        append.assert_not_awaited()

    asyncio.run(_run())
