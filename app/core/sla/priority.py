"""Priority queue scoring for ticket triage."""


class PriorityScorer:
    """Calculates composite priority score for ticket queue ordering."""

    def score(self, ticket_data: dict) -> float:
        raise NotImplementedError
