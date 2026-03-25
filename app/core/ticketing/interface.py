"""
TicketingProvider — Abstract interface for ticketing platforms.

Rules:
1. Middleware NEVER imports platform-specific code (zoho, freshdesk, etc.)
2. Middleware ONLY uses TicketingProvider, StandardTicket, StandardEvent, StandardStatus
3. All platform-specific logic lives INSIDE the adapter
4. Switching platforms = new adapter + change TICKETING_PROVIDER env var
"""

from abc import ABC, abstractmethod

from .models import (
    StandardTicket,
    StandardEvent,
    StandardComment,
    StandardContact,
    StandardStatus,
    TicketCreatePayload,
    CommentPayload,
    AssignPayload,
    TagPayload,
)


class TicketingProvider(ABC):
    """Abstract base class for all ticketing platform adapters."""

    # ── Ticket Operations ──

    @abstractmethod
    async def create_ticket(self, payload: TicketCreatePayload) -> StandardTicket:
        """Create a new ticket. Returns standardized ticket with platform ticket_id."""
        ...

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> StandardTicket:
        """Fetch ticket details by platform ticket ID. Returns standardized ticket."""
        ...

    @abstractmethod
    async def update_status(self, ticket_id: str, status: StandardStatus) -> bool:
        """Update ticket status. Adapter maps StandardStatus → platform-specific status."""
        ...

    # ── Comments ──

    @abstractmethod
    async def add_public_comment(self, ticket_id: str, payload: CommentPayload) -> str:
        """Add a customer-visible comment (AI response). Returns comment_id."""
        ...

    @abstractmethod
    async def add_internal_note(self, ticket_id: str, payload: CommentPayload) -> str:
        """Add an agent-only internal note (handoff summary). Returns note_id."""
        ...

    # ── Assignment ──

    @abstractmethod
    async def assign_agent(self, ticket_id: str, payload: AssignPayload) -> bool:
        """Assign ticket to a specific agent or group. Used for handoff + escalation."""
        ...

    # ── Tags ──

    @abstractmethod
    async def add_tags(self, ticket_id: str, payload: TagPayload) -> bool:
        """Add classification tags to ticket (AI-generated categories)."""
        ...

    # ── Contacts ──

    @abstractmethod
    async def get_or_create_contact(self, contact: StandardContact) -> str:
        """Find or create contact in platform. Returns platform contact_id."""
        ...

    # ── Webhooks ──

    @abstractmethod
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify incoming webhook signature is authentic (not spoofed)."""
        ...

    @abstractmethod
    async def parse_webhook(self, raw_payload: dict) -> StandardEvent:
        """Convert platform-specific webhook payload into StandardEvent."""
        ...

    # ── Health ──

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if platform API is reachable. Used by /health endpoint."""
        ...
