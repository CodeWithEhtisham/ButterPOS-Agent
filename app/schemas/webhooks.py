"""Webhook API response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.models.standard import StandardEventType


class WebhookAcceptedResponse(BaseModel):
    """Acknowledgement after verify + parse — processing is deferred to later steps."""

    status: Literal["accepted"] = "accepted"
    event_type: StandardEventType
    provider_event_id: str
    provider_ticket_id: str
    idempotency_key: str | None = None
