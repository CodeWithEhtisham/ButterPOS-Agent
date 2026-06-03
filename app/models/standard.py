"""Platform-agnostic ticketing domain models (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class StandardStatus(str, Enum):
    """12-value ticket lifecycle — adapters map platform statuses to/from this enum."""

    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    WAITING_ON_INTERNAL = "waiting_on_internal"
    ESCALATED = "escalated"
    SNOOZED = "snoozed"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class StandardEventType(str, Enum):
    """Normalized webhook event types across ticketing platforms."""

    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    CONVERSATION_STATUS_CHANGED = "conversation_status_changed"
    CONVERSATION_UPDATED = "conversation_updated"
    WEBWIDGET_TRIGGERED = "webwidget_triggered"
    UNKNOWN = "unknown"


MessageDirection = Literal["incoming", "outgoing"]


class StandardContact(BaseModel):
    """Platform-agnostic contact (Chatwoot contact, Zoho contact, etc.)."""

    provider_contact_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StandardTicket(BaseModel):
    """Platform-agnostic ticket/conversation mirror."""

    provider_ticket_id: str
    status: StandardStatus
    subject: str | None = None
    provider_contact_id: str | None = None
    assignee_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StandardEvent(BaseModel):
    """Normalized inbound webhook event for middleware processing."""

    event_type: StandardEventType
    provider_event_id: str
    provider_ticket_id: str
    occurred_at: datetime
    message_body: str | None = None
    message_direction: MessageDirection | None = None
    sender_provider_contact_id: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class CreateTicketRequest(BaseModel):
    """Input for opening a new ticket/conversation."""

    provider_contact_id: str
    subject: str | None = None
    initial_message: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateContactRequest(BaseModel):
    """Input for contact lookup/creation."""

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    external_user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddCommentRequest(BaseModel):
    """Public reply visible to the customer."""

    provider_ticket_id: str
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddCustomerMessageRequest(BaseModel):
    """Customer message on an existing ticket (API channel — widget after escalation)."""

    provider_ticket_id: str
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddNoteRequest(BaseModel):
    """Internal note — not visible to the customer."""

    provider_ticket_id: str
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateStatusRequest(BaseModel):
    provider_ticket_id: str
    status: StandardStatus


class AssignAgentRequest(BaseModel):
    provider_ticket_id: str
    assignee_id: str


class AddTagsRequest(BaseModel):
    provider_ticket_id: str
    tags: list[str] = Field(min_length=1)


class ProviderHealth(BaseModel):
    """Result of adapter health_check."""

    healthy: bool
    provider: str
    message: str | None = None
    latency_ms: float | None = None
