"""PII masking + de-masking (reversible via Redis)."""


class PIIMasker:
    """Detects and masks PII in text, stores mapping in Redis for reversal."""

    async def mask(self, text: str) -> tuple[str, dict]:
        """Mask PII in text. Returns (masked_text, mapping_dict)."""
        raise NotImplementedError

    async def unmask(self, masked_text: str, mapping_key: str) -> str:
        """Restore original PII from masked text using Redis-stored mapping."""
        raise NotImplementedError
