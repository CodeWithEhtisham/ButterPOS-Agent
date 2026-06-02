"""Branch ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.restaurant import Restaurant
    from app.db.models.user import User


class Branch(Base, TimestampMixin):
    """Physical location under a restaurant — timezone drives SLA and hours logic."""

    __tablename__ = "branches"

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    butterpos_branch_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Karachi")
    devices: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    restaurant: Mapped[Restaurant] = relationship(back_populates="branches")
    users: Mapped[list[User]] = relationship(back_populates="branch", cascade="all, delete-orphan")
