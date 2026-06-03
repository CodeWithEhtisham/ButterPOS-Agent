"""Chat session ORM tests — Phase 2.1."""

from __future__ import annotations

from app.db.base import Base
from app.db.models import ChatSession
from sqlalchemy.dialects.postgresql import JSONB


def test_chat_session_table_columns() -> None:
    columns = ChatSession.__table__.columns
    assert columns["external_id"].unique
    assert columns["jwt_subject"].nullable is False
    assert isinstance(columns["messages_json"].type, JSONB)
    assert isinstance(columns["meta"].type, JSONB)


def test_chat_session_in_metadata() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert "chat_sessions" in names
