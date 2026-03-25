"""Main chat orchestration — message → triage → respond."""


class ChatService:
    """Orchestrates the full chat flow: receive message, check payment, triage, route to AI/human."""

    async def process_message(self, user_id: int, message: str, ticket_id: str | None = None) -> dict:
        raise NotImplementedError
