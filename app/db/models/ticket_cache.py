"""Ticket cache ORM model — durable platform-agnostic ticket mirror."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.ai_conversation import AIConversation
    from app.db.models.user import User


class TicketCache(Base, TimestampMixin):
    """Local mirror of a ticketing-platform conversation for fast lookup and polling fallback."""

    __tablename__ = "ticket_cache"

    provider_ticket_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_contact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="ticket_caches")
    ai_conversation: Mapped[AIConversation | None] = relationship(
        back_populates="ticket_cache",
        uselist=False,
        cascade="all, delete-orphan",
    )
