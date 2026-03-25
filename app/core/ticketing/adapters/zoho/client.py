"""Zoho HTTP client — raw API calls to Zoho Desk REST API."""


class ZohoClient:
    """Low-level HTTP client for Zoho Desk API."""

    async def get(self, endpoint: str, params: dict | None = None) -> dict:
        raise NotImplementedError

    async def post(self, endpoint: str, data: dict | None = None) -> dict:
        raise NotImplementedError

    async def patch(self, endpoint: str, data: dict | None = None) -> dict:
        raise NotImplementedError
