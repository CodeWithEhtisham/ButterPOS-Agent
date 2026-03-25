"""
ZohoAdapter — Implements TicketingProvider for Zoho Desk.

All Zoho-specific logic is isolated here. The middleware never imports this directly;
it's loaded via the factory based on TICKETING_PROVIDER=zoho.
"""

from app.core.ticketing.interface import TicketingProvider
from app.core.ticketing.models import (
    StandardTicket,
    StandardEvent,
    StandardContact,
    StandardStatus,
    TicketCreatePayload,
    CommentPayload,
    AssignPayload,
    TagPayload,
)


class ZohoAdapter(TicketingProvider):
    """Zoho Desk implementation of TicketingProvider."""

    async def create_ticket(self, payload: TicketCreatePayload) -> StandardTicket:
        raise NotImplementedError("ZohoAdapter.create_ticket not yet implemented")

    async def get_ticket(self, ticket_id: str) -> StandardTicket:
        raise NotImplementedError("ZohoAdapter.get_ticket not yet implemented")

    async def update_status(self, ticket_id: str, status: StandardStatus) -> bool:
        raise NotImplementedError("ZohoAdapter.update_status not yet implemented")

    async def add_public_comment(self, ticket_id: str, payload: CommentPayload) -> str:
        raise NotImplementedError("ZohoAdapter.add_public_comment not yet implemented")

    async def add_internal_note(self, ticket_id: str, payload: CommentPayload) -> str:
        raise NotImplementedError("ZohoAdapter.add_internal_note not yet implemented")

    async def assign_agent(self, ticket_id: str, payload: AssignPayload) -> bool:
        raise NotImplementedError("ZohoAdapter.assign_agent not yet implemented")

    async def add_tags(self, ticket_id: str, payload: TagPayload) -> bool:
        raise NotImplementedError("ZohoAdapter.add_tags not yet implemented")

    async def get_or_create_contact(self, contact: StandardContact) -> str:
        raise NotImplementedError("ZohoAdapter.get_or_create_contact not yet implemented")

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        raise NotImplementedError("ZohoAdapter.verify_webhook not yet implemented")

    async def parse_webhook(self, raw_payload: dict) -> StandardEvent:
        raise NotImplementedError("ZohoAdapter.parse_webhook not yet implemented")

    async def health_check(self) -> bool:
        raise NotImplementedError("ZohoAdapter.health_check not yet implemented")
