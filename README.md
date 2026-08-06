<!-- mcp-name: io.github.meshachjackson/mcp-nimble-crm -->

# mcp-nimble-crm

MCP server for the [Nimble CRM](https://www.nimble.com/) API — manage contacts, deals, deal pipelines, notes, tasks, tags, fields metadata, and message drafts from Claude, Cursor, Zed, or any MCP client.

This project began as a fork of [cphoskins/nimble-crm-mcp](https://github.com/cphoskins/nimble-crm-mcp) (MIT licensed). It has since been rewritten against Nimble's official v1/v2 OpenAPI reference (readthedocs/Redocly spec) to correct and extend coverage: deals and deal pipelines now correctly target the **v2** API (`/api/v2/deals`), with full pipeline/stage/field/group/choice management, deal tags, deal notes, and lead pipeline transitions — plus the full v1 contacts-fields-metadata CRUD surface (tabs, groups, fields, choices) that the upstream project didn't cover. See `NIMBLE_API_REFERENCE.md` for the endpoint-by-endpoint source notes.

**Scope note:** binary file upload/download endpoints (deal files, contact avatar uploads via Azure Blob SDK) are intentionally not implemented — they require a separate multipart/Azure Blob integration outside a JSON REST client's scope.

> **Note on naming:** this is unrelated to `nimble-js-mcp` on npm, which is for [Nimbleway](https://nimbleway.com) (a web-scraping/data API company) — a different "Nimble" entirely.

## Installation

```bash
pip install mcp-nimble-crm
```

Or install from source:

```bash
git clone https://github.com/meshachjackson/mcp-nimble-crm.git
cd mcp-nimble-crm
pip install -e .
```

## Configuration

### Get your Nimble API Key

1. Log in to [Nimble](https://app.nimble.com/)
2. Go to **Settings** > **API Tokens** (or visit the [API Access](https://support.nimble.com/en/articles/502755-nimble-api-access) guide)
3. Generate an API key

### Claude Code

Add to your Claude Code MCP settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "nimble-crm": {
      "command": "mcp-nimble-crm",
      "env": {
        "NIMBLE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Generic MCP Client

```json
{
  "mcpServers": {
    "nimble-crm": {
      "command": "python",
      "args": ["-m", "mcp_nimble_crm.server"],
      "env": {
        "NIMBLE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Available Tools

### Contacts
- **list_contacts** — List contacts with optional keyword search and record type filter
- **search_contacts** — Advanced search with field-level operators (is, contains, range, etc.)
- **get_contact** — Get a single contact by ID with all fields and tags
- **create_contact** — Create a person or company contact with name, email, phone, tags
- **update_contact** — Update contact fields (merge or replace mode)
- **delete_contacts** — Delete one or more contacts by ID

### Notes
- **list_notes** — List notes for a specific contact
- **get_note** — Get a single note by ID
- **create_note** — Create a note attached to one or more contacts
- **update_note** — Update an existing note
- **delete_note** — Delete a note

### Tags
- **replace_tags** — Replace all tags on a contact (full replace, not additive)

### Tasks
- **create_task** — Create a task with subject, notes, due date, and related contacts

### Contacts Fields Metadata
- **list_contact_fields** — List all contact field metadata (tabs, groups, fields, types)
- **create_contact_field** / **update_contact_field** / **delete_contact_field** — Manage custom contact fields
- **create_contact_field_group** — Create a fields group
- **create_contact_field_tab** — Create a fields tab

### Contact Pipelines (Leads)
- **list_contact_pipelines** — List lead/contact pipelines visible to the user
- **move_lead_to_stage** — Move a lead into a pipeline stage
- **exit_lead_successful** / **exit_lead_unsuccessful** — Exit a lead as won/lost
- **undo_lead_transition** — Undo a recent won/lost transition

### Activities & Tasks
- **list_activities** — List pending or past activities, filterable by contact/deal
- **create_task** — Create a task with subject, notes, due date, related contacts/deals, and tags

### Deals (v2)
- **list_deals** — List the current user's deals
- **get_deal** — Get a single deal by ID
- **create_deal** — Create a deal (pipeline, stage, fields_values, owner, currency, tags)
- **update_deal** — Update deal fields, pipeline, stage, owner, or tags
- **delete_deal** — Delete a deal
- **get_won_deals_last_month** — Sum/count of deals won in the last month

### Deal Tags & Notes
- **list_deal_tags** / **add_tags_to_deals** / **rename_deal_tag** / **delete_deal_tag**
- **create_deal_note** / **update_deal_note** / **delete_deal_note**
- **list_deal_overdue_activities** — Overdue activities for a deal

### Deal Fields
- **list_deal_fields** — Standard + per-pipeline deal fields
- **list_deal_column_catalogue** — Deal column/column-group catalogue

### Deal Pipelines (v2)
- **list_deal_pipelines** / **get_deal_pipeline** / **create_deal_pipeline** / **update_deal_pipeline** / **delete_deal_pipeline**
- **list_pipeline_deals_by_stage** / **list_pipeline_deals_by_owner**
- **archive_deal_pipeline** / **unarchive_deal_pipeline** / **add_pipeline_lost_reason**
- **create_pipeline_stage** / **update_pipeline_stage** / **archive_pipeline_stage**

### Messages
- **list_message_drafts** — List draft messages
- **create_message_draft** — Create a draft message linked to recipients

### Account
- **get_myself** — Get current authenticated user info

## Development

```bash
# Clone and install
git clone https://github.com/meshachjackson/mcp-nimble-crm.git
cd mcp-nimble-crm
pip install -e .

# Run tests (no credentials needed — all mocked)
pytest tests/ -v

# Run integration tests against a live account (creates + cleans up real records)
NIMBLE_API_KEY=your-key pytest tests/test_integration.py -v

# Run the server locally
NIMBLE_API_KEY=your-key mcp-nimble-crm
```

## Releasing

```bash
./release.sh <version>
```

This bumps the version in `pyproject.toml`, `mcp_nimble_crm/__init__.py`, and `server.json`, commits, tags, and pushes. Publishing a GitHub Release for that tag triggers the PyPI publish workflow (`.github/workflows/publish.yml`).

## License

MIT — see [LICENSE](LICENSE). Includes portions originally from [cphoskins/nimble-crm-mcp](https://github.com/cphoskins/nimble-crm-mcp), also MIT licensed.
