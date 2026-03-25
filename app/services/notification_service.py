"""Email notifications — resolution, escalation, CSAT."""


class NotificationService:
    """Sends email notifications for ticket lifecycle events."""

    async def send_resolution_email(self, ticket_id: str, user_email: str) -> None:
        raise NotImplementedError

    async def send_escalation_email(self, ticket_id: str, agent_email: str) -> None:
        raise NotImplementedError

    async def send_csat_email(self, ticket_id: str, user_email: str) -> None:
        raise NotImplementedError
