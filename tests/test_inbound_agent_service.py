"""Inbound webhook agent loop tests — Phase 2.1.2."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.db.models.ai_conversation import AIConversation
from app.db.models.ticket_cache import TicketCache
from app.models.standard import StandardEvent, StandardEventType
from app.services.agent_service import AgentRunResult, AgentToolCallRecord
from app.services.inbound_agent_service import (
    InboundAgentService,
    is_private_message,
    resolve_branch_id,
    should_run_inbound_agent,
)


def _event(**overrides: object) -> StandardEvent:
    base = {
        "event_type": StandardEventType.MESSAGE_CREATED,
        "provider_event_id": "99",
        "provider_ticket_id": "5678",
        "occurred_at": datetime.now(tz=UTC),
        "message_body": "Printer offline hai",
        "message_direction": "incoming",
        "sender_provider_contact_id": "101",
        "raw_payload": {"message_type": "incoming", "private": False},
        "idempotency_key": "message_created:99",
    }
    base.update(overrides)
    return StandardEvent.model_validate(base)


def _ticket(**overrides: object) -> TicketCache:
    row = TicketCache(
        provider_ticket_id="5678",
        status="open",
        tags=[],
        meta={"branch_id": "branch-a"},
    )
    row.id = 1
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def test_should_run_inbound_agent_skips_outgoing() -> None:
    event = _event(message_direction="outgoing")
    assert should_run_inbound_agent(event, _ticket(), enabled=True) is False


def test_should_run_inbound_agent_skips_private() -> None:
    event = _event(raw_payload={"private": True, "message_type": "incoming"})
    assert is_private_message(event) is True
    assert should_run_inbound_agent(event, _ticket(), enabled=True) is False


def test_should_run_inbound_agent_skips_ai_escalated_tag() -> None:
    event = _event()
    ticket = _ticket(tags=["ai-escalated"])
    assert should_run_inbound_agent(event, ticket, enabled=True) is False


def test_should_run_inbound_agent_skips_when_disabled() -> None:
    assert should_run_inbound_agent(_event(), _ticket(), enabled=False) is False


def test_resolve_branch_id_prefers_ticket_meta() -> None:
    settings = Settings(_env_file=None, agent_default_branch_id="default-branch")
    event = _event(
        raw_payload={
            "conversation": {"custom_attributes": {"branch_id": "conv-branch"}},
        },
    )
    branch = resolve_branch_id(
        ticket_meta={"branch_id": "ticket-branch"},
        event=event,
        settings=settings,
    )
    assert branch == "ticket-branch"


def test_inbound_agent_replies_via_chatwoot() -> None:
    async def _run() -> None:
        settings = Settings(_env_file=None, agent_inbound_enabled=True)
        agent = AsyncMock()
        agent.run_chat = AsyncMock(
            return_value=AgentRunResult(
                reply="Try restarting the printer.",
                model="openai/gpt-4o-mini",
                tool_calls=[
                    AgentToolCallRecord(
                        tool_name="check_printer",
                        arguments={"branch_id": "branch-a"},
                        result="offline",
                        success=True,
                    ),
                ],
            ),
        )
        ticketing = AsyncMock()
        ticketing.get_ticket = AsyncMock(
            return_value=MagicMock(
                provider_ticket_id="5678",
                status=MagicMock(value="open"),
                subject="Printer",
                provider_contact_id="101",
                assignee_id=None,
                tags=[],
                metadata={"branch_id": "branch-a"},
            ),
        )

        db = AsyncMock()
        ticket = _ticket()
        conversation = AIConversation(ticket_cache_id=1, messages_json=[], confidence_history=[])
        conversation.id = 10

        service = InboundAgentService(settings, agent, ticketing)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.inbound_agent_service.get_or_fetch_ticket_cache",
                AsyncMock(return_value=ticket),
            )
            mp.setattr(
                "app.repositories.ai_conversation_repository.AIConversationRepository.get_or_create",
                AsyncMock(return_value=conversation),
            )
            mp.setattr(
                "app.repositories.ai_conversation_repository.AIConversationRepository.append_turns",
                AsyncMock(),
            )
            mp.setattr(
                "app.repositories.chat_session_repository.ChatSessionRepository.get_by_provider_ticket_id",
                AsyncMock(return_value=None),
            )

            ran = await service.handle_event(db, _event())

        assert ran is True
        agent.run_chat.assert_awaited_once()
        ticketing.add_comment.assert_awaited_once()
        body = ticketing.add_comment.await_args.args[0].body
        assert "Try restarting the printer." in body

    asyncio.run(_run())


def test_inbound_agent_handoff_on_human_keyword() -> None:
    async def _run() -> None:
        settings = Settings(_env_file=None, agent_inbound_enabled=True)
        agent = AsyncMock()
        agent.run_chat = AsyncMock(
            return_value=AgentRunResult(
                reply="Connecting you with support.",
                model="openai/gpt-4o-mini",
            ),
        )
        ticketing = AsyncMock()
        service = InboundAgentService(settings, agent, ticketing)
        ticket = _ticket()
        conversation = AIConversation(ticket_cache_id=1, messages_json=[], confidence_history=[])
        conversation.id = 10

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.inbound_agent_service.get_or_fetch_ticket_cache",
                AsyncMock(return_value=ticket),
            )
            mp.setattr(
                "app.repositories.ai_conversation_repository.AIConversationRepository.get_or_create",
                AsyncMock(return_value=conversation),
            )
            mp.setattr(
                "app.repositories.ai_conversation_repository.AIConversationRepository.append_turns",
                AsyncMock(),
            )
            service._escalation.handoff_existing_ticket = AsyncMock()

            event = _event(message_body="I need a human agent please")
            ran = await service.handle_event(db := AsyncMock(), event)

        assert ran is True
        service._escalation.handoff_existing_ticket.assert_awaited_once()
        ticketing.add_comment.assert_not_awaited()

    asyncio.run(_run())
