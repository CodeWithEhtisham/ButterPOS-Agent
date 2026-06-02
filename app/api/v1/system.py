"""System / health routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_subject, settings_dep, ticketing_provider_dep
from app.core.config import Settings
from app.db.session import get_async_session
from app.models.standard import ProviderHealth
from app.providers.ticketing.base import TicketingProvider
from app.schemas.auth import AuthenticatedSubject
from app.schemas.system import SystemHealthResponse
from app.services.system_health_service import collect_system_health

router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="Middleware readiness (Postgres + Redis)",
)
async def system_health(
    settings: Annotated[Settings, Depends(settings_dep)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> JSONResponse | SystemHealthResponse:
    """Unauthenticated liveness/readiness — used by smoke tests and load balancers."""
    report = await collect_system_health(settings, session)
    status_code = status.HTTP_200_OK if report.healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=report.model_dump())


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
