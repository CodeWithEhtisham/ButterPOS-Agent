"""Chatwoot adapter — implements TicketingProvider (Task 1.3).

Platform-specific Chatwoot API calls live here only.
"""

from __future__ import annotations

from datetime import datetime

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
from app.providers.ticketing.chatwoot.contacts import get_or_create_contact as chatwoot_get_or_create_contact
from app.providers.ticketing.chatwoot.conversations import (
    add_conversation_labels,
    append_conversation_labels,
    assign_conversation_agent,
    build_source_id,
    create_conversation,
    get_conversation,
    list_conversations_updated_since,
    parse_assignee_id,
    parse_contact_id,
    parse_conversation_id,
    send_conversation_message,
    set_conversation_custom_attributes,
    toggle_conversation_status,
)
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError, ChatwootAuthError, ChatwootConfigError
from app.providers.ticketing.chatwoot.mappers import (
    STANDARD_STATUS_ATTRIBUTE,
    conversation_to_standard_ticket,
    standard_status_to_chatwoot,
    unwrap_conversation,
)

from app.providers.ticketing.chatwoot.webhooks import (
    parse_chatwoot_webhook,
    register_account_webhook,
    verify_chatwoot_webhook,
)


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
        """Open a Chatwoot conversation for an existing contact."""
        if not self._settings.chatwoot_inbox_id:
            raise ChatwootConfigError("CHATWOOT_INBOX_ID is not configured")

        contact_id = parse_contact_id(request.provider_contact_id)
        source_id = build_source_id(contact_id, request.metadata)
        custom_attributes = request.metadata.get("custom_attributes")
        if not isinstance(custom_attributes, dict):
            custom_attributes = None
        if request.subject and custom_attributes is None:
            custom_attributes = {"subject": request.subject}
        elif request.subject and custom_attributes is not None:
            custom_attributes = {**custom_attributes, "subject": request.subject}

        raw = await create_conversation(
            self._client,
            contact_id=contact_id,
            source_id=source_id,
            custom_attributes=custom_attributes,
        )
        ticket = conversation_to_standard_ticket(
            raw,
            subject=request.subject,
            extra_metadata=dict(request.metadata),
        )
        ticket.metadata["source_id"] = source_id

        conversation_id = int(ticket.provider_ticket_id)

        if request.initial_message:
            await send_conversation_message(
                self._client,
                conversation_id,
                content=request.initial_message,
                private=False,
            )

        if request.tags:
            await add_conversation_labels(self._client, conversation_id, request.tags)
            ticket.tags = list(request.tags)

        return ticket

    async def get_ticket(self, provider_ticket_id: str) -> StandardTicket:
        """Fetch a conversation by Chatwoot id."""
        conversation_id = parse_conversation_id(provider_ticket_id)
        raw = await get_conversation(self._client, conversation_id)
        return conversation_to_standard_ticket(raw)

    async def update_status(self, request: UpdateStatusRequest) -> StandardTicket:
        """Toggle Chatwoot status and persist canonical StandardStatus in custom_attributes."""
        conversation_id = parse_conversation_id(request.provider_ticket_id)
        chatwoot_status = standard_status_to_chatwoot(request.status)

        await toggle_conversation_status(
            self._client,
            conversation_id,
            status=chatwoot_status,
        )

        raw = await get_conversation(self._client, conversation_id)
        conversation = unwrap_conversation(raw)
        existing_attrs = conversation.get("custom_attributes")
        if not isinstance(existing_attrs, dict):
            existing_attrs = {}
        merged_attrs = {
            **existing_attrs,
            STANDARD_STATUS_ATTRIBUTE: request.status.value,
        }
        await set_conversation_custom_attributes(
            self._client,
            conversation_id,
            merged_attrs,
        )

        updated = await get_conversation(self._client, conversation_id)
        return conversation_to_standard_ticket(updated)

    async def add_comment(self, request: AddCommentRequest) -> None:
        """Post a public AI reply visible to the customer."""
        conversation_id = parse_conversation_id(request.provider_ticket_id)
        content_type = str(request.metadata.get("content_type", "text"))
        content_attributes = request.metadata.get("content_attributes")
        if content_attributes is not None and not isinstance(content_attributes, dict):
            content_attributes = None
        await send_conversation_message(
            self._client,
            conversation_id,
            content=request.body,
            private=False,
            content_type=content_type,
            content_attributes=content_attributes,
        )

    async def add_note(self, request: AddNoteRequest) -> None:
        """Post an internal handoff note — agent-only, not visible to customer."""
        conversation_id = parse_conversation_id(request.provider_ticket_id)
        await send_conversation_message(
            self._client,
            conversation_id,
            content=request.body,
            private=True,
        )

    async def assign_agent(self, request: AssignAgentRequest) -> StandardTicket:
        """Assign conversation to a Chatwoot agent user."""
        conversation_id = parse_conversation_id(request.provider_ticket_id)
        assignee_id = parse_assignee_id(request.assignee_id)
        await assign_conversation_agent(self._client, conversation_id, assignee_id)
        raw = await get_conversation(self._client, conversation_id)
        return conversation_to_standard_ticket(raw)

    async def add_tags(self, request: AddTagsRequest) -> StandardTicket:
        """Append classification labels to a conversation."""
        conversation_id = parse_conversation_id(request.provider_ticket_id)
        merged_tags = await append_conversation_labels(
            self._client,
            conversation_id,
            request.tags,
        )
        raw = await get_conversation(self._client, conversation_id)
        ticket = conversation_to_standard_ticket(raw)
        ticket.tags = merged_tags
        return ticket

    async def get_or_create_contact(self, request: CreateContactRequest) -> StandardContact:
        """Map ButterPOS user to Chatwoot contact — filter/search then create."""
        if not self._settings.chatwoot_inbox_id:
            raise ChatwootConfigError("CHATWOOT_INBOX_ID is not configured")
        return await chatwoot_get_or_create_contact(self._client, request)

    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """Validate Chatwoot HMAC signature (X-Chatwoot-Signature + Timestamp)."""
        return verify_chatwoot_webhook(
            raw_body,
            headers,
            self._settings.chatwoot_webhook_secret,
            max_age_seconds=self._settings.chatwoot_webhook_max_age_seconds,
        )

    async def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> StandardEvent:
        """Map Chatwoot webhook JSON to StandardEvent (event-specific parsers)."""
        _ = headers  # reserved for delivery-id logging in Task 1.4
        return parse_chatwoot_webhook(raw_body)

    async def register_webhook(
        self,
        callback_url: str,
        *,
        subscriptions: list[str] | None = None,
    ) -> dict:
        """Register account webhook in Chatwoot — save returned secret to CHATWOOT_WEBHOOK_SECRET."""
        resolved = subscriptions or self._settings.chatwoot_webhook_subscription_list()
        return await register_account_webhook(
            self._client,
            callback_url,
            subscriptions=resolved,
        )

    async def list_tickets_updated_since(self, since: datetime) -> list[StandardTicket]:
        """Filter Chatwoot conversations updated after `since` for configured inbox."""
        raw_items = await list_conversations_updated_since(self._client, since)
        return [conversation_to_standard_ticket(item) for item in raw_items]

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
