"""System health API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health of a single middleware dependency."""

    name: str
    healthy: bool
    message: str | None = None


class SystemHealthResponse(BaseModel):
    """Aggregate readiness for load balancers and smoke tests."""

    healthy: bool
    app: str = Field(description="Application name from settings")
    version: str
    components: list[ComponentHealth]
