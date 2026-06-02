"""PII masking tests — Task 1.1.7."""

from __future__ import annotations

import asyncio

import pytest
from app.core.pii.detector import RegexPiiDetector
from app.core.pii.masker import PIIMasker
from app.core.pii.store import InMemoryPiiTokenStore


@pytest.fixture
def masker() -> PIIMasker:
    return PIIMasker(store=InMemoryPiiTokenStore(), detector=RegexPiiDetector())


def test_mask_email_and_phone(masker: PIIMasker) -> None:
    text = "Contact at ali@restaurant.pk or 0301-1234567 for billing."
    result = asyncio.run(masker.mask(text))
    assert result.token_count >= 2
    assert "ali@restaurant.pk" not in result.masked_text
    assert "0301" not in result.masked_text or "[PII:PHONE_NUMBER:" in result.masked_text
    assert "[PII:EMAIL_ADDRESS:" in result.masked_text


def test_unmask_restores_original(masker: PIIMasker) -> None:
    original = "Email support@butterpos.com for help."
    masked = asyncio.run(masker.mask(original))
    restored = asyncio.run(masker.unmask(masked.masked_text))
    assert restored == original


def test_roundtrip_preserves_non_pii(masker: PIIMasker) -> None:
    original = "Printer offline hai branch 101 pe."
    masked = asyncio.run(masker.mask(original))
    assert masked.masked_text == original
    assert masked.token_count == 0


def test_mask_messages_llm_format(masker: PIIMasker) -> None:
    messages = [
        {"role": "system", "content": "You are support."},
        {"role": "user", "content": "Mera number 03001234567 hai, card 4111 1111 1111 1111"},
    ]
    masked, count = asyncio.run(masker.mask_messages(messages))
    assert count >= 1
    assert "03001234567" not in masked[1]["content"]
    assert masked[0]["content"] == "You are support."


def test_unmask_without_tokens_returns_unchanged(masker: PIIMasker) -> None:
    text = "No sensitive data here."
    assert asyncio.run(masker.unmask(text)) == text


def test_expired_token_left_as_placeholder() -> None:
    store = InMemoryPiiTokenStore()
    masker = PIIMasker(store=store, detector=RegexPiiDetector())
    original = "Call 03009998877"
    masked = asyncio.run(masker.mask(original))
    # Simulate expiry by clearing store
    store._values.clear()
    unmasked = asyncio.run(masker.unmask(masked.masked_text))
    assert "03009998877" not in unmasked
    assert "[PII:PHONE_NUMBER:" in unmasked
