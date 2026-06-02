"""Inbound webhook routes — Chatwoot and future platforms."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ticketing_provider_dep
from app.db.session import get_async_session
from app.providers.ticketing.base import TicketingProvider
from app.schemas.auth import ErrorResponse
from app.schemas.webhooks import WebhookAcceptedResponse
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/chatwoot",
    response_model=WebhookAcceptedResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
    summary="Receive Chatwoot account webhook",
)
async def receive_chatwoot_webhook(
    request: Request,
    provider: Annotated[TicketingProvider, Depends(ticketing_provider_dep)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WebhookAcceptedResponse:
    """Verify HMAC, parse, dedupe via Postgres, return 200 quickly."""
    raw_body = await request.body()
    headers = dict(request.headers)
    result = await WebhookService(provider, session).receive_chatwoot(raw_body, headers)
    return WebhookAcceptedResponse(
        status=result.status,
        event_type=result.event.event_type,
        provider_event_id=result.event.provider_event_id,
        provider_ticket_id=result.event.provider_ticket_id,
        idempotency_key=result.idempotency_key,
    )
