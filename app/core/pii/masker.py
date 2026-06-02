"""PII detection and reversible masking before LLM calls."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field

from app.core.pii.detector import PiiDetector, RegexPiiDetector, build_pii_detector
from app.core.pii.store import PiiTokenStore

TOKEN_PATTERN = re.compile(r"\[PII:(?P<entity>[A-Z_]+):(?P<token>[a-f0-9]{8})\]")


@dataclass
class MaskResult:
    """Output of mask operation."""

    masked_text: str
    token_count: int
    entity_types: list[str] = field(default_factory=list)


class PIIMasker:
    """Detect PII, replace with reversible tokens stored in Redis (24h TTL)."""

    def __init__(self, store: PiiTokenStore, detector: PiiDetector | None = None) -> None:
        self._store = store
        self._detector = detector or build_pii_detector()

    async def mask(self, text: str, *, language: str = "en") -> MaskResult:
        if not text:
            return MaskResult(masked_text="", token_count=0)

        spans = self._detector.detect(text, language=language)
        if not spans:
            return MaskResult(masked_text=text, token_count=0)

        masked = text
        entity_types: list[str] = []
        for span in sorted(spans, key=lambda s: s.start, reverse=True):
            original = text[span.start : span.end]
            token_id = secrets.token_hex(4)
            placeholder = f"[PII:{span.entity_type}:{token_id}]"
            await self._store.put(token_id, original, span.entity_type)
            masked = masked[: span.start] + placeholder + masked[span.end :]
            entity_types.append(span.entity_type)

        return MaskResult(
            masked_text=masked,
            token_count=len(spans),
            entity_types=entity_types,
        )

    async def unmask(self, text: str) -> str:
        if not text or "[PII:" not in text:
            return text

        unmasked = text
        for match in TOKEN_PATTERN.finditer(text):
            token_id = match.group("token")
            original = await self._store.get(token_id)
            if original is not None:
                unmasked = unmasked.replace(match.group(0), original, 1)
        return unmasked

    async def mask_messages(
        self,
        messages: list[dict[str, str]],
        *,
        language: str = "en",
    ) -> tuple[list[dict[str, str]], int]:
        """Mask `content` on each message dict before sending to an LLM."""
        total_tokens = 0
        masked_messages: list[dict[str, str]] = []
        for message in messages:
            content = message.get("content", "")
            if not content:
                masked_messages.append(dict(message))
                continue
            result = await self.mask(content, language=language)
            total_tokens += result.token_count
            updated = dict(message)
            updated["content"] = result.masked_text
            masked_messages.append(updated)
        return masked_messages, total_tokens


__all__ = ["MaskResult", "PIIMasker", "RegexPiiDetector"]
