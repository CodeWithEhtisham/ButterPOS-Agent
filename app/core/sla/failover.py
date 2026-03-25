"""Graceful failover — Critical Unresolved, 48h last resort escalation."""


class FailoverManager:
    """Handles edge-case escalation paths when normal resolution fails."""

    async def check_stale_tickets(self) -> list[str]:
        raise NotImplementedError

    async def force_escalate(self, ticket_id: str) -> None:
        raise NotImplementedError
