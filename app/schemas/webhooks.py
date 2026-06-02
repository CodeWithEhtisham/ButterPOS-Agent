"""Webhook API response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.models.standard import StandardEventType

WebhookResponseStatus = Literal["accepted", "duplicate", "rate_limited"]


class WebhookAcceptedResponse(BaseModel):
    """Acknowledgement after verify, parse, and idempotency gate."""

    status: WebhookResponseStatus
    event_type: StandardEventType
    provider_event_id: str
    provider_ticket_id: str
    idempotency_key: str
