"""Ticket lifecycle management."""


class TicketService:
    """Manages ticket creation, updates, caching, and sync with ticketing platform."""

    async def create(self, data: dict) -> dict:
        raise NotImplementedError

    async def get(self, ticket_id: int) -> dict:
        raise NotImplementedError

    async def update_status(self, ticket_id: int, status: str) -> dict:
        raise NotImplementedError

    async def sync_from_platform(self, platform_ticket_id: str) -> dict:
        raise NotImplementedError
