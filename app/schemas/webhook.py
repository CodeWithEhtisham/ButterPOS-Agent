from pydantic import BaseModel
from typing import Optional


class WebhookPayload(BaseModel):
    """Raw webhook payload received from ticketing platform."""
    event_type: Optional[str] = None
    payload: dict = {}
    signature: Optional[str] = None
