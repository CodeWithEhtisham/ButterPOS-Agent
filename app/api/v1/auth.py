"""Authentication routes — token issuance and session introspection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_subject, settings_dep
from app.core.config import Settings
from app.schemas.auth import AuthenticatedSubject, ErrorResponse, TokenRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
    summary="Obtain JWT access token",
)
def create_token(
    body: TokenRequest,
    settings: Annotated[Settings, Depends(settings_dep)],
) -> TokenResponse:
    """Exchange API client credentials for a signed JWT."""
    service = AuthService(settings)
    try:
        return service.issue_token(body)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get(
    "/me",
    response_model=AuthenticatedSubject,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
    summary="Return authenticated subject from JWT",
)
def read_current_subject(
    subject: Annotated[AuthenticatedSubject, Depends(get_current_subject)],
) -> AuthenticatedSubject:
    """Protected route — validates Bearer JWT dependency."""
    return subject
