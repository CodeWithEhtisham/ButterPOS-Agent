"""ButterPOS tenant export schema — Task 1.7 seeding."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

EXPORT_SCHEMA_VERSION = "1"
ALLOWED_PLAN_TYPES = frozenset({"8h", "16h", "24-7"})


class RestaurantExportRow(BaseModel):
    butterpos_restaurant_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    plan_type: str = Field(min_length=1, max_length=32)
    payment_due: bool = False
    expiry: datetime | None = None

    @field_validator("plan_type")
    @classmethod
    def validate_plan_type(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in ALLOWED_PLAN_TYPES:
            allowed = ", ".join(sorted(ALLOWED_PLAN_TYPES))
            raise ValueError(f"plan_type must be one of: {allowed}")
        return normalized


class BranchExportRow(BaseModel):
    butterpos_branch_id: str = Field(min_length=1, max_length=64)
    butterpos_restaurant_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(default="Asia/Karachi", max_length=64)
    devices: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid IANA timezone: {value}") from exc
        return value


class UserExportRow(BaseModel):
    butterpos_user_id: str = Field(min_length=1, max_length=64)
    butterpos_branch_id: str | None = Field(default=None, max_length=64)
    provider_contact_id: str | None = Field(default=None, max_length=128)
    language_pref: str = Field(default="en", max_length=16)


class SlaConfigExportRow(BaseModel):
    plan_type: str = Field(min_length=1, max_length=32)
    coverage_hours: int = Field(ge=1, le=24)
    first_response_minutes: int = Field(ge=1)
    resolution_minutes: int = Field(ge=1)
    escalation_after_minutes: int = Field(ge=1)
    description: str | None = Field(default=None, max_length=512)
    rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("plan_type")
    @classmethod
    def validate_plan_type(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in ALLOWED_PLAN_TYPES:
            allowed = ", ".join(sorted(ALLOWED_PLAN_TYPES))
            raise ValueError(f"plan_type must be one of: {allowed}")
        return normalized


class TenantExportDocument(BaseModel):
    """Versioned envelope for restaurant / branch / user seed files."""

    schema_version: Literal["1"] = EXPORT_SCHEMA_VERSION
    restaurants: list[RestaurantExportRow] = Field(min_length=1)
    branches: list[BranchExportRow] = Field(default_factory=list)
    users: list[UserExportRow] = Field(default_factory=list)
    sla_configs: list[SlaConfigExportRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cross_references(self) -> TenantExportDocument:
        _assert_unique([r.butterpos_restaurant_id for r in self.restaurants], "restaurant id")
        _assert_unique([b.butterpos_branch_id for b in self.branches], "branch id")
        _assert_unique([u.butterpos_user_id for u in self.users], "user id")
        _assert_unique([s.plan_type for s in self.sla_configs], "sla plan_type")

        restaurant_ids = {r.butterpos_restaurant_id for r in self.restaurants}
        branch_ids = {b.butterpos_branch_id for b in self.branches}

        for branch in self.branches:
            if branch.butterpos_restaurant_id not in restaurant_ids:
                raise ValueError(
                    f"branch {branch.butterpos_branch_id} references unknown restaurant "
                    f"{branch.butterpos_restaurant_id}"
                )

        for user in self.users:
            if user.butterpos_branch_id is not None and user.butterpos_branch_id not in branch_ids:
                raise ValueError(
                    f"user {user.butterpos_user_id} references unknown branch "
                    f"{user.butterpos_branch_id}"
                )

        restaurant_plans = {r.plan_type for r in self.restaurants}
        sla_plans = {s.plan_type for s in self.sla_configs}
        missing_sla = restaurant_plans - sla_plans
        if missing_sla and self.sla_configs:
            raise ValueError(
                f"sla_configs missing plan types used by restaurants: {sorted(missing_sla)}"
            )

        return self


def _assert_unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"Duplicate {label}: {value}")
        seen.add(value)
