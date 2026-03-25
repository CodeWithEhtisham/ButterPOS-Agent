"""Test PII masking/de-masking — placeholder for Phase 2."""


def test_pii_masker_exists():
    from app.core.security.pii import PIIMasker
    masker = PIIMasker()
    assert masker is not None
