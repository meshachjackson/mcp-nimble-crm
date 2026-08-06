<!-- mcp-name: io.github.meshachjackson/mcp-nimble-crm -->

# mcp-nimble-crm

MCP server for the [Nimble CRM](https://www.nimble.com/) API — manage contacts, deals, deal pipelines, notes, tasks, tags, and message drafts from Claude, Cursor, Zed, or any MCP client.

This project began as a fork of [cphoskins/nimble-crm-mcp](https://github.com/cphoskins/nimble-crm-mcp) (MIT licensed), extended with deal pipeline management, single-deal lookups, deal tags, deal field metadata, and message drafts — plus ongoing maintenance across multiple machines/environments.

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

### Deals
- **list_deals** — List deals, with optional filters for pipeline, stage, and owner
- **get_deal** — Get a single deal by ID
- **create_deal** — Create a deal with name, amount, stage, probability, etc.
- **update_deal** — Update deal fields
- **delete_deal** — Delete a deal
- **replace_deal_tags** — Replace all tags on a deal (full replace, not additive)

### Deal Pipelines
- **list_deal_pipelines** — List all deal pipelines and their stages
- **create_deal_pipeline** — Create a new pipeline with ordered stages
- **update_deal_pipeline** — Rename a pipeline or update its stages
- **delete_deal_pipeline** — Delete a pipeline

### Messages
- **list_messages** — List messages
- **create_message_draft** — Create a draft message linked to contacts and/or recipients

### Metadata
- **list_contact_fields** — List all contact field metadata (tabs, groups, fields, types)
- **list_deal_fields** — List all deal field metadata (standard and pipeline fields)

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
