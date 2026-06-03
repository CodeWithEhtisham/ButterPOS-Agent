"""Inbound Chatwoot webhook → agent loop → public reply."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.db.models.ticket_cache import TicketCache
from app.models.standard import AddCommentRequest, StandardEvent, StandardEventType
from app.providers.ticketing.base import TicketingProvider
from app.repositories.ai_conversation_repository import AIConversationRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.ticket_cache_repository import get_or_fetch_ticket_cache
from app.schemas.chat_session import StoredChatTurn, StoredToolCall, turns_to_agent_history
from app.services.agent_service import AgentService
from app.services.escalation_service import EscalationService, should_auto_escalate

logger = get_logger("app.inbound_agent")

HUMAN_HANDOFF_TAGS = frozenset({"ai-escalated"})


def is_private_message(event: StandardEvent) -> bool:
    return bool(event.raw_payload.get("private"))


def resolve_branch_id(
    *,
    ticket_meta: dict[str, Any],
    event: StandardEvent,
    settings: Settings,
) -> str:
    conversation = event.raw_payload.get("conversation")
    conv_attrs: dict[str, Any] = {}
    if isinstance(conversation, dict):
        raw_attrs = conversation.get("custom_attributes")
        if isinstance(raw_attrs, dict):
            conv_attrs = raw_attrs

    for source in (ticket_meta, conv_attrs):
        branch = source.get("branch_id") or source.get("butterpos_branch_id")
        if branch:
            return str(branch)
    return settings.agent_default_branch_id


def should_run_inbound_agent(
    event: StandardEvent,
    ticket: TicketCache | None,
    *,
    enabled: bool,
) -> bool:
    """Decide whether this webhook should trigger the AI agent."""
    if not enabled:
        return False
    if event.event_type is not StandardEventType.MESSAGE_CREATED:
        return False
    if event.message_direction != "incoming":
        return False
    if not event.message_body or not event.message_body.strip():
        return False
    if is_private_message(event):
        return False
    if event.sender_provider_contact_id is None:
        return False
    if ticket is None:
        return True
    if ticket.status == "escalated":
        return False
    tags = {str(tag) for tag in (ticket.tags or [])}
    if tags & HUMAN_HANDOFF_TAGS:
        return False
    if ticket.assignee_id:
        return False
    return True


class InboundAgentService:
    """Run the support agent for Chatwoot-originated customer messages."""

    def __init__(
        self,
        settings: Settings,
        agent: AgentService,
        ticketing: TicketingProvider,
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._ticketing = ticketing
        self._escalation = EscalationService(settings, ticketing)

    async def handle_event(self, db: AsyncSession, event: StandardEvent) -> bool:
        """Process one inbound customer message. Returns True when agent ran."""
        if event.event_type is not StandardEventType.MESSAGE_CREATED:
            return False

        ticket_cache = await get_or_fetch_ticket_cache(
            db,
            self._ticketing,
            event.provider_ticket_id,
        )
        if not should_run_inbound_agent(
            event,
            ticket_cache,
            enabled=self._settings.agent_inbound_enabled,
        ):
            return False

        assert event.message_body is not None
        ai_repo = AIConversationRepository(db)
        conversation = await ai_repo.get_or_create(
            ticket_cache_id=ticket_cache.id,
            user_id=ticket_cache.user_id,
        )

        if conversation.messages_json:
            history = turns_to_agent_history(
                [StoredChatTurn.model_validate(m) for m in conversation.messages_json],
            )
        else:
            history = []

        branch_id = resolve_branch_id(
            ticket_meta=dict(ticket_cache.meta or {}),
            event=event,
            settings=self._settings,
        )

        agent_result = await self._agent.run_chat(
            event.message_body,
            history=history,
            branch_id=branch_id,
        )

        tool_records = [
            StoredToolCall(
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                result=tc.result,
                success=tc.success,
            )
            for tc in agent_result.tool_calls
        ]

        await ai_repo.append_turns(
            conversation,
            [
                StoredChatTurn(
                    role="user",
                    content=event.message_body,
                    at=event.occurred_at or datetime.now(tz=UTC),
                ),
                StoredChatTurn(
                    role="assistant",
                    content=agent_result.reply or agent_result.error or "",
                    at=datetime.now(tz=UTC),
                    tool_calls=tool_records,
                ),
            ],
        )

        wants_handoff = should_auto_escalate(
            event.message_body,
            agent_error=agent_result.error,
        )

        if wants_handoff:
            reason = (
                f"agent_error:{agent_result.error[:120]}"
                if agent_result.error
                else "customer_requested_human"
            )
            await self._escalation.handoff_existing_ticket(
                db,
                provider_ticket_id=event.provider_ticket_id,
                messages_json=conversation.messages_json or [],
                reason=reason,
                customer_reply=agent_result.reply if agent_result.reply else None,
            )
            ticket_cache.status = "escalated"
            ticket_cache.tags = list(set((ticket_cache.tags or []) + ["ai-escalated"]))
            await db.flush()
            logger.info(
                "inbound_agent_handoff ticket_id=%s reason=%s",
                event.provider_ticket_id,
                reason,
                extra={"ticket_id": event.provider_ticket_id},
            )
            return True

        if agent_result.error and not agent_result.reply:
            raise RuntimeError(agent_result.error)

        reply = agent_result.reply.strip()
        if reply:
            msg_id = await self._ticketing.add_comment(
                AddCommentRequest(
                    provider_ticket_id=event.provider_ticket_id,
                    body=reply,
                ),
            )
            if msg_id:
                chat_session = await ChatSessionRepository(db).get_by_provider_ticket_id(
                    event.provider_ticket_id,
                )
                if chat_session is not None:
                    await ChatSessionRepository(db).record_middleware_message_id(
                        chat_session,
                        msg_id,
                    )

        logger.info(
            "inbound_agent_replied ticket_id=%s tool_calls=%s",
            event.provider_ticket_id,
            len(agent_result.tool_calls),
            extra={"ticket_id": event.provider_ticket_id},
        )
        return True
