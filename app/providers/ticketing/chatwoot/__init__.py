"""Chatwoot adapter package — platform-specific HTTP client and mappers (Task 1.3)."""

from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootAuthError, ChatwootConfigError

__all__ = ["ChatwootAPIError", "ChatwootAuthError", "ChatwootClient", "ChatwootConfigError"]
