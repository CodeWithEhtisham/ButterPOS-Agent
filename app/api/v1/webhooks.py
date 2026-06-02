"""Inbound webhook routes — Chatwoot and future platforms."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import ticketing_provider_dep
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
    },
    summary="Receive Chatwoot account webhook",
)
async def receive_chatwoot_webhook(
    request: Request,
    provider: Annotated[TicketingProvider, Depends(ticketing_provider_dep)],
) -> WebhookAcceptedResponse:
    """Verify HMAC on raw body, parse to StandardEvent, return 200 quickly.

    Idempotency persistence and agent processing arrive in Task 1.4 sub-steps 2+.
    """
    raw_body = await request.body()
    headers = dict(request.headers)
    event = await WebhookService(provider).receive_chatwoot(raw_body, headers)
    return WebhookAcceptedResponse(
        event_type=event.event_type,
        provider_event_id=event.provider_event_id,
        provider_ticket_id=event.provider_ticket_id,
        idempotency_key=event.idempotency_key,
    )
