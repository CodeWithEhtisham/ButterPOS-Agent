"""Customer/branch mapping result models — Task 1.6."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MappingStatus(str, Enum):
    """Outcome of resolving a ButterPOS user to tenant context."""

    ACTIVE = "active"
    UNKNOWN_USER = "unknown_user"
    NO_BRANCH = "no_branch"
    PAYMENT_DUE = "payment_due"
    PLAN_EXPIRED = "plan_expired"
    OUTSIDE_COVERAGE = "outside_coverage"
    SLA_NOT_CONFIGURED = "sla_not_configured"


class SlaSnapshot(BaseModel):
    """SLA targets for the restaurant plan at resolution time."""

    plan_type: str
    coverage_hours: int
    first_response_minutes: int
    resolution_minutes: int
    escalation_after_minutes: int
    coverage_start_hour: int = 9
    within_coverage: bool


class CustomerMappingResult(BaseModel):
    """Resolved tenant context for agent authorization and SLA routing."""

    status: MappingStatus
    status_message: str
    max_agent_tier: int = Field(
        ge=1,
        le=3,
        description="Highest autonomous tier allowed (1=read-only, 3=full per D-5 tiers)",
    )
    butterpos_user_id: str | None = None
    user_id: int | None = None
    language_pref: str | None = None
    provider_contact_id: str | None = None
    branch_id: int | None = None
    butterpos_branch_id: str | None = None
    branch_name: str | None = None
    branch_timezone: str | None = None
    restaurant_id: int | None = None
    butterpos_restaurant_id: str | None = None
    restaurant_name: str | None = None
    plan_type: str | None = None
    payment_due: bool | None = None
    plan_expiry: datetime | None = None
    sla: SlaSnapshot | None = None
