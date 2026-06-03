"""Escalate AI chat sessions to Chatwoot with full transcript."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.db.models.chat_session import ChatSession
from app.models.standard import (
    AddCommentRequest,
    AddNoteRequest,
    AddTagsRequest,
    AssignAgentRequest,
    CreateContactRequest,
    CreateTicketRequest,
    StandardStatus,
    UpdateStatusRequest,
)
from app.providers.ticketing.base import TicketingProvider
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.ticket_cache_repository import upsert_ticket_cache
from app.schemas.chat_session import StoredChatTurn, StoredToolCall
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.escalation")

_ESCALATION_KEYWORDS = (
    "human agent",
    "speak to human",
    "real person",
    "talk to agent",
    "escalate",
    "support agent",
)


def should_auto_escalate(user_message: str, *, agent_error: str | None) -> bool:
    """Heuristic until KB/tier routing lands in a later Phase 2 step."""
    if agent_error:
        return True
    lowered = user_message.lower()
    return any(keyword in lowered for keyword in _ESCALATION_KEYWORDS)


def format_transcript_note(
    *,
    reason: str,
    messages_json: list[object],
    header_lines: list[str] | None = None,
) -> str:
    """Private Chatwoot note — full transcript for human agents."""
    lines = ["=== ButterPOS AI escalation ===", f"Reason: {reason}"]
    if header_lines:
        lines.extend(header_lines)
    lines.extend(["", "--- Transcript ---"])
    for raw in messages_json or []:
        turn = StoredChatTurn.model_validate(raw)
        prefix = "Customer" if turn.role == "user" else "AI Agent"
        lines.append(f"[{prefix}]: {turn.content}")
        for tc in turn.tool_calls:
            tool = StoredToolCall.model_validate(tc) if isinstance(tc, dict) else tc
            mark = "ok" if tool.success else "fail"
            lines.append(f"  MCP {mark}: {tool.tool_name}({tool.arguments})")
            if tool.result:
                lines.append(f"    → {tool.result[:500]}")
    lines.append("--- End transcript ---")
    return "\n".join(lines)


def format_escalation_note(session: ChatSession, *, reason: str) -> str:
    """Private Chatwoot note — full transcript for human agents."""
    return format_transcript_note(
        reason=reason,
        messages_json=session.messages_json or [],
        header_lines=[
            f"Source: {session.source}",
            f"Branch: {session.branch_id or 'n/a'}",
            f"User subject: {session.jwt_subject}",
            f"Session: {session.external_id}",
        ],
    )


@dataclass(frozen=True)
class EscalationResult:
    provider_ticket_id: str
    provider_contact_id: str


class EscalationService:
    def __init__(self, settings: Settings, ticketing: TicketingProvider) -> None:
        self._settings = settings
        self._ticketing = ticketing

    async def escalate_to_chatwoot(
        self,
        db: AsyncSession,
        session: ChatSession,
        *,
        reason: str,
        customer_reply: str | None = None,
    ) -> EscalationResult:
        """Create Chatwoot conversation, sync transcript, return platform ids."""
        if session.provider_ticket_id:
            ticket_id = session.provider_ticket_id
            contact_id = session.provider_contact_id or ""
            await self._ticketing.add_note(
                AddNoteRequest(
                    provider_ticket_id=ticket_id,
                    body=format_escalation_note(session, reason=reason),
                ),
            )
            return EscalationResult(provider_ticket_id=ticket_id, provider_contact_id=contact_id)

        contact = await self._ticketing.get_or_create_contact(
            CreateContactRequest(
                name=session.jwt_subject,
                external_user_id=session.jwt_subject,
                metadata={
                    "custom_attributes": {
                        "chat_source": session.source,
                        "branch_id": session.branch_id or "",
                    },
                },
            ),
        )

        last_user = _last_user_message(session)
        subject = f"[{session.source}] {last_user[:80]}" if last_user else f"[{session.source}] AI escalation"

        ticket = await self._ticketing.create_ticket(
            CreateTicketRequest(
                provider_contact_id=contact.provider_contact_id,
                subject=subject,
                initial_message=last_user or "Customer requested human support.",
                tags=["ai-escalated", f"source-{session.source}"],
                metadata={
                    "custom_attributes": {
                        "chat_session_id": session.external_id,
                        "chat_source": session.source,
                        "branch_id": session.branch_id or "",
                    },
                },
            ),
        )
        ticket_id = ticket.provider_ticket_id

        await self._ticketing.add_note(
            AddNoteRequest(
                provider_ticket_id=ticket_id,
                body=format_escalation_note(session, reason=reason),
            ),
        )

        public_reply = customer_reply or (
            "I've escalated this to our support team. A human agent will follow up shortly."
        )
        msg_id = await self._ticketing.add_comment(
            AddCommentRequest(provider_ticket_id=ticket_id, body=public_reply),
        )
        if msg_id:
            await ChatSessionRepository(db).record_middleware_message_id(session, msg_id)

        await self._ticketing.update_status(
            UpdateStatusRequest(
                provider_ticket_id=ticket_id,
                status=StandardStatus.ESCALATED,
            ),
        )

        tags = ["ai-escalated", f"source-{session.source}"]
        await self._ticketing.add_tags(AddTagsRequest(provider_ticket_id=ticket_id, tags=tags))

        agent_id = self._settings.chatwoot_agent_id.strip()
        if agent_id:
            await self._ticketing.assign_agent(
                AssignAgentRequest(provider_ticket_id=ticket_id, assignee_id=agent_id),
            )

        await upsert_ticket_cache(db, ticket)

        logger.info(
            "chat_escalated session=%s ticket_id=%s source=%s",
            session.external_id,
            ticket_id,
            session.source,
            extra={"ticket_id": ticket_id},
        )
        return EscalationResult(
            provider_ticket_id=ticket_id,
            provider_contact_id=contact.provider_contact_id,
        )

    async def handoff_existing_ticket(
        self,
        db: AsyncSession,
        *,
        provider_ticket_id: str,
        messages_json: list[object],
        reason: str,
        customer_reply: str | None = None,
        source_tag: str = "chatwoot-inbound",
    ) -> None:
        """Escalate an existing Chatwoot conversation to a human agent."""
        note = format_transcript_note(
            reason=reason,
            messages_json=messages_json,
            header_lines=[f"Ticket: {provider_ticket_id}", f"Source: {source_tag}"],
        )
        await self._ticketing.add_note(
            AddNoteRequest(provider_ticket_id=provider_ticket_id, body=note),
        )

        public_reply = customer_reply or (
            "I've escalated this to our support team. A human agent will follow up shortly."
        )
        msg_id = await self._ticketing.add_comment(
            AddCommentRequest(provider_ticket_id=provider_ticket_id, body=public_reply),
        )
        chat_session = await ChatSessionRepository(db).get_by_provider_ticket_id(provider_ticket_id)
        if msg_id and chat_session is not None:
            await ChatSessionRepository(db).record_middleware_message_id(chat_session, msg_id)
        await self._ticketing.update_status(
            UpdateStatusRequest(
                provider_ticket_id=provider_ticket_id,
                status=StandardStatus.ESCALATED,
            ),
        )
        await self._ticketing.add_tags(
            AddTagsRequest(
                provider_ticket_id=provider_ticket_id,
                tags=["ai-escalated", source_tag],
            ),
        )

        agent_id = self._settings.chatwoot_agent_id.strip()
        if agent_id:
            await self._ticketing.assign_agent(
                AssignAgentRequest(provider_ticket_id=provider_ticket_id, assignee_id=agent_id),
            )

        ticket = await self._ticketing.get_ticket(provider_ticket_id)
        await upsert_ticket_cache(db, ticket)

        logger.info(
            "inbound_handoff ticket_id=%s reason=%s",
            provider_ticket_id,
            reason,
            extra={"ticket_id": provider_ticket_id},
        )


def _last_user_message(session: ChatSession) -> str:
    for raw in reversed(session.messages_json or []):
        turn = StoredChatTurn.model_validate(raw)
        if turn.role == "user":
            return turn.content
    return ""
