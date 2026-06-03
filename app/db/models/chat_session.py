"""Chat session ORM — middleware AI chat history (Android / HQ widgets)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    """Durable AI chat session; links to Chatwoot after escalation."""

    __tablename__ = "chat_sessions"

    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    jwt_subject: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="test")
    branch_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    provider_ticket_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    provider_contact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    messages_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
