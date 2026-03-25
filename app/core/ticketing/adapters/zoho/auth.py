"""Zoho OAuth 2.0 token management."""


class ZohoAuthManager:
    """Handles Zoho OAuth token refresh and caching via Redis."""

    async def get_access_token(self) -> str:
        raise NotImplementedError

    async def refresh_token(self) -> str:
        raise NotImplementedError
