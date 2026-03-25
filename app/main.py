from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB connection pool, Redis, etc.
    yield
    # Shutdown: cleanup connections


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.include_router(api_v1_router, prefix="/api/v1")
