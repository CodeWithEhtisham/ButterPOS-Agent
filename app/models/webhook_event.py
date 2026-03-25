from sqlalchemy import Column, Integer, String, Text, DateTime

from .base import Base, TimestampMixin


class WebhookEvent(Base, TimestampMixin):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    platform_ticket_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    payload_hash = Column(String(64), nullable=False)  # SHA-256
    status = Column(String(20), nullable=False, default="processed")  # processed, failed, retrying, dead
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
