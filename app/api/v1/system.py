"""System / health routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_subject, ticketing_provider_dep
from app.models.standard import ProviderHealth
from app.providers.ticketing.base import TicketingProvider
from app.schemas.auth import AuthenticatedSubject

router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/ticketing-health",
    response_model=ProviderHealth,
    summary="Ticketing provider configuration / health probe",
)
async def ticketing_health(
    _subject: Annotated[AuthenticatedSubject, Depends(get_current_subject)],
    provider: Annotated[TicketingProvider, Depends(ticketing_provider_dep)],
) -> ProviderHealth:
    """Protected route — verifies factory wiring and adapter health_check."""
    return await provider.health_check()
