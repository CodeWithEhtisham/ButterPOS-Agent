"""
Standard models for platform-agnostic ticketing.

These are the ONLY ticketing models the middleware uses.
Adapters convert platform-specific data to/from these models.
"""

from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StandardStatus(str, Enum):
    """Platform-agnostic ticket statuses. Each adapter maps these to platform-specific values."""
    OPEN = "open"
    AI_WAITING = "ai_waiting"
    AI_PROCESSING = "ai_processing"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    PENDING_PAYMENT = "pending_payment"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CRITICAL = "critical"
    REOPENED = "reopened"


class StandardPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StandardEventType(str, Enum):
    """Types of events from ticketing platform webhooks."""
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    STATUS_CHANGED = "status_changed"
    COMMENT_ADDED = "comment_added"
    INTERNAL_NOTE_ADDED = "internal_note_added"
    AGENT_ASSIGNED = "agent_assigned"
    TICKET_CLOSED = "ticket_closed"
    TICKET_REOPENED = "ticket_reopened"


class TicketCreatePayload(BaseModel):
    """Data needed to create a ticket in any platform."""
    subject: str
    description: str
    contact_id: str
    priority: StandardPriority = StandardPriority.MEDIUM
    metadata: dict = {}
    tags: list[str] = []


class CommentPayload(BaseModel):
    """Data for adding a comment or note."""
    content: str
    author_type: str = "system"


class AssignPayload(BaseModel):
    """Data for assigning ticket to agent."""
    agent_id: str
    agent_name: Optional[str] = None
    escalation_level: int = 1


class TagPayload(BaseModel):
    """Data for adding tags."""
    tags: list[str]


class StandardContact(BaseModel):
    """Normalized contact/user data."""
    email: Optional[str] = None
    name: str
    phone: Optional[str] = None
    external_id: Optional[str] = None
    metadata: dict = {}


class StandardTicket(BaseModel):
    """Normalized ticket data returned by any adapter."""
    ticket_id: str
    subject: str
    description: str
    status: StandardStatus
    priority: StandardPriority
    contact_id: str
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    tags: list[str] = []
    metadata: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    comments: list["StandardComment"] = []


class StandardComment(BaseModel):
    """Normalized comment/note."""
    comment_id: str
    content: str
    author_name: str
    author_type: str
    is_internal: bool = False
    created_at: Optional[datetime] = None


class StandardEvent(BaseModel):
    """
    Normalized webhook event. ALL downstream webhook processing uses this.
    The middleware NEVER processes raw platform webhook payloads.
    """
    event_type: StandardEventType
    ticket_id: str
    timestamp: datetime
    data: dict = {}
    raw_event_id: Optional[str] = None
