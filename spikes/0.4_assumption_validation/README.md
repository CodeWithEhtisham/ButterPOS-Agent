# Step 0.4 — Assumption Validation (A1–A7)

**Goal:** Definitive Yes/No on every foundational assumption with evidence where automatable.

## Assumptions

| ID | Assumption | Auto-check |
|----|------------|------------|
| A1 | ButterPOS Android/tablet app codebase access | `BUTTERPOS_ANDROID_REPO` — local path or git URL |
| A2 | Restaurant → Branch → User data accessible | `DATABASE_URL` or `BUTTERPOS_DATA_EXPORT` |
| A3 | Billing/payment status source identifiable | `BILLING_API_URL` (+ optional `BILLING_API_TOKEN`) |
| A4 | Chatwoot runs locally via Docker | `CHATWOOT_*` env + health probe |
| A5 | MCP server owned by backend teammate | `MCP_SERVER_URL` (manual ownership ack) |
| A6 | WhatsApp export available for KB audit | `WHATSAPP_EXPORT_PATH` |
| A7 | Chat path: widget → middleware → Chatwoot | Architecture + Step 0.1 spike evidence |

## Run

```bash
cd spikes/0.4_assumption_validation
python verify_assumptions.py
```

Exit code `0` = no blocked/failed automated checks. `manual` items still need owner sign-off.

## Status meanings

| Status | Meaning |
|--------|---------|
| **verified** | Automated check passed with evidence |
| **manual** | Cannot fully auto-verify — owner must confirm |
| **blocked** | Required input missing (env var / file path) |
| **failed** | Check ran but did not pass |

## Optional `.env` keys for Step 0.4

```env
# A1
BUTTERPOS_ANDROID_REPO=/path/to/butterpos-android

# A2 (either)
DATABASE_URL=postgresql://readonly:pass@host:5432/butterpos
BUTTERPOS_DATA_EXPORT=/path/to/restaurants_export.json

# A3
BILLING_API_URL=https://api.example.com/billing/status
BILLING_API_TOKEN=

# A5 (Step 0.6 will fully validate)
MCP_SERVER_URL=

# A6
WHATSAPP_EXPORT_PATH=/path/to/whatsapp_export.json
```

Chatwoot vars (`CHATWOOT_*`) are reused from Step 0.1.

## Sign-off

After running, review `results/validation_report_*.json` and confirm manual items with project owner. Update `docs/DECISIONS.md` D-7 with evidence links.
