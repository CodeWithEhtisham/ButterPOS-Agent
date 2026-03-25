"""Multi-turn conversation manager."""


class ConversationManager:
    """Manages multi-turn AI conversations with context windowing."""

    async def get_history(self, ticket_id: str) -> list[dict]:
        raise NotImplementedError

    async def add_message(self, ticket_id: str, role: str, content: str) -> None:
        raise NotImplementedError

    async def summarize(self, ticket_id: str) -> str:
        raise NotImplementedError
