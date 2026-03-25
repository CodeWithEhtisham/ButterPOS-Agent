"""AI decision router — Routes tickets through Path A (auto-resolve), B (guided), or C (escalate)."""


class AIRouter:
    """Determines resolution path based on confidence score and ticket context."""

    async def route(self, ticket_id: str, message: str, context: dict) -> dict:
        raise NotImplementedError
