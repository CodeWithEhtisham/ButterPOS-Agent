"""AI conversation ORM model — agent memory separate from ticketing platform."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.ticket_cache import TicketCache
    from app.db.models.user import User


class AIConversation(Base, TimestampMixin):
    """Per-ticket AI state: LLM message history and confidence audit trail."""

    __tablename__ = "ai_conversations"

    ticket_cache_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_cache.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    messages_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    confidence_history: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    ticket_cache: Mapped[TicketCache] = relationship(back_populates="ai_conversation")
    user: Mapped[User | None] = relationship(back_populates="ai_conversations")
