"""TicketingProvider abstract interface — 12 methods (Task 1.1.4 + 1.4.4).

All platform-specific logic lives in adapters (e.g. ChatwootAdapter in Task 1.3).
The middleware core imports this module only, never a platform SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.models.standard import (
    AddCommentRequest,
    AddNoteRequest,
    AddTagsRequest,
    AssignAgentRequest,
    CreateContactRequest,
    CreateTicketRequest,
    ProviderHealth,
    StandardContact,
    StandardEvent,
    StandardTicket,
    UpdateStatusRequest,
)


class TicketingProvider(ABC):
    """Platform-agnostic ticketing operations."""

    provider_name: str

    @abstractmethod
    async def create_ticket(self, request: CreateTicketRequest) -> StandardTicket:
        """Open a new ticket/conversation for a contact."""

    @abstractmethod
    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket:
        """Fetch a ticket by platform-native id."""

    @abstractmethod
    async def update_status(self, request: UpdateStatusRequest) -> StandardTicket:
        """Transition ticket to a StandardStatus value."""

    @abstractmethod
    async def add_comment(self, request: AddCommentRequest) -> None:
        """Post a public reply visible to the customer."""

    @abstractmethod
    async def add_note(self, request: AddNoteRequest) -> None:
        """Post an internal note (agent-only)."""

    @abstractmethod
    async def assign_agent(self, request: AssignAgentRequest) -> StandardTicket:
        """Assign ticket to a platform agent/user id."""

    @abstractmethod
    async def add_tags(self, request: AddTagsRequest) -> StandardTicket:
        """Append classification tags to a ticket."""

    @abstractmethod
    async def get_or_create_contact(self, request: CreateContactRequest) -> StandardContact:
        """Resolve contact by identifiers; create if absent."""

    @abstractmethod
    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """Validate inbound webhook authenticity (e.g. Chatwoot HMAC)."""

    @abstractmethod
    async def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        """Map platform webhook payload to StandardEvent."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Probe platform API reachability and credentials."""

    @abstractmethod
    async def list_tickets_updated_since(self, since: datetime) -> list[StandardTicket]:
        """List tickets/conversations updated after `since` — polling fallback (Task 1.4.4)."""
