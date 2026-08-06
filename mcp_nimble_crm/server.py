"""MCP server for Nimble CRM.

Thin layer over NimbleClient — reads env vars, defines tools,
formats responses as JSON strings.
"""

import json
import logging
import os

from mcp.server.fastmcp import FastMCP

from .client import NimbleClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "nimble-crm",
    instructions=(
        "Nimble CRM MCP server for managing contacts, deals, deal "
        "pipelines, notes, tasks, tags, and message drafts. Use "
        "list/search tools to find records, create/update tools to "
        "modify them, and note/task tools for activity tracking."
    ),
)

_client: NimbleClient | None = None


def _get_client() -> NimbleClient:
    global _client
    if _client is None:
        _client = NimbleClient(
            api_key=os.environ.get("NIMBLE_API_KEY", ""),
        )
    return _client


# ── User / Account ──────────────────────────────────────────────────


@mcp.tool()
def get_myself() -> str:
    """Get current authenticated Nimble user info and account details."""
    try:
        client = _get_client()
        result = client.get_myself()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Contacts ────────────────────────────────────────────────────────


@mcp.tool()
def list_contacts(
    record_type: str = "all",
    keyword: str = "",
    per_page: int = 30,
    page: int = 1,
) -> str:
    """List contacts with optional keyword search.

    Args:
        record_type: Filter by 'person', 'company', or 'all'.
        keyword: Simple search across indexed fields (name, email, etc).
        per_page: Results per page (default 30).
        page: Page number (starts at 1).
    """
    try:
        client = _get_client()
        result = client.list_contacts(
            record_type=record_type,
            keyword=keyword or None,
            per_page=per_page,
            page=page,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def search_contacts(
    query_json: str,
    per_page: int = 30,
    page: int = 1,
) -> str:
    """Search contacts with advanced query.

    Args:
        query_json: JSON string with search criteria.
            Format: {"and": [{"field name": {"operator": "value"}}]}
            Operators: is, is_not, contains, does_not_contain,
                       is_empty, is_not_empty, range.
            Example: {"and": [{"first name": {"is": "Jack"}},
                              {"company name": {"contains": "Acme"}}]}
        per_page: Results per page (default 30).
        page: Page number (starts at 1).
    """
    try:
        client = _get_client()
        query = json.loads(query_json)
        result = client.search_contacts(query, per_page=per_page, page=page)
        return json.dumps(result, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid query JSON: {e}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_contact(contact_id: str) -> str:
    """Get a single contact by ID with all fields and tags.

    Args:
        contact_id: The Nimble contact ID.
    """
    try:
        client = _get_client()
        result = client.get_contact(contact_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def create_contact(
    record_type: str,
    first_name: str = "",
    last_name: str = "",
    company_name: str = "",
    email: str = "",
    email_modifier: str = "work",
    phone: str = "",
    phone_modifier: str = "mobile",
    tags: str = "",
) -> str:
    """Create a new contact (person or company).

    Args:
        record_type: 'person' or 'company'.
        first_name: First name (for person records).
        last_name: Last name (for person records).
        company_name: Company name (required for company records).
        email: Email address.
        email_modifier: Email type: 'work', 'personal', or 'other'.
        phone: Phone number.
        phone_modifier: Phone type: 'work', 'home', 'mobile', 'main', 'other'.
        tags: Comma-separated tags (max 5 on creation).
    """
    try:
        client = _get_client()
        fields: dict = {}
        if first_name:
            fields["first name"] = [{"value": first_name, "modifier": ""}]
        if last_name:
            fields["last name"] = [{"value": last_name, "modifier": ""}]
        if company_name:
            fields["company name"] = [{"value": company_name, "modifier": ""}]
        if email:
            fields["email"] = [{"value": email, "modifier": email_modifier}]
        if phone:
            fields["phone"] = [{"value": phone, "modifier": phone_modifier}]

        result = client.create_contact(
            record_type=record_type,
            fields=fields,
            tags=tags or None,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def update_contact(
    contact_id: str,
    fields_json: str,
    replace: bool = False,
) -> str:
    """Update an existing contact's fields.

    Args:
        contact_id: The Nimble contact ID.
        fields_json: JSON string of fields to update.
            Format: {"field name": [{"value": "val", "modifier": "mod"}]}
            Example: {"email": [{"value": "new@example.com", "modifier": "work"}]}
            Set a field to null to remove all values for it.
        replace: If true, replaces all values for each field type.
                 If false, merges with existing values.
    """
    try:
        client = _get_client()
        fields = json.loads(fields_json)
        result = client.update_contact(
            contact_id, fields=fields, replace=replace,
        )
        return json.dumps(result, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid fields JSON: {e}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def delete_contacts(contact_ids: str) -> str:
    """Delete one or more contacts by ID.

    Args:
        contact_ids: Comma-separated contact IDs to delete.
    """
    try:
        client = _get_client()
        ids = [cid.strip() for cid in contact_ids.split(",")]
        result = client.delete_contacts(ids)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Notes ───────────────────────────────────────────────────────────


@mcp.tool()
def list_notes(
    contact_id: str,
    per_page: int = 5,
    page: int = 1,
) -> str:
    """List notes for a specific contact.

    Args:
        contact_id: The Nimble contact ID.
        per_page: Results per page (default 5).
        page: Page number (starts at 1).
    """
    try:
        client = _get_client()
        result = client.list_notes(contact_id, per_page=per_page, page=page)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_note(note_id: str) -> str:
    """Get a single note by ID.

    Args:
        note_id: The Nimble note ID.
    """
    try:
        client = _get_client()
        result = client.get_note(note_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def create_note(
    contact_ids: str,
    note: str,
    note_preview: str = "",
) -> str:
    """Create a note attached to one or more contacts.

    Args:
        contact_ids: Comma-separated contact IDs (1-10).
        note: Full note text (can contain HTML).
        note_preview: Short plain-text preview. If empty, first 100 chars of note are used.
    """
    try:
        client = _get_client()
        ids = [cid.strip() for cid in contact_ids.split(",")]
        preview = note_preview or note[:100]
        result = client.create_note(ids, note, preview)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def update_note(
    note_id: str,
    contact_ids: str,
    note: str,
    note_preview: str = "",
) -> str:
    """Update an existing note.

    Args:
        note_id: The Nimble note ID.
        contact_ids: Comma-separated contact IDs (1-10).
        note: Updated full note text.
        note_preview: Updated short preview. If empty, first 100 chars of note are used.
    """
    try:
        client = _get_client()
        ids = [cid.strip() for cid in contact_ids.split(",")]
        preview = note_preview or note[:100]
        result = client.update_note(note_id, ids, note, preview)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def delete_note(note_id: str) -> str:
    """Delete a note by ID.

    Args:
        note_id: The Nimble note ID.
    """
    try:
        client = _get_client()
        result = client.delete_note(note_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Tags ────────────────────────────────────────────────────────────


@mcp.tool()
def replace_tags(contact_id: str, tags: str) -> str:
    """Replace all tags on a contact.

    WARNING: This is a full replace — tags not in the list will be REMOVED.
    To add a tag, first get current tags with get_contact, then include
    all existing tags plus the new one.

    Args:
        contact_id: The Nimble contact ID.
        tags: Comma-separated list of tags to set.
    """
    try:
        client = _get_client()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        result = client.replace_tags(contact_id, tag_list)
        return json.dumps({"status": "ok", "tags_set": tag_list})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Tasks ───────────────────────────────────────────────────────────


@mcp.tool()
def create_task(
    subject: str,
    notes: str = "",
    related_to: str = "",
    due_date: str = "",
) -> str:
    """Create a task in Nimble CRM.

    Args:
        subject: Task title (2-128 chars).
        notes: Additional task notes.
        related_to: Comma-separated contact IDs to associate with the task.
        due_date: Due date in YYYY-MM-DDTHH:MM:SS format.
    """
    try:
        client = _get_client()
        contact_ids = (
            [cid.strip() for cid in related_to.split(",") if cid.strip()]
            if related_to else None
        )
        result = client.create_task(
            subject=subject,
            notes=notes or None,
            related_to=contact_ids,
            due_date=due_date or None,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Deals ───────────────────────────────────────────────────────────


@mcp.tool()
def list_deals(
    per_page: int = 30,
    page: int = 1,
    pipeline_id: str = "",
    stage_id: str = "",
    owner_id: str = "",
) -> str:
    """List all deals in Nimble CRM.

    Args:
        per_page: Results per page (default 30).
        page: Page number (starts at 1).
        pipeline_id: Filter to deals in a specific pipeline.
        stage_id: Filter to deals in a specific pipeline stage.
        owner_id: Filter to deals owned by a specific user.
    """
    try:
        client = _get_client()
        result = client.list_deals(
            per_page=per_page,
            page=page,
            pipeline_id=pipeline_id or None,
            stage_id=stage_id or None,
            owner_id=owner_id or None,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_deal(deal_id: str) -> str:
    """Get a single deal by ID.

    Args:
        deal_id: The Nimble deal ID.
    """
    try:
        client = _get_client()
        result = client.get_deal(deal_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def create_deal(
    deal_name: str,
    amount: str = "",
    stage: str = "",
    probability: str = "",
    expected_close_date: str = "",
    description: str = "",
    tags: str = "",
    pipeline_id: str = "",
) -> str:
    """Create a new deal in Nimble CRM.

    Args:
        deal_name: Name of the deal (required).
        amount: Deal value/amount.
        stage: Pipeline stage name.
        probability: Win probability percentage.
        expected_close_date: Expected close date (YYYY-MM-DD).
        description: Deal description.
        tags: Comma-separated tags.
        pipeline_id: Pipeline ID to place the deal in.
    """
    try:
        client = _get_client()
        fields: dict = {
            "deal name": [{"value": deal_name}],
        }
        if amount:
            fields["amount"] = [{"value": amount}]
        if stage:
            fields["stage"] = [{"value": stage}]
        if probability:
            fields["probability"] = [{"value": probability}]
        if expected_close_date:
            fields["expected close date"] = [{"value": expected_close_date}]
        if description:
            fields["description"] = [{"value": description}]

        result = client.create_deal(
            fields=fields,
            tags=tags or None,
            pipeline_id=pipeline_id or None,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def update_deal(deal_id: str, fields_json: str) -> str:
    """Update an existing deal.

    Args:
        deal_id: The Nimble deal ID.
        fields_json: JSON string of fields to update.
            Format: {"field name": [{"value": "val"}]}
            Example: {"amount": [{"value": "75000"}],
                      "stage": [{"value": "Negotiation"}]}
    """
    try:
        client = _get_client()
        fields = json.loads(fields_json)
        result = client.update_deal(deal_id, fields)
        return json.dumps(result, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid fields JSON: {e}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def delete_deal(deal_id: str) -> str:
    """Delete a deal by ID.

    Args:
        deal_id: The Nimble deal ID.
    """
    try:
        client = _get_client()
        result = client.delete_deal(deal_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def replace_deal_tags(deal_id: str, tags: str) -> str:
    """Replace all tags on a deal.

    WARNING: This is a full replace — tags not in the list will be REMOVED.

    Args:
        deal_id: The Nimble deal ID.
        tags: Comma-separated list of tags to set.
    """
    try:
        client = _get_client()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        client.replace_deal_tags(deal_id, tag_list)
        return json.dumps({"status": "ok", "tags_set": tag_list})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Deal Pipelines ──────────────────────────────────────────────────


@mcp.tool()
def list_deal_pipelines() -> str:
    """List all deal pipelines and their stages in Nimble CRM."""
    try:
        client = _get_client()
        result = client.list_deal_pipelines()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def create_deal_pipeline(name: str, stages: str) -> str:
    """Create a new deal pipeline in Nimble CRM.

    Args:
        name: Pipeline name.
        stages: Comma-separated ordered list of stage names.
    """
    try:
        client = _get_client()
        stage_list = [s.strip() for s in stages.split(",") if s.strip()]
        result = client.create_deal_pipeline(name, stage_list)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def update_deal_pipeline(
    pipeline_id: str,
    name: str = "",
    stages: str = "",
) -> str:
    """Update an existing deal pipeline.

    Args:
        pipeline_id: The Nimble pipeline ID.
        name: New pipeline name (leave blank to keep unchanged).
        stages: Comma-separated ordered list of stage names
            (leave blank to keep unchanged).
    """
    try:
        client = _get_client()
        stage_list = (
            [s.strip() for s in stages.split(",") if s.strip()]
            if stages else None
        )
        result = client.update_deal_pipeline(
            pipeline_id, name=name or None, stages=stage_list,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def delete_deal_pipeline(pipeline_id: str) -> str:
    """Delete a deal pipeline by ID.

    Args:
        pipeline_id: The Nimble pipeline ID.
    """
    try:
        client = _get_client()
        result = client.delete_deal_pipeline(pipeline_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Messages ─────────────────────────────────────────────────────────


@mcp.tool()
def list_messages(per_page: int = 30, page: int = 1) -> str:
    """List messages in Nimble CRM.

    Args:
        per_page: Results per page (default 30).
        page: Page number (starts at 1).
    """
    try:
        client = _get_client()
        result = client.list_messages(per_page=per_page, page=page)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def create_message_draft(
    subject: str,
    body: str,
    contact_ids: str = "",
    to: str = "",
) -> str:
    """Create a draft message in Nimble CRM.

    Args:
        subject: Message subject.
        body: Message body text.
        contact_ids: Comma-separated contact IDs to associate with the draft.
        to: Comma-separated recipient email addresses.
    """
    try:
        client = _get_client()
        contact_id_list = (
            [cid.strip() for cid in contact_ids.split(",") if cid.strip()]
            if contact_ids else None
        )
        to_list = (
            [addr.strip() for addr in to.split(",") if addr.strip()]
            if to else None
        )
        result = client.create_message_draft(
            subject=subject, body=body,
            contact_ids=contact_id_list, to=to_list,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Metadata ────────────────────────────────────────────────────────


@mcp.tool()
def list_contact_fields() -> str:
    """List all contact field metadata — tabs, groups, and fields.

    Returns the complete schema of available contact fields
    including custom fields, their types, and valid modifiers.
    """
    try:
        client = _get_client()
        result = client.list_contact_fields()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def list_deal_fields() -> str:
    """List all deal field metadata — standard and pipeline fields.

    Returns the complete schema of available deal fields,
    following the same pattern as contact field metadata.
    """
    try:
        client = _get_client()
        result = client.list_deal_fields()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
