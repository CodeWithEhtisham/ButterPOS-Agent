"""Zoho-specific ↔ Standard model mapping functions."""

from app.core.ticketing.models import StandardTicket, StandardStatus, StandardComment


def zoho_ticket_to_standard(zoho_data: dict) -> StandardTicket:
    """Convert Zoho Desk ticket JSON to StandardTicket."""
    raise NotImplementedError


def standard_status_to_zoho(status: StandardStatus) -> str:
    """Map StandardStatus enum to Zoho Desk status string."""
    raise NotImplementedError


def zoho_status_to_standard(zoho_status: str) -> StandardStatus:
    """Map Zoho Desk status string to StandardStatus enum."""
    raise NotImplementedError
