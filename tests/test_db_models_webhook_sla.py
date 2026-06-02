"""Webhook event log + SLA config ORM tests — Task 1.2 sub-step 5."""

from __future__ import annotations

from app.db.base import Base
from app.db.models import SLAConfig, WebhookEventLog
from sqlalchemy.dialects.postgresql import JSONB


def test_webhook_event_log_table_columns() -> None:
    columns = WebhookEventLog.__table__.columns
    assert columns["idempotency_key"].unique
    assert columns["payload_hash"].nullable is False
    assert columns["payload_hash"].type.length == 64  # type: ignore[attr-defined]
    assert columns["event_type"].nullable is False
    assert columns["status"].nullable is False
    assert columns["error_message"].nullable is True
    assert columns["processed_at"].nullable is True


def test_sla_config_table_columns() -> None:
    columns = SLAConfig.__table__.columns
    assert columns["plan_type"].unique
    assert columns["coverage_hours"].nullable is False
    assert columns["first_response_minutes"].nullable is False
    assert columns["resolution_minutes"].nullable is False
    assert columns["escalation_after_minutes"].nullable is False
    assert isinstance(columns["rules"].type, JSONB)
    assert columns["is_active"].nullable is False


def test_webhook_sla_models_in_metadata() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert {"webhook_event_log", "sla_config"}.issubset(names)
