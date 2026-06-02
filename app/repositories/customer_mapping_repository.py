"""Customer mapping persistence — User → Branch → Restaurant → SLA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.branch import Branch
from app.db.models.restaurant import Restaurant
from app.db.models.sla_config import SLAConfig
from app.db.models.user import User


@dataclass(frozen=True)
class MappingRecord:
    """Joined row for mapping evaluation — optional fields when chain breaks."""

    butterpos_user_id: str
    user_id: int
    language_pref: str
    provider_contact_id: str | None
    branch_id: int | None
    butterpos_branch_id: str | None
    branch_name: str | None
    branch_timezone: str | None
    restaurant_id: int | None
    butterpos_restaurant_id: str | None
    restaurant_name: str | None
    plan_type: str | None
    payment_due: bool | None
    plan_expiry: datetime | None
    sla_coverage_hours: int | None
    sla_first_response_minutes: int | None
    sla_resolution_minutes: int | None
    sla_escalation_after_minutes: int | None
    sla_rules: dict[str, Any] | None
    sla_is_active: bool | None


def _row_to_record(
    user: User,
    branch: Branch | None,
    restaurant: Restaurant | None,
    sla: SLAConfig | None,
) -> MappingRecord:
    return MappingRecord(
        butterpos_user_id=user.butterpos_user_id,
        user_id=user.id,
        language_pref=user.language_pref,
        provider_contact_id=user.provider_contact_id,
        branch_id=branch.id if branch else None,
        butterpos_branch_id=branch.butterpos_branch_id if branch else None,
        branch_name=branch.name if branch else None,
        branch_timezone=branch.timezone if branch else None,
        restaurant_id=restaurant.id if restaurant else None,
        butterpos_restaurant_id=restaurant.butterpos_restaurant_id if restaurant else None,
        restaurant_name=restaurant.name if restaurant else None,
        plan_type=restaurant.plan_type if restaurant else None,
        payment_due=restaurant.payment_due if restaurant else None,
        plan_expiry=restaurant.expiry if restaurant else None,
        sla_coverage_hours=sla.coverage_hours if sla else None,
        sla_first_response_minutes=sla.first_response_minutes if sla else None,
        sla_resolution_minutes=sla.resolution_minutes if sla else None,
        sla_escalation_after_minutes=sla.escalation_after_minutes if sla else None,
        sla_rules=sla.rules if sla else None,
        sla_is_active=sla.is_active if sla else None,
    )


class CustomerMappingRepository:
    """Load mapping chain from Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_butterpos_user_id(self, butterpos_user_id: str) -> MappingRecord | None:
        return await self._fetch(user_filter=User.butterpos_user_id == butterpos_user_id)

    async def get_by_provider_contact_id(self, provider_contact_id: str) -> MappingRecord | None:
        return await self._fetch(user_filter=User.provider_contact_id == provider_contact_id)

    async def _fetch(self, *, user_filter: Any) -> MappingRecord | None:
        branch = aliased(Branch)
        restaurant = aliased(Restaurant)
        sla = aliased(SLAConfig)

        stmt = (
            select(User, branch, restaurant, sla)
            .outerjoin(branch, User.branch_id == branch.id)
            .outerjoin(restaurant, branch.restaurant_id == restaurant.id)
            .outerjoin(sla, restaurant.plan_type == sla.plan_type)
            .where(user_filter)
        )
        row = await self._session.execute(stmt)
        result = row.first()
        if result is None:
            return None
        user, branch_obj, restaurant_obj, sla_obj = result
        return _row_to_record(user, branch_obj, restaurant_obj, sla_obj)
