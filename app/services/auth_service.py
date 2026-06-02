"""Authentication business logic."""

from __future__ import annotations

from app.core.config import Settings
from app.core.security import create_access_token, token_expires_in_seconds
from app.schemas.auth import TokenRequest, TokenResponse


class AuthService:
    """Issue JWT access tokens after client credential validation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def issue_token(self, request: TokenRequest) -> TokenResponse:
        if not self._settings.jwt_secret:
            raise ValueError("JWT_SECRET is not configured")

        if not self._settings.api_client_id or not self._settings.api_client_secret:
            raise ValueError("API client credentials are not configured")

        if request.client_id != self._settings.api_client_id:
            raise PermissionError("Invalid client credentials")

        if request.client_secret != self._settings.api_client_secret:
            raise PermissionError("Invalid client credentials")

        access_token = create_access_token(request.subject, self._settings)
        return TokenResponse(
            access_token=access_token,
            expires_in=token_expires_in_seconds(self._settings),
        )
