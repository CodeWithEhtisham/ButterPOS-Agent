"""FastAPI dependencies shared across routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, decode_access_token
from app.schemas.auth import AuthenticatedSubject

_bearer = HTTPBearer(auto_error=False)


def settings_dep() -> Settings:
    """Inject cached application settings."""
    return get_settings()


def get_current_subject(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> AuthenticatedSubject:
    """Require a valid Bearer JWT on protected routes."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedSubject(subject=payload.sub)
