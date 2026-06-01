# MCP Integration

Model Context Protocol client contract for the ButterPOS AI Support Agent middleware.

---

## Ownership split

<!-- TBD Step 0.6: Backend teammate owns MCP server; this repo is MCP client only. -->

---

## Transport

<!-- TBD Step 0.6: Server URL, transport type (stdio/SSE/HTTP), connection lifecycle. -->

---

## Auth

<!-- TBD Step 0.6: Authentication method, credential storage, token refresh if applicable. -->

---

## Tool catalog

<!-- TBD Step 0.6: Tool names, descriptions, tier classification (read-only vs fix vs escalate). -->

---

## Request/response shapes

<!-- TBD Step 0.6: Input schemas, output schemas, error formats, example calls. -->

---

## LLM provider compatibility (Step 0.2)

Tool-calling in Step 0.6 must be validated against the **primary and fallback models chosen in D-9**. Requirements:

- Both models must support OpenAI-style `tools` / function-calling (used by MCP client bridge).
- Switching primary → fallback in config must fire the **same MCP tools with no code change** (D-4 portability rationale).
- When Gemini/Anthropic keys become available (D-8), repeat Step 0.6 validation for each new provider adapter before promoting to fallback.

**Primary/fallback models:** see D-9 in `DECISIONS.md` (pending live eval).
