"""Webhook event log ORM model — idempotency and inbound audit trail."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WebhookEventLog(Base, TimestampMixin):
    """Durable record of every inbound webhook — dedupe via unique idempotency_key."""

    __tablename__ = "webhook_event_log"

    idempotency_key: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_ticket_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received", server_default="received")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
