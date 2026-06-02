"""Restaurant ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.branch import Branch


class Restaurant(Base, TimestampMixin):
    """ButterPOS tenant — plan and billing state drive agent authorization (Task 1.6)."""

    __tablename__ = "restaurants"

    butterpos_restaurant_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_due: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branches: Mapped[list[Branch]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )
