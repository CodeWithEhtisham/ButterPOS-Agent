"""Chatwoot contact API helpers — lookup and create."""

from __future__ import annotations

import logging
from typing import Any

from app.models.standard import CreateContactRequest, StandardContact
from app.providers.ticketing.chatwoot.client import ChatwootClient
from app.providers.ticketing.chatwoot.errors import ChatwootAPIError
from app.providers.ticketing.chatwoot.mappers import contact_to_standard_contact, unwrap_contact

logger = logging.getLogger(__name__)


def _contact_matches_request(contact: dict[str, Any], request: CreateContactRequest) -> bool:
    if request.external_user_id and contact.get("identifier") == request.external_user_id:
        return True
    if request.email and contact.get("email") == request.email:
        return True
    phone = contact.get("phone_number") or contact.get("phone")
    if request.phone and phone == request.phone:
        return True
    return False


async def filter_contacts(
    client: ChatwootClient,
    *,
    attribute_key: str,
    value: str,
) -> list[dict[str, Any]]:
    """POST /contacts/filter — exact match on a standard attribute."""
    response = await client.request(
        "POST",
        client.account_path("/contacts/filter"),
        json={
            "payload": [
                {
                    "attribute_key": attribute_key,
                    "filter_operator": "equal_to",
                    "values": [value],
                },
            ],
        },
    )
    data = response.json()
    payload = data.get("payload", [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


async def search_contacts(client: ChatwootClient, query: str) -> list[dict[str, Any]]:
    """GET /contacts/search — server-side match on name, identifier, email, phone."""
    response = await client.request(
        "GET",
        client.account_path("/contacts/search"),
        params={"q": query},
    )
    data = response.json()
    payload = data.get("payload", [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


async def find_contact(
    client: ChatwootClient,
    request: CreateContactRequest,
) -> dict[str, Any] | None:
    """Resolve an existing Chatwoot contact by identifier, email, or phone."""
    if request.external_user_id:
        matches = await filter_contacts(
            client,
            attribute_key="identifier",
            value=request.external_user_id,
        )
        if matches:
            return unwrap_contact(matches[0])

    if request.email:
        matches = await filter_contacts(client, attribute_key="email", value=request.email)
        for item in matches:
            contact = unwrap_contact(item)
            if _contact_matches_request(contact, request):
                return contact

    lookup_queries: list[str] = []
    if request.external_user_id:
        lookup_queries.append(request.external_user_id)
    if request.email:
        lookup_queries.append(request.email)
    if request.phone:
        lookup_queries.append(request.phone)

    for query in lookup_queries:
        for item in await search_contacts(client, query):
            contact = unwrap_contact(item)
            if _contact_matches_request(contact, request):
                return contact

    return None


async def create_contact(
    client: ChatwootClient,
    request: CreateContactRequest,
) -> dict[str, Any]:
    """POST /contacts — create contact in the configured API inbox."""
    payload: dict[str, Any] = {"inbox_id": client.inbox_id}
    if request.name:
        payload["name"] = request.name
    if request.email:
        payload["email"] = request.email
    if request.phone:
        payload["phone_number"] = request.phone
    if request.external_user_id:
        payload["identifier"] = request.external_user_id

    custom_attributes = request.metadata.get("custom_attributes")
    if isinstance(custom_attributes, dict):
        payload["custom_attributes"] = custom_attributes

    response = await client.request(
        "POST",
        client.account_path("/contacts"),
        json=payload,
    )
    data = response.json()
    contact = unwrap_contact(data if isinstance(data, dict) else {})
    logger.info(
        "Chatwoot contact created",
        extra={"contact_id": contact.get("id"), "identifier": request.external_user_id},
    )
    return data if isinstance(data, dict) else {}


async def get_or_create_contact(
    client: ChatwootClient,
    request: CreateContactRequest,
) -> StandardContact:
    """Find contact by ButterPOS identifiers or create in the API inbox."""
    if not (request.external_user_id or request.email or request.phone):
        raise ChatwootAPIError(
            "CreateContactRequest requires external_user_id, email, or phone",
            status_code=400,
        )

    existing = await find_contact(client, request)
    if existing:
        return contact_to_standard_contact(existing, extra_metadata=dict(request.metadata))

    created = await create_contact(client, request)
    return contact_to_standard_contact(created, extra_metadata=dict(request.metadata))
