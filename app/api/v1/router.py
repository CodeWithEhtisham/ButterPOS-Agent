"""Main v1 router — includes all sub-routers."""

from fastapi import APIRouter

from .routes.health import router as health_router
from .routes.chat import router as chat_router
from .routes.tickets import router as tickets_router
from .routes.webhooks import router as webhooks_router
from .routes.admin import router as admin_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(tickets_router)
api_v1_router.include_router(webhooks_router)
api_v1_router.include_router(admin_router)
