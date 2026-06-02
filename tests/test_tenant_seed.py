"""Tenant export validation and seeding tests — Task 1.7 sub-step 1."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from app.schemas.tenant_export import TenantExportDocument
from app.services.tenant_export_loader import TenantExportLoadError, load_tenant_export
from app.services.tenant_seed_service import TenantSeedService

FIXTURE = Path(__file__).resolve().parents[1] / "scripts" / "fixtures" / "sample_tenant_export.json"


def test_sample_fixture_loads_and_validates() -> None:
    loaded = load_tenant_export(FIXTURE)
    assert loaded.format == "json"
    assert len(loaded.document.restaurants) == 3
    assert len(loaded.document.users) == 3


def test_duplicate_restaurant_id_rejected() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["restaurants"].append(payload["restaurants"][0])
    with pytest.raises(ValidationError, match="Duplicate"):
        TenantExportDocument.model_validate(payload)


def test_unknown_branch_reference_rejected() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["users"].append(
        {
            "butterpos_user_id": "bad-user",
            "butterpos_branch_id": "missing-branch",
            "language_pref": "en",
        }
    )
    with pytest.raises(ValidationError, match="unknown branch"):
        TenantExportDocument.model_validate(payload)


def test_invalid_timezone_rejected() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["branches"][0]["timezone"] = "Not/Real"
    with pytest.raises(ValidationError, match="timezone"):
        TenantExportDocument.model_validate(payload)


def test_missing_export_path_raises() -> None:
    with pytest.raises(TenantExportLoadError, match="not found"):
        load_tenant_export(Path("/tmp/does-not-exist-butterpos-export.json"))


def test_dry_run_does_not_touch_database() -> None:
    async def _run() -> None:
        loaded = load_tenant_export(FIXTURE)
        session = MagicMock()
        session.flush = AsyncMock()
        service = TenantSeedService(session)
        summary = await service.seed(loaded.document, dry_run=True)
        assert summary.dry_run is True
        assert summary.restaurants == 3
        session.add.assert_not_called()

    asyncio.run(_run())


def test_seed_default_sla_merges_missing_plans() -> None:
    async def _run() -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["sla_configs"] = []
        document = TenantExportDocument.model_validate(payload)
        session = MagicMock()
        session.scalar = AsyncMock(return_value=None)
        session.add = MagicMock()
        session.flush = AsyncMock()

        service = TenantSeedService(session)
        summary = await service.seed(document, seed_default_sla=True)
        assert summary.sla_configs == 3
        assert session.add.call_count >= 3

    asyncio.run(_run())


def test_upsert_updates_existing_restaurant() -> None:
    async def _run() -> None:
        loaded = load_tenant_export(FIXTURE)
        row = loaded.document.restaurants[0]
        existing = MagicMock()
        existing.id = 99
        session = MagicMock()
        session.scalar = AsyncMock(return_value=existing)
        session.add = MagicMock()
        session.flush = AsyncMock()

        service = TenantSeedService(session)
        mapping = await service._upsert_restaurants([row])
        assert mapping[row.butterpos_restaurant_id] == 99
        assert existing.name == row.name

    asyncio.run(_run())
