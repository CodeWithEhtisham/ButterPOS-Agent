"""Admin endpoints — circuit breaker, KB management."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/circuit-breaker/status")
async def circuit_breaker_status():
    raise NotImplementedError("Circuit breaker status not yet implemented")


@router.post("/circuit-breaker/toggle")
async def toggle_circuit_breaker():
    raise NotImplementedError("Circuit breaker toggle not yet implemented")


@router.get("/kb/articles")
async def list_kb_articles():
    raise NotImplementedError("KB article listing not yet implemented")
