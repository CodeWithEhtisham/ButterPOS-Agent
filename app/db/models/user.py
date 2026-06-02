"""User ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.ai_conversation import AIConversation
    from app.db.models.branch import Branch
    from app.db.models.ticket_cache import TicketCache


class User(Base, TimestampMixin):
    """Staff/tablet user — maps to ticketing contact via provider_contact_id."""

    __tablename__ = "users"

    butterpos_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider_contact_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    language_pref: Mapped[str] = mapped_column(String(16), nullable=False, default="en")

    branch: Mapped[Branch | None] = relationship(back_populates="users")
    ticket_caches: Mapped[list[TicketCache]] = relationship(back_populates="user")
    ai_conversations: Mapped[list[AIConversation]] = relationship(back_populates="user")
