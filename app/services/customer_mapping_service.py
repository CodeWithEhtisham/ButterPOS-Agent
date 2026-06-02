"""Customer/branch mapping service — Task 1.6."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.customer_mapping import CustomerMappingResult, MappingStatus
from app.repositories.customer_mapping_repository import CustomerMappingRepository, MappingRecord
from app.services.mapping.evaluator import (
    evaluate_mapping_record,
    unknown_contact_result,
    unknown_user_result,
)

logger = get_logger("app.mapping")


class CustomerMappingService:
    """Resolve ButterPOS user or ticketing contact to tenant context."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = CustomerMappingRepository(session)

    async def resolve_by_user_id(
        self,
        butterpos_user_id: str,
        *,
        now: datetime | None = None,
    ) -> CustomerMappingResult:
        """User ID → branch → restaurant → plan/payment/SLA checks."""
        record = await self._repo.get_by_butterpos_user_id(butterpos_user_id)
        if record is None:
            logger.info(
                "mapping_unknown_user butterpos_user_id=%s",
                butterpos_user_id,
                extra={"user_id": butterpos_user_id},
            )
            return unknown_user_result(butterpos_user_id)
        return self._evaluate(record, now=now)

    async def resolve_by_contact_id(
        self,
        provider_contact_id: str,
        *,
        now: datetime | None = None,
    ) -> CustomerMappingResult:
        """Ticketing contact id → user chain (webhook path until explicit user id)."""
        record = await self._repo.get_by_provider_contact_id(provider_contact_id)
        if record is None:
            logger.info(
                "mapping_unknown_contact provider_contact_id=%s",
                provider_contact_id,
                extra={"provider_contact_id": provider_contact_id},
            )
            return unknown_contact_result(provider_contact_id)
        return self._evaluate(record, now=now)

    def _evaluate(self, record: MappingRecord, *, now: datetime | None) -> CustomerMappingResult:
        resolved_at = now if now is not None else datetime.now(tz=UTC)
        result = evaluate_mapping_record(record, now=resolved_at)
        logger.info(
            "mapping_resolved butterpos_user_id=%s status=%s max_agent_tier=%s",
            result.butterpos_user_id,
            result.status.value,
            result.max_agent_tier,
            extra={
                "user_id": result.butterpos_user_id,
                "mapping_status": result.status.value,
                "max_agent_tier": result.max_agent_tier,
                "plan_type": result.plan_type,
            },
        )
        if result.status is not MappingStatus.ACTIVE:
            logger.warning(
                "mapping_restricted butterpos_user_id=%s status=%s",
                result.butterpos_user_id,
                result.status.value,
                extra={
                    "user_id": result.butterpos_user_id,
                    "mapping_status": result.status.value,
                },
            )
        return result
