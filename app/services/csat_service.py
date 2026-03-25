"""CSAT collection + feedback loop."""


class CSATService:
    """Manages customer satisfaction scoring and feedback collection."""

    async def collect_score(self, ticket_id: str, score: int, source: str) -> None:
        raise NotImplementedError

    async def get_average_score(self, restaurant_id: int, days: int = 30) -> float:
        raise NotImplementedError
