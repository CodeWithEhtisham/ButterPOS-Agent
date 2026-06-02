"""SLA configuration ORM model — escalation rules per support plan type."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SLAConfig(Base, TimestampMixin):
    """Support SLA targets keyed by restaurant plan_type (8h / 16h / 24-7)."""

    __tablename__ = "sla_config"

    plan_type: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    coverage_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
