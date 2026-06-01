# Chat Surface Capability Matrix — Step 0.1

**Inbox type assumed:** API Channel (middleware posts via Application API; tablet widget talks to middleware only).

**Latency target:** <5s round-trip (post message → read back).

| Feature | Content type | API research | Live spike | Middleware notes |
|---------|--------------|--------------|------------|------------------|
| Plain text messages | `text` | **Supported** — standard POST | _Pending credentials_ | Baseline agent replies |
| Quick replies | `input_select` | **Supported** — `content_attributes.items[]` with `title`/`value` | _Pending credentials_ | Maps to playbook selection; webhook returns selected value |
| Action buttons | `cards` (postback) | **Supported** — `actions[].type: postback` with `payload` | _Pending credentials_ | Postback payload delivered via `message_created` webhook |
| Inline form | `form` | **Supported** — `content_attributes.items[]` field definitions | _Pending credentials_ | Collect branch ID, etc.; submission via webhook |
| CSAT / inline rating | `input_csat` | **Partial** — API inbox: send via agent API; response via public message PATCH with `submitted_values.csat_survey_response`, or redirect to `/survey/responses/{uuid}` | _Pending credentials_ | Tablet widget can render custom stars OR redirect to Chatwoot survey page |
| WhatsApp templates | `template_params` | N/A for API channel | Skip | Only for WhatsApp inboxes |

## Why widget → middleware → Chatwoot (not direct)

1. **Latency control** — middleware can cache, batch, and fall back without blocking the tablet UI on Chatwoot response times.
2. **Rich UI ownership** — middleware translates playbook steps into the correct Chatwoot `content_type`; widget stays thin.
3. **Decoupling** — agent loop, PII masking, and MCP tool calls run in middleware; Chatwoot remains system of record only.

## Sources

- [Create New Message](https://developers.chatwoot.com/api-reference/messages/create-new-message)
- [Interactive messages guide](https://chatwoot.com/hc/user-guide/articles/1677689344-how-to-use-interactive-messages)
- [CSAT via Message API (API channel)](https://github.com/chatwoot/chatwoot/pull/6470)
