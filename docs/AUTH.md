# Authentication & Authorization

Security model for API access, webhooks, tiered actions, and PII handling.

---

## JWT

<!-- TBD: Token creation, validation, FastAPI dependencies, protected routes. -->

---

## Webhook signatures

<!-- TBD: Chatwoot HMAC verification; signing secret storage. -->

---

## Tiered authorization

<!-- TBD: Tier 1 read-only auto; Tier 2 fix on high-confidence/soft-confirm; Tier 3 always escalate. -->

---

## PII masking

<!-- TBD: Detect & mask phone, email, financial, ID, name before LLM; reversible via Redis (24h TTL). -->
