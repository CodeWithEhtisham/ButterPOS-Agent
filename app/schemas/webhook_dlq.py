"""Webhook DLQ payload schema — serialized to Redis for Celery retries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebhookDlqPayload(BaseModel):
    """Entry stored in Redis sorted set until next retry window."""

    idempotency_key: str
    attempt_count: int = Field(ge=1, description="Next processing attempt number")
    error_message: str = ""
    event: dict[str, Any]
    next_retry_at: float
