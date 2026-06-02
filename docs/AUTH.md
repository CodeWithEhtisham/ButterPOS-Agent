# Authentication & Authorization

Security model for API access, webhooks, tiered actions, and PII handling.

---

## JWT

**Task 1.1.2** — HS256 access tokens for middleware API clients (tablet widget, internal services).

### Flow

1. Client calls `POST /api/v1/auth/token` with `client_id`, `client_secret`, and `subject` (staff/user id for the session).
2. Middleware validates credentials against `API_CLIENT_ID` / `API_CLIENT_SECRET` in `.env`.
3. Returns `{ access_token, token_type: "bearer", expires_in }` signed with `JWT_SECRET`.
4. Protected routes require `Authorization: Bearer <token>`.
5. Use `GET /api/v1/auth/me` to verify token validity and read the embedded `subject`.

### Token claims

| Claim | Description |
|-------|-------------|
| `sub` | User or session identifier (from token request) |
| `iat` | Issued-at (unix) |
| `exp` | Expiry (unix) |
| `token_type` | Always `access` |

### FastAPI dependency

```python
from app.api.deps import get_current_subject

@router.get("/protected")
def protected(subject: Annotated[AuthenticatedSubject, Depends(get_current_subject)]):
    ...
```

Implementation: `app/core/security.py`, `app/api/deps.py`.

### Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Yes | HS256 signing secret — use a long random value |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Default `60` |
| `API_CLIENT_ID` | Yes | Bootstrap client id (e.g. `butterpos-widget`) |
| `API_CLIENT_SECRET` | Yes | Bootstrap client secret |

User/password login against Postgres users arrives with Task 1.2+; until then, client credentials + explicit `subject` identify the session.

---

## Webhook signatures

<!-- Task 1.3 / 1.4: Chatwoot HMAC verification; signing secret = CHATWOOT_WEBHOOK_SECRET. -->

---

## Tiered authorization

<!-- Phase 2: Tier 1 read-only auto; Tier 2 fix on high-confidence/soft-confirm; Tier 3 always escalate. -->

---

## PII masking

<!-- Task 1.1.7: Detect & mask phone, email, financial, ID, name before LLM; reversible via Redis (24h TTL). -->
