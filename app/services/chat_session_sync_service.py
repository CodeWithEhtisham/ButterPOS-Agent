"""Sync escalated widget sessions from Chatwoot when webhooks are unavailable (local dev)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.db.models.chat_session import ChatSession
from app.providers.ticketing.base import TicketingProvider
from app.providers.ticketing.caching_adapter import CachingTicketingProvider
from app.providers.ticketing.chatwoot.conversations import (
    list_conversation_messages,
    parse_conversation_id,
)
from app.providers.ticketing.chatwoot_adapter import ChatwootAdapter
from app.providers.ticketing.deduping_adapter import DedupingTicketingProvider
from app.repositories.chat_session_repository import ChatSessionRepository
from app.schemas.chat_session import StoredChatTurn
from app.services.chat_relay_service import should_relay_outgoing_to_widget
from app.models.standard import StandardEvent, StandardEventType
from app.providers.ticketing.chatwoot.mappers import parse_chatwoot_timestamp

logger = get_logger("app.chat_sync")


def _unwrap_chatwoot(provider: TicketingProvider) -> ChatwootAdapter | None:
    current: TicketingProvider = provider
    while True:
        if isinstance(current, ChatwootAdapter):
            return current
        if isinstance(current, CachingTicketingProvider):
            current = current.inner
            continue
        if isinstance(current, DedupingTicketingProvider):
            current = current.inner
            continue
        return None


def _is_outgoing_message(msg: dict[str, Any]) -> bool:
    message_type = msg.get("message_type")
    if message_type in {"outgoing", 1, "1"}:
        return True
    return message_type == "outgoing"


def _message_to_event(msg: dict[str, Any], *, provider_ticket_id: str) -> StandardEvent | None:
    content = msg.get("content")
    if content is None or not str(content).strip():
        return None
    message_id = msg.get("id")
    if message_id is None:
        return None

    sender = msg.get("sender") if isinstance(msg.get("sender"), dict) else {}
    sender_type = sender.get("type")
    sender_id = sender.get("id")

    occurred = parse_chatwoot_timestamp(msg.get("created_at")) or datetime.now(tz=UTC)

    return StandardEvent(
        event_type=StandardEventType.MESSAGE_CREATED,
        provider_event_id=str(message_id),
        provider_ticket_id=provider_ticket_id,
        occurred_at=occurred,
        message_body=str(content),
        message_direction="outgoing",
        sender_provider_contact_id=str(sender_id) if sender_type == "contact" and sender_id else None,
        raw_payload={
            "message_type": "outgoing",
            "private": bool(msg.get("private")),
            "sender": sender,
        },
        idempotency_key=f"message_created:{message_id}",
    )


class ChatSessionSyncService:
    """Pull new human agent messages from Chatwoot into ``chat_sessions``."""

    def __init__(self, settings: Settings, ticketing: TicketingProvider) -> None:
        self._settings = settings
        self._ticketing = ticketing

    async def sync_human_replies_from_chatwoot(
        self,
        db: object,
        chat_session: ChatSession,
    ) -> int:
        """Fetch Chatwoot messages and append unseen human replies. Returns count added."""
        if chat_session.status != "escalated" or not chat_session.provider_ticket_id:
            return 0

        adapter = _unwrap_chatwoot(self._ticketing)
        if adapter is None:
            return 0

        conversation_id = parse_conversation_id(chat_session.provider_ticket_id)
        messages = await list_conversation_messages(adapter._client, conversation_id)
        repo = ChatSessionRepository(db)  # type: ignore[arg-type]
        known_ids = repo.known_provider_event_ids(chat_session)
        added = 0

        for msg in messages:
            if not _is_outgoing_message(msg) or msg.get("private"):
                continue
            event = _message_to_event(msg, provider_ticket_id=chat_session.provider_ticket_id)
            if event is None or not should_relay_outgoing_to_widget(event):
                continue
            if event.provider_event_id in known_ids:
                continue

            await repo.append_turns(
                chat_session,
                [
                    StoredChatTurn(
                        role="assistant",
                        content=event.message_body or "",
                        at=event.occurred_at,
                        speaker="human",
                        provider_event_id=event.provider_event_id,
                    ),
                ],
            )
            known_ids.add(event.provider_event_id)
            added += 1
            logger.info(
                "human_reply_synced_from_chatwoot session=%s ticket_id=%s event_id=%s",
                chat_session.external_id,
                chat_session.provider_ticket_id,
                event.provider_event_id,
            )

        return added
