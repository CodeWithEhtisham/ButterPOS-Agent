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

**Task 1.1.7** — Mandatory before **every** third-party LLM call (OpenRouter → OpenAI / Anthropic / Gemini). V1 does not run self-hosted models; customer PII must not reach paid providers in cleartext.

### Why it matters

Data routed through OpenRouter still leaves your infrastructure and may hit multiple vendors. Masking is load-bearing for compliance and customer trust until Ollama/self-hosted is evaluated post-V1 (D-6).

### Flow

1. **Before LLM:** `PIIMasker.mask(text)` or `mask_messages()` replaces detected entities with tokens like `[PII:EMAIL_ADDRESS:a1b2c3d4]`.
2. **Redis map:** `pii:token:{id}` → original value, TTL **24 hours** (`PII_TOKEN_TTL_SECONDS=86400`).
3. **After LLM:** `PIIMasker.unmask(response)` restores originals for display to staff / Chatwoot public reply.
4. **Never log** cleartext PII or Redis token values.

### Detected entity types

| Type | Examples |
|------|----------|
| `PHONE_NUMBER` | `0301-1234567`, international formats |
| `EMAIL_ADDRESS` | `user@domain.com` |
| `CREDIT_CARD` | 13–16 digit card numbers |
| `IBAN_CODE` | Bank IBANs |
| `US_SSN` | `123-45-6789` |
| `PERSON` | Capitalized multi-word names (regex baseline) |
| + Presidio types when spaCy model installed | `NATIONAL_ID`, `US_PASSPORT`, etc. |

Detection: **regex baseline** (always on) with optional **Presidio** enrichment when spaCy is available (`build_pii_detector()`).

### Usage (agent loop — Phase 2)

```python
from app.api.deps import pii_masker_dep

masker = pii_masker_dep()
masked_msgs, _ = await masker.mask_messages(conversation_messages)
# ... call LLMProvider with masked_msgs ...
reply = await masker.unmask(llm_response.content)
```

Implementation: `app/core/pii/masker.py`, `app/core/pii/store.py`, `app/core/pii/detector.py`.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | — | Required for production token store |
| `PII_TOKEN_TTL_SECONDS` | `86400` | Mask token TTL (24h) |
| `PII_REDIS_KEY_PREFIX` | `pii:token:` | Redis key prefix |

### Optional: Presidio + spaCy

For stronger name/ID detection in production:

```bash
python -m spacy download en_core_web_lg
```

If spaCy is missing, the service falls back to regex patterns automatically.
