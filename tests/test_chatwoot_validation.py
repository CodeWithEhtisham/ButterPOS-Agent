"""Offline tests for Chatwoot validation report shape — Task 1.8.2."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.models.standard import ProviderHealth, StandardContact, StandardStatus, StandardTicket
from scripts.validate_chatwoot import ValidationReport, validate_adapter


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        chatwoot_base_url="http://localhost:3000",
        chatwoot_api_token="token",
        chatwoot_account_id=1,
        chatwoot_inbox_id=1,
    )


def test_validate_adapter_report_passes_with_mocked_adapter() -> None:
    async def _run() -> None:
        contact = StandardContact(provider_contact_id="42", name="Test")
        ticket = StandardTicket(
            provider_ticket_id="9001",
            status=StandardStatus.OPEN,
            provider_contact_id="42",
            tags=["butterpos-integration"],
        )
        in_progress = ticket.model_copy(update={"status": StandardStatus.IN_PROGRESS, "tags": ["integration-pass"]})

        mock_adapter = MagicMock()
        mock_adapter.health_check = AsyncMock(
            return_value=ProviderHealth(healthy=True, provider="chatwoot", latency_ms=12.5),
        )
        mock_adapter.get_or_create_contact = AsyncMock(return_value=contact)
        mock_adapter.create_ticket = AsyncMock(return_value=ticket)
        mock_adapter.get_ticket = AsyncMock(return_value=ticket)
        mock_adapter.add_comment = AsyncMock(return_value=None)
        mock_adapter.add_note = AsyncMock(return_value=None)
        mock_adapter.add_tags = AsyncMock(return_value=in_progress)
        mock_adapter.update_status = AsyncMock(return_value=in_progress)
        mock_adapter._client.close = AsyncMock()

        with patch("scripts.validate_chatwoot.ChatwootAdapter", return_value=mock_adapter):
            report = await validate_adapter(_settings())

        assert isinstance(report, ValidationReport)
        assert report.passed is True
        assert report.contact_id == "42"
        assert report.ticket_id == "9001"
        assert len(report.checks) >= 7

    asyncio.run(_run())
