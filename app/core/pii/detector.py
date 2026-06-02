"""PII entity detection — regex baseline with optional Presidio/spaCy enrichment."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PII_ENTITIES = frozenset(
    {
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "CREDIT_CARD",
        "IBAN_CODE",
        "US_BANK_NUMBER",
        "PERSON",
        "US_SSN",
        "NATIONAL_ID",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
    }
)


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    entity_type: str


class PiiDetector(ABC):
    @abstractmethod
    def detect(self, text: str, *, language: str = "en") -> list[PiiSpan]:
        """Return detected PII spans in text."""


class RegexPiiDetector(PiiDetector):
    """Pattern-based detector — no spaCy; always available."""

    _RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "EMAIL_ADDRESS",
            re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        ),
        ("PHONE_NUMBER", re.compile(r"03\d{2}[\s\-]?\d{7}")),
        ("PHONE_NUMBER", re.compile(r"\+?\d[\d\s\-()]{8,}\d")),
        ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
        ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        ("IBAN_CODE", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
        (
            "PERSON",
            re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
        ),
    )

    def detect(self, text: str, *, language: str = "en") -> list[PiiSpan]:
        del language
        spans: list[PiiSpan] = []
        for entity_type, pattern in self._RULES:
            for match in pattern.finditer(text):
                spans.append(PiiSpan(match.start(), match.end(), entity_type))
        return non_overlapping_spans(spans)


class PresidioPiiDetector(PiiDetector):
    """Presidio AnalyzerEngine wrapper — requires spaCy model when used."""

    def __init__(self, analyzer: object) -> None:
        self._analyzer = analyzer

    def detect(self, text: str, *, language: str = "en") -> list[PiiSpan]:
        results = self._analyzer.analyze(  # type: ignore[union-attr]
            text=text,
            entities=list(PII_ENTITIES),
            language=language,
        )
        spans = [PiiSpan(r.start, r.end, r.entity_type) for r in results]
        return non_overlapping_spans(spans)


def non_overlapping_spans(spans: list[PiiSpan]) -> list[PiiSpan]:
    ordered = sorted(spans, key=lambda s: s.start)
    kept: list[PiiSpan] = []
    last_end = -1
    for span in ordered:
        if span.start >= last_end:
            kept.append(span)
            last_end = span.end
    return kept


def build_pii_detector() -> PiiDetector:
    """Prefer Presidio when spaCy model is installed; otherwise regex fallback."""
    try:
        from presidio_analyzer import AnalyzerEngine

        return PresidioPiiDetector(AnalyzerEngine())
    except Exception as exc:  # noqa: BLE001 — optional dependency path
        logger.warning("Presidio unavailable (%s); using regex PII detector", exc)
        return RegexPiiDetector()
