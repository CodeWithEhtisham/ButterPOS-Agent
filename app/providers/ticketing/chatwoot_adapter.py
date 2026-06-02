"""Chatwoot adapter — implements TicketingProvider (Task 1.3).

Platform-specific Chatwoot API calls live here only.
"""

from __future__ import annotations

from app.core.config import Settings
from app.models.standard import (
    AddCommentRequest,
    AddNoteRequest,
    AddTagsRequest,
    AssignAgentRequest,
    CreateContactRequest,
    CreateTicketRequest,
    ProviderHealth,
    StandardContact,
    StandardEvent,
    StandardTicket,
    UpdateStatusRequest,
)
from app.providers.ticketing.base import TicketingProvider
from app.providers.ticketing.chatwoot.auth import missing_config_fields
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootAuthError, ChatwootConfigError

_TASK_1_3_REMAINING = "Not implemented — completed in later Task 1.3 sub-steps"


class ChatwootAdapter(TicketingProvider):
    """Chatwoot implementation of TicketingProvider."""

    provider_name = "chatwoot"

    def __init__(
        self,
        settings: Settings,
        *,
        client: ChatwootClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or ChatwootClient(settings)

    async def create_ticket(self, request: CreateTicketRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def update_status(self, request: UpdateStatusRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def add_comment(self, request: AddCommentRequest) -> None:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def add_note(self, request: AddNoteRequest) -> None:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def assign_agent(self, request: AssignAgentRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def add_tags(self, request: AddTagsRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def get_or_create_contact(self, request: CreateContactRequest) -> StandardContact:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        raise NotImplementedError(_TASK_1_3_REMAINING)

    async def health_check(self) -> ProviderHealth:
        """Validate config and probe Chatwoot Application API (`GET /api`)."""
        missing = missing_config_fields(self._settings)
        if missing:
            return ProviderHealth(
                healthy=False,
                provider=self.provider_name,
                message=f"Missing configuration: {', '.join(missing)}",
            )

        try:
            latency_ms = await self._client.ping()
        except ChatwootAuthError as exc:
            return ProviderHealth(
                healthy=False,
                provider=self.provider_name,
                message=str(exc.message),
            )
        except (ChatwootConfigError, ChatwootAPIError) as exc:
            return ProviderHealth(
                healthy=False,
                provider=self.provider_name,
                message=str(exc.message),
            )

        return ProviderHealth(
            healthy=True,
            provider=self.provider_name,
            message="Chatwoot Application API reachable",
            latency_ms=round(latency_ms, 2),
        )
