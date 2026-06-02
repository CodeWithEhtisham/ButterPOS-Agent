"""Inbound text PII masking — Task 1.5.3 ties Redis token map to webhook ingress."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.core.pii.factory import create_pii_masker
from app.core.pii.masker import PIIMasker
from app.models.standard import StandardEvent, StandardEventType

logger = get_logger("app.pii")

INBOUND_PII_EVENT_TYPES = frozenset(
    {
        StandardEventType.MESSAGE_CREATED,
        StandardEventType.MESSAGE_UPDATED,
    }
)


class InboundPiiService:
    """Mask customer message text and persist reversible tokens in Redis."""

    def __init__(self, masker: PIIMasker) -> None:
        self._masker = masker

    async def mask_event_for_processing(self, event: StandardEvent) -> StandardEvent:
        """Return event copy with message_body masked when PII is detected."""
        if event.event_type not in INBOUND_PII_EVENT_TYPES:
            return event
        if not event.message_body or event.message_direction != "incoming":
            return event

        result = await self._masker.mask(event.message_body)
        if result.token_count == 0:
            return event

        logger.info(
            "inbound_message_pii_masked ticket_id=%s token_count=%s",
            event.provider_ticket_id,
            result.token_count,
            extra={
                "ticket_id": event.provider_ticket_id,
                "token_count": result.token_count,
                "entity_types": result.entity_types,
            },
        )
        return event.model_copy(update={"message_body": result.masked_text})


def build_inbound_pii_service(settings: Settings, *, masker: PIIMasker | None = None) -> InboundPiiService:
    return InboundPiiService(masker or create_pii_masker(settings))


@lru_cache
def get_inbound_pii_service() -> InboundPiiService:
    return build_inbound_pii_service(get_settings())


def clear_inbound_pii_service_cache() -> None:
    get_inbound_pii_service.cache_clear()
