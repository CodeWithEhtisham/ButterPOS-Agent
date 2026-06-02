"""API v1 route aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, chat, system, webhooks

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(system.router)
api_v1_router.include_router(webhooks.router)
api_v1_router.include_router(chat.router)
