# Step 0.3 — KB Content Audit + MVP List

**Goal:** Turn 3–6 months of WhatsApp support history into the **top-30 article MVP list** for Phase 2 KB work.

**Hard gate:** This step gates Phase 2 KB article authoring — it does **not** block Phase 1.

## What you need to provide

1. **WhatsApp export** — 3–6 months of support chat history (JSON or CSV)
2. **Article authors** — comma-separated names for round-robin assignment on the MVP sheet

## Supported input formats

### JSON

```json
{
  "messages": [
    {"text": "Printer offline aa raha hai", "sender": "customer", "timestamp": "2026-01-15T10:00:00Z"},
    {"text": "Orders not syncing", "sender": "customer"}
  ]
}
```

Or a plain array: `[{"text": "..."}, ...]`

### CSV

Must have a message body column named one of: `text`, `body`, `message`, `content`, `Message`.  
Override with `--text-column`.

## Run

```bash
# Production run (your WhatsApp export)
python run_audit.py --input /path/to/whatsapp_export.json --authors "Ali,Sara,Ehtisham"

# Demo run (bundled sample — tests categorizer only, NOT production data)
python run_audit.py --demo
```

## Output

Written to `results/`:

| File | Contents |
|------|----------|
| `mvp_articles_*.csv` | Top-30 MVP list with columns: rank, issue_title, category, frequency, existing_doc, author, roman_urdu_needed, notes |
| `frequency_report_*.json` | Category counts + ranked issues with sample messages |

## Categories

`billing` · `printer` · `crash` · `login` · `menu` · `network` · `general`

Sync-related messages are bucketed under `network`.

## MVP CSV columns

| Column | Description |
|--------|-------------|
| `issue_title` | Normalized issue name from keyword clustering |
| `category` | One of the six categories |
| `frequency` | Message count matching this issue |
| `existing_doc` | Y/N — fill manually if internal docs exist |
| `author` | Assigned from `--authors` round-robin |
| `roman_urdu_needed` | Y/N — auto-detected from sample messages |
| `notes` | Free text |

## After running

1. Review top-30 list with support team
2. Fill `existing_doc` column manually
3. Adjust authors if needed
4. Sign off in `docs/PROGRESS.md`
