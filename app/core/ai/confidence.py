"""Confidence scoring engine for AI responses."""


class ConfidenceScorer:
    """Calculates confidence score for AI-generated responses."""

    async def score(self, query: str, response: str, context: dict) -> float:
        raise NotImplementedError
