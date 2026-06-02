"""Ticket cache + AI conversation ORM tests — Task 1.2 sub-step 3."""

from __future__ import annotations

from app.db.base import Base
from app.db.models import AIConversation, TicketCache, User
from sqlalchemy.dialects.postgresql import JSONB


def test_ticket_cache_table_columns() -> None:
    columns = TicketCache.__table__.columns
    assert columns["provider_ticket_id"].unique
    assert columns["status"].nullable is False
    assert isinstance(columns["tags"].type, JSONB)
    assert isinstance(columns["meta"].type, JSONB)
    assert columns["synced_at"].nullable is True
    assert columns["user_id"].foreign_keys


def test_ai_conversation_table_columns() -> None:
    columns = AIConversation.__table__.columns
    assert columns["ticket_cache_id"].unique
    assert isinstance(columns["messages_json"].type, JSONB)
    assert isinstance(columns["confidence_history"].type, JSONB)
    assert columns["ticket_cache_id"].foreign_keys
    assert columns["user_id"].foreign_keys


def test_ticket_cache_ai_conversation_relationships() -> None:
    assert TicketCache.ai_conversation.property.mapper.class_ is AIConversation
    assert AIConversation.ticket_cache.property.mapper.class_ is TicketCache
    assert User.ticket_caches.property.mapper.class_ is TicketCache
    assert User.ai_conversations.property.mapper.class_ is AIConversation


def test_ticket_models_in_metadata() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert {"ticket_cache", "ai_conversations"}.issubset(names)
