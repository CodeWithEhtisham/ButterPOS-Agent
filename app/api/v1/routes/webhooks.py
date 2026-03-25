"""POST /webhooks/ticketing — receives platform webhooks."""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/ticketing")
async def receive_ticketing_webhook(request: Request):
    raise NotImplementedError("Webhook processing not yet implemented")
