"""JWT creation and validation (HS256)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jose import JWTError as JoseJWTError
from jose import jwt
from pydantic import BaseModel, Field

from app.core.config import Settings


class TokenPayload(BaseModel):
    """Claims stored in access tokens."""

    sub: str = Field(description="Subject — user or service identifier")
    exp: int = Field(description="Expiry unix timestamp")
    iat: int = Field(description="Issued-at unix timestamp")
    token_type: str = "access"


class InvalidTokenError(Exception):
    """Invalid or expired token."""


def _now_ts() -> int:
    return int(datetime.now(UTC).timestamp())


def create_access_token(
    subject: str,
    settings: Settings,
    *,
    expires_minutes: int | None = None,
) -> str:
    """Sign a JWT access token for the given subject."""
    if not settings.jwt_secret:
        raise ValueError("JWT_SECRET is not configured")

    default_ttl = settings.jwt_access_token_expire_minutes
    ttl = expires_minutes if expires_minutes is not None else default_ttl
    now = _now_ts()
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + ttl * 60,
        "token_type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> TokenPayload:
    """Validate and parse a JWT access token."""
    if not settings.jwt_secret:
        raise InvalidTokenError("JWT_SECRET is not configured")

    try:
        data: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JoseJWTError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    if data.get("token_type") != "access":
        raise InvalidTokenError("Invalid token type")

    sub = data.get("sub")
    if not sub or not isinstance(sub, str):
        raise InvalidTokenError("Token missing subject")

    return TokenPayload(
        sub=sub,
        exp=int(data["exp"]),
        iat=int(data["iat"]),
        token_type=str(data.get("token_type", "access")),
    )


def token_expires_in_seconds(settings: Settings, *, expires_minutes: int | None = None) -> int:
    default_ttl = settings.jwt_access_token_expire_minutes
    ttl = expires_minutes if expires_minutes is not None else default_ttl
    return ttl * 60
