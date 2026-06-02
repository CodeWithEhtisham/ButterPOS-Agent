"""Authentication API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """Exchange client credentials for a JWT access token."""

    client_id: str = Field(min_length=1, max_length=128)
    client_secret: str = Field(min_length=1, max_length=256)
    subject: str = Field(
        min_length=1,
        max_length=128,
        description="User or session identifier embedded in the token (e.g. staff user id)",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until token expiry")


class AuthenticatedSubject(BaseModel):
    """Resolved identity from a valid JWT."""

    subject: str


class ErrorResponse(BaseModel):
    detail: str
