# API Specification

REST API contract for the ButterPOS AI Support Agent middleware. All endpoints live under `/api/v1/`.

---

## Versioning

- Base path: `/api/v1/`
- Breaking changes increment the version prefix (`/api/v2/`); v1 remains until deprecated.
- Router aggregation: `app/api/v1/router.py`

---

## Endpoints

### Auth (Task 1.1.2)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/token` | Client credentials in body | Issue JWT access token |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Return authenticated `subject` |

#### `POST /api/v1/auth/token`

**Request body:**

```json
{
  "client_id": "butterpos-widget",
  "client_secret": "<API_CLIENT_SECRET>",
  "subject": "staff-user-123"
}
```

**Response `200`:**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:** `401` invalid credentials · `503` JWT or client config missing

#### `GET /api/v1/auth/me`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:**

```json
{
  "subject": "staff-user-123"
}
```

**Errors:** `401` missing, invalid, or expired token

---

## Request/response schemas

Pydantic models: `app/schemas/auth.py`

| Model | Purpose |
|-------|---------|
| `TokenRequest` | Token issuance input |
| `TokenResponse` | Token issuance output |
| `AuthenticatedSubject` | Resolved JWT subject |
| `ErrorResponse` | Standard error body |

---

## Status mappings

<!-- Task 1.1.5 / 1.3: StandardStatus (12-value enum) ↔ Chatwoot status mapping table. -->
