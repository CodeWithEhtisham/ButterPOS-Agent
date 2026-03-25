"""Zoho webhook → StandardEvent parser."""

from app.core.ticketing.models import StandardEvent


def parse_zoho_webhook(raw_payload: dict) -> StandardEvent:
    """Convert Zoho Desk webhook payload into StandardEvent."""
    raise NotImplementedError
