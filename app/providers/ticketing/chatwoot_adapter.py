"""Chatwoot adapter — implements TicketingProvider (Task 1.3).

Platform-specific Chatwoot API calls live here only.
Method bodies are filled in Task 1.3; skeleton for factory wiring.
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

_TASK_1_3 = "Not implemented — completed in Task 1.3 (ChatwootAdapter)"


class ChatwootAdapter(TicketingProvider):
    """Chatwoot implementation of TicketingProvider."""

    provider_name = "chatwoot"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_ticket(self, request: CreateTicketRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3)

    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3)

    async def update_status(self, request: UpdateStatusRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3)

    async def add_comment(self, request: AddCommentRequest) -> None:
        raise NotImplementedError(_TASK_1_3)

    async def add_note(self, request: AddNoteRequest) -> None:
        raise NotImplementedError(_TASK_1_3)

    async def assign_agent(self, request: AssignAgentRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3)

    async def add_tags(self, request: AddTagsRequest) -> StandardTicket:
        raise NotImplementedError(_TASK_1_3)

    async def get_or_create_contact(self, request: CreateContactRequest) -> StandardContact:
        raise NotImplementedError(_TASK_1_3)

    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        raise NotImplementedError(_TASK_1_3)

    async def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        raise NotImplementedError(_TASK_1_3)

    async def health_check(self) -> ProviderHealth:
        """Config-only probe until Task 1.3 adds live API checks."""
        missing: list[str] = []
        if not self._settings.chatwoot_base_url:
            missing.append("CHATWOOT_BASE_URL")
        if not self._settings.chatwoot_api_token:
            missing.append("CHATWOOT_API_TOKEN")
        if not self._settings.chatwoot_account_id:
            missing.append("CHATWOOT_ACCOUNT_ID")

        if missing:
            return ProviderHealth(
                healthy=False,
                provider=self.provider_name,
                message=f"Missing configuration: {', '.join(missing)}",
            )

        return ProviderHealth(
            healthy=True,
            provider=self.provider_name,
            message="Configuration present; live API probe in Task 1.3",
        )
