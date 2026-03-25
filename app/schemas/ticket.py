from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TicketCreate(BaseModel):
    subject: str
    description: str
    user_id: int
    branch_id: Optional[int] = None
    priority: str = "medium"
    tags: list[str] = []
    metadata: dict = {}


class TicketResponse(BaseModel):
    id: int
    platform_ticket_id: str
    subject: Optional[str] = None
    status: str
    priority: Optional[str] = None
    ai_confidence: Optional[float] = None
    resolution_path: Optional[str] = None
    csat_score: Optional[int] = None
    reopen_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketStatusUpdate(BaseModel):
    status: str
