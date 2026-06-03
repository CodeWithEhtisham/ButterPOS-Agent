"""Relay Chatwoot human-agent replies to escalated widget chat sessions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.standard import StandardEvent, StandardEventType
from app.repositories.chat_session_repository import ChatSessionRepository
from app.schemas.chat_session import StoredChatTurn
from app.services.inbound_agent_service import is_private_message

logger = get_logger("app.chat_relay")


def should_relay_outgoing_to_widget(event: StandardEvent) -> bool:
    """True when webhook is a public outgoing agent message worth relaying."""
    if event.event_type is not StandardEventType.MESSAGE_CREATED:
        return False
    if event.message_direction != "outgoing":
        return False
    if is_private_message(event):
        return False
    if not event.message_body or not event.message_body.strip():
        return False
    sender = event.raw_payload.get("sender")
    if isinstance(sender, dict) and sender.get("type") == "contact":
        return False
    return True


class ChatRelayService:
    """Append human Chatwoot replies to linked ``chat_sessions`` for widget polling."""

    async def relay_outgoing_to_widget(self, db: AsyncSession, event: StandardEvent) -> bool:
        """Store human agent reply on the widget session, if linked. Returns True when stored."""
        if not should_relay_outgoing_to_widget(event):
            return False

        repo = ChatSessionRepository(db)
        chat_session = await repo.get_by_provider_ticket_id(event.provider_ticket_id)
        if chat_session is None:
            return False

        known_ids = repo.known_provider_event_ids(chat_session)
        event_id = event.provider_event_id
        if event_id in known_ids:
            return False

        assert event.message_body is not None
        await repo.append_turns(
            chat_session,
            [
                StoredChatTurn(
                    role="assistant",
                    content=event.message_body,
                    at=event.occurred_at,
                    speaker="human",
                    provider_event_id=event_id,
                ),
            ],
        )
        logger.info(
            "human_reply_relayed session=%s ticket_id=%s event_id=%s",
            chat_session.external_id,
            event.provider_ticket_id,
            event_id,
            extra={"ticket_id": event.provider_ticket_id},
        )
        return True
