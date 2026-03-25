from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    message: str
    ticket_id: Optional[str] = None
    user_id: int
    branch_id: Optional[int] = None
    language: str = "en"  # en, ur, mixed
    metadata: dict = {}


class ChatMessageResponse(BaseModel):
    response: str
    ticket_id: str
    confidence: float
    resolution_path: str  # A, B, C
    suggested_actions: list[str] = []
    escalated: bool = False
    timestamp: datetime
