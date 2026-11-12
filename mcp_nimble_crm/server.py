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

_INSTRUCTIONS = (
    "Nimble CRM MCP server for managing contacts, deals, deal "
    "pipelines, notes, tasks, tags, fields metadata, and message "
    "drafts. Use list/search tools to find records, create/update "
    "tools to modify them, and note/task tools for activity "
    "tracking."
)


def _build_mcp() -> FastMCP:
    """Construct the FastMCP instance.

    In the default stdio mode this is a plain, auth-free server keyed by the
    NIMBLE_API_KEY environment variable. When NIMBLE_MCP_REMOTE is set (by
    the mcp-nimble-crm-remote entrypoint), the OAuth provider and transport
    settings are injected here, on the public constructor, so the remote
    package stays an optional dependency.
    """
    kwargs = {}
    if os.environ.get("NIMBLE_MCP_REMOTE"):
        from .remote.bootstrap import build_auth_kwargs

        kwargs = build_auth_kwargs()
    return FastMCP("nimble-crm", instructions=_INSTRUCTIONS, **kwargs)


mcp = _build_mcp()

_client: NimbleClient | None = None

# Remote mode installs a resolver returning the authenticated caller's own
# Nimble key; every tool call then acts as that user. None means single-user
# stdio mode, which falls through to the environment variable.
_key_resolver = None
_MAX_CACHED_CLIENTS = 256
_clients_by_key: dict[str, NimbleClient] = {}


def set_key_resolver(resolver) -> None:
    global _key_resolver
    _key_resolver = resolver


def _client_for_key(api_key: str) -> NimbleClient:
    client = _clients_by_key.get(api_key)
    if client is None:
        if len(_clients_by_key) >= _MAX_CACHED_CLIENTS:
            _clients_by_key.clear()
        client = NimbleClient(api_key=api_key)
        _clients_by_key[api_key] = client
    return client


def _get_client() -> NimbleClient:
    if _key_resolver is not None:
        api_key = _key_resolver()
        if api_key:
            return _client_for_key(api_key)
    global _client
    if _client is None:
        _client = NimbleClient(
            api_key=os.environ.get("NIMBLE_API_KEY", ""),
        )
    return _client


def _ok(result) -> str:
    return json.dumps(result, indent=2)


def _err(e: Exception) -> str:
    return json.dumps({"status": "error", "message": str(e)})


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# ── User / Account ──────────────────────────────────────────────


@mcp.tool()
def get_myself() -> str:
    """Get current authenticated Nimble user info and account details."""
    try:
        return _ok(_get_client().get_myself())
    except Exception as e:
        return _err(e)


# ── Contacts ────────────────────────────────────────────────────


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
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def search_contacts(
    query_json: str,
    per_page: int = 30,
    page: int = 1,
) -> str:
    """Search contacts with an advanced NSE query.

    Args:
        query_json: JSON string with search criteria.
            Format: {"and": [{"field name": {"operator": "value"}}]}
            Operators: is, is_not, contain, not_contain, starts_with,
                       is_empty, in, range, gt, gte, lt, lte,
                       in_the_last, not_in_the_last, day_month_range.
            Example: {"and": [{"first name": {"is": "Jack"}},
                              {"company name": {"contain": "Acme"}}]}
        per_page: Results per page (default 30).
        page: Page number (starts at 1).
    """
    try:
        client = _get_client()
        query = json.loads(query_json)
        result = client.search_contacts(query, per_page=per_page, page=page)
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid query JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_contact_ids(
    record_type: str = "all",
    keyword: str = "",
    per_page: int = 30,
    page: int = 1,
) -> str:
    """List contact IDs only (faster than a full contact listing).

    Args:
        record_type: Filter by 'person', 'company', or 'all'.
        keyword: Simple search across indexed fields.
        per_page: Results per page (default 30).
        page: Page number (starts at 1).
    """
    try:
        client = _get_client()
        result = client.list_contact_ids(
            record_type=record_type,
            keyword=keyword or None,
            per_page=per_page,
            page=page,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_contacts_by_ids(contact_ids: str) -> str:
    """Return standard contact listings for up to 30 explicit IDs.

    Args:
        contact_ids: Comma-separated contact IDs (max 30).
    """
    try:
        client = _get_client()
        result = client.get_contacts_by_ids(_csv(contact_ids))
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_contact(contact_id: str) -> str:
    """Get a single contact by ID with all fields and tags.

    Args:
        contact_id: The Nimble contact ID.
    """
    try:
        return _ok(_get_client().get_contact(contact_id))
    except Exception as e:
        return _err(e)


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
        return _ok(result)
    except Exception as e:
        return _err(e)


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
            Set a field to an empty list to remove all values for it.
        replace: If true, replaces all values for each field type.
                 If false, merges with existing values.
    """
    try:
        client = _get_client()
        fields = json.loads(fields_json)
        result = client.update_contact(
            contact_id, fields=fields, replace=replace,
        )
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid fields JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_contact(
    contact_id: str,
    deletion_method: str = "regular",
    cleanup_email_lists: bool = False,
) -> str:
    """Delete a single contact by ID.

    Args:
        contact_id: The Nimble contact ID.
        deletion_method: 'regular' (errors if relations block deletion)
            or 'force' (delete despite relations).
        cleanup_email_lists: If true, also remove matching email list entries.
    """
    try:
        client = _get_client()
        result = client.delete_contact(
            contact_id,
            deletion_method=deletion_method,
            cleanup_email_lists=cleanup_email_lists,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_contacts(contact_ids: str) -> str:
    """Delete one or more contacts by ID.

    Args:
        contact_ids: Comma-separated contact IDs to delete.
    """
    try:
        client = _get_client()
        result = client.delete_contacts(_csv(contact_ids))
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_contacts_by_query(
    query_json: str = "",
    keyword: str = "",
    record_type: str = "all",
    preflight_checks: bool = False,
) -> str:
    """Bulk-delete contacts matching an advanced query or keyword list.

    Requires bulk delete permission for the authenticated user.

    Args:
        query_json: JSON-encoded advanced search query. If provided,
            record_type is ignored by Nimble.
        keyword: Comma-separated list of keywords; contacts whose
            fields contain any of these values will be deleted.
        record_type: 'person', 'company', or 'all'.
        preflight_checks: If true, verify contacts are editable first.
    """
    try:
        client = _get_client()
        query = json.loads(query_json) if query_json else None
        result = client.delete_contacts_by_query(
            keyword=_csv(keyword) if keyword else None,
            query=query,
            record_type=record_type,
            preflight_checks=preflight_checks,
        )
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid query JSON: {e}"})
    except Exception as e:
        return _err(e)


# ── Notes ───────────────────────────────────────────────────────


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
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_note(note_id: str) -> str:
    """Get a single note by ID.

    Args:
        note_id: The Nimble note ID.
    """
    try:
        return _ok(_get_client().get_note(note_id))
    except Exception as e:
        return _err(e)


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
        ids = _csv(contact_ids)
        preview = note_preview or note[:100]
        result = client.create_note(ids, note, preview)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_contact_note(
    contact_id: str,
    note: str,
    note_preview: str = "",
) -> str:
    """Create a note attached to a single contact.

    Args:
        contact_id: The Nimble contact ID.
        note: Full note text.
        note_preview: Short preview. Defaults to the full note if omitted.
    """
    try:
        client = _get_client()
        result = client.create_contact_note(
            contact_id, note, note_preview=note_preview or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


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
        ids = _csv(contact_ids)
        preview = note_preview or note[:100]
        result = client.update_note(note_id, ids, note, preview)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_note(note_id: str) -> str:
    """Delete a note by ID.

    Args:
        note_id: The Nimble note ID.
    """
    try:
        return _ok(_get_client().delete_note(note_id))
    except Exception as e:
        return _err(e)


# ── Tags ────────────────────────────────────────────────────────


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
        tag_list = _csv(tags)
        client.replace_tags(contact_id, tag_list)
        return json.dumps({"status": "ok", "tags_set": tag_list})
    except Exception as e:
        return _err(e)


# ── Contacts Fields Metadata ─────────────────────────────────────


@mcp.tool()
def list_contact_fields() -> str:
    """List all contact field metadata — tabs, groups, and fields.

    Returns the complete schema of available contact fields
    including custom fields, their types, and valid modifiers.
    """
    try:
        return _ok(_get_client().list_contact_fields())
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_contact_field(
    name: str,
    field_kind: str,
    tab_id: str,
    presentation_json: str = "{}",
    group_id: str = "",
    insert_after: str = "",
    multiples: bool = False,
) -> str:
    """Create a new custom contact field.

    Args:
        name: Field name (1-50 chars).
        field_kind: One of 'string', 'long_string', 'choice', 'number',
            'datetime', 'boolean', 'address', 'user'.
        tab_id: ID of the tab this field belongs to.
        presentation_json: JSON string describing presentation
            (required for number/datetime fields, e.g.
            {"number_type": "integer"}).
        group_id: Optional group ID to nest the field under.
        insert_after: Optional field/group ID to insert after.
        multiples: Whether this field can hold multiple values.
    """
    try:
        client = _get_client()
        result = client.create_contact_field(
            name=name,
            field_type={"field_kind": field_kind},
            presentation=json.loads(presentation_json),
            tab_id=tab_id,
            group_id=group_id or None,
            insert_after=insert_after or None,
            multiples=multiples,
        )
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid presentation JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def update_contact_field(
    field_id: str,
    name: str = "",
    presentation_json: str = "",
    group_id: str = "",
    tab_id: str = "",
    insert_after: str = "",
) -> str:
    """Update an existing custom contact field.

    Args:
        field_id: The field ID.
        name: New field name.
        presentation_json: JSON string for new presentation settings.
        group_id: New group ID to move the field into.
        tab_id: New tab ID.
        insert_after: Field/group ID to move this field after.
    """
    try:
        client = _get_client()
        result = client.update_contact_field(
            field_id,
            name=name or None,
            presentation=json.loads(presentation_json) if presentation_json else None,
            group_id=group_id or None,
            tab_id=tab_id or None,
            insert_after=insert_after or None,
        )
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid presentation JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_contact_field(field_id: str, preflight_checks: bool = True) -> str:
    """Delete a custom contact field.

    Args:
        field_id: The field ID.
        preflight_checks: If true, errors if the field is in use by
            any contacts instead of deleting it.
    """
    try:
        client = _get_client()
        result = client.delete_contact_field(field_id, preflight_checks=preflight_checks)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_contact_field_group(
    name: str,
    tab_id: str,
    logo_id: str = "",
    insert_after: str = "",
) -> str:
    """Create a new contact fields group.

    Args:
        name: Group name (1-50 chars).
        tab_id: ID of the tab this group belongs to.
        logo_id: Optional logo ID to display.
        insert_after: Optional field/group ID to insert after.
    """
    try:
        client = _get_client()
        result = client.create_contact_field_group(
            name=name, tab_id=tab_id,
            logo_id=logo_id, insert_after=insert_after or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_contact_field_tab(
    tab_name: str,
    contact_types: str = "person,company",
    insert_after: str = "",
) -> str:
    """Create a new contact fields tab.

    Args:
        tab_name: Tab name (1-50 chars).
        contact_types: Comma-separated types: 'person', 'company'.
        insert_after: Optional tab ID to insert after.
    """
    try:
        client = _get_client()
        result = client.create_contact_field_tab(
            tab_name=tab_name,
            contact_types=_csv(contact_types),
            insert_after=insert_after or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


# ── Contacts Pipelines / Lead Transitions ───────────────────────


@mcp.tool()
def list_contact_pipelines() -> str:
    """List contact/lead pipelines visible to the requesting user."""
    try:
        return _ok(_get_client().list_contact_pipelines())
    except Exception as e:
        return _err(e)


@mcp.tool()
def move_lead_to_stage(lead_id: str, pipeline_id: str, stage_id: str) -> str:
    """Move a lead (contact) into a pipeline stage.

    Args:
        lead_id: The contact/lead ID.
        pipeline_id: The pipeline ID.
        stage_id: The target stage ID.
    """
    try:
        client = _get_client()
        result = client.move_lead_to_stage(lead_id, pipeline_id, stage_id)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def exit_lead_successful(
    lead_id: str,
    pipeline_id: str,
    notes: str = "",
) -> str:
    """Exit a lead from a pipeline as won.

    Args:
        lead_id: The contact/lead ID.
        pipeline_id: The pipeline ID.
        notes: Optional notes about the transition.
    """
    try:
        client = _get_client()
        result = client.exit_lead_successful(
            lead_id, pipeline_id, notes=notes or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def exit_lead_unsuccessful(
    lead_id: str,
    pipeline_id: str,
    notes: str = "",
    lost_reason: str = "",
) -> str:
    """Exit a lead from a pipeline as lost.

    Args:
        lead_id: The contact/lead ID.
        pipeline_id: The pipeline ID.
        notes: Optional notes about the transition.
        lost_reason: Optional lost reason.
    """
    try:
        client = _get_client()
        result = client.exit_lead_unsuccessful(
            lead_id, pipeline_id,
            notes=notes or None, lost_reason=lost_reason or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def undo_lead_transition(lead_id: str, pipeline_id: str) -> str:
    """Undo a recent won/lost transition for a lead.

    Args:
        lead_id: The contact/lead ID.
        pipeline_id: The pipeline ID.
    """
    try:
        return _ok(_get_client().undo_lead_transition(lead_id, pipeline_id))
    except Exception as e:
        return _err(e)


# ── Activities ───────────────────────────────────────────────────


@mcp.tool()
def list_activities(
    direction: str,
    limit: int = 30,
    contact_ids: str = "",
    deal_ids: str = "",
    completed: bool | None = None,
) -> str:
    """List activities (pending or past) matching filters.

    Args:
        direction: 'pending' (future) or 'past' (old) activities.
        limit: Max activities to return.
        contact_ids: Comma-separated contact IDs to filter by.
        deal_ids: Comma-separated deal IDs to filter by.
        completed: True for only completed, False for uncompleted.
    """
    try:
        client = _get_client()
        result = client.list_activities(
            direction=direction,
            limit=limit,
            contacts=_csv(contact_ids) if contact_ids else None,
            deals=_csv(deal_ids) if deal_ids else None,
            completed=completed,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


# ── Tasks ───────────────────────────────────────────────────────


@mcp.tool()
def create_task(
    subject: str,
    notes: str = "",
    related_contacts: str = "",
    related_deals: str = "",
    due_date: str = "",
    tags: str = "",
) -> str:
    """Create a task in Nimble CRM.

    Args:
        subject: Task title.
        notes: Additional task notes.
        related_contacts: Comma-separated contact IDs to associate.
        related_deals: Comma-separated deal IDs to associate.
        due_date: Due date, e.g. YYYY-MM-DDTHH:MM:SS.
        tags: Comma-separated tags to apply.
    """
    try:
        client = _get_client()
        result = client.create_task(
            subject=subject,
            notes=notes or None,
            related_contacts=_csv(related_contacts) if related_contacts else None,
            related_deals=_csv(related_deals) if related_deals else None,
            due_date=due_date or None,
            tags=_csv(tags) if tags else None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


# ── Deals ───────────────────────────────────────────────────────


@mcp.tool()
def list_deals(sort: str = "name:desc", limit: int = 30) -> str:
    """List all of the current user's deals.

    Args:
        sort: Sort spec as "<field>:<order>", e.g. "name:asc".
        limit: Max deals to return.
    """
    try:
        client = _get_client()
        result = client.list_deals(sort=sort, limit=limit)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_deal(deal_id: str) -> str:
    """Get a single deal by ID.

    Args:
        deal_id: The Nimble deal ID.
    """
    try:
        return _ok(_get_client().get_deal(deal_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_deal(
    pipeline_id: str,
    stage_id: str,
    fields_values_json: str,
    owner_id: str = "",
    currency: str = "",
    tags: str = "",
) -> str:
    """Create a new deal in Nimble CRM (deals_v2).

    Args:
        pipeline_id: Pipeline to place the deal in.
        stage_id: Stage within that pipeline.
        fields_values_json: JSON string keyed by field id, each a list
            of {"value": ...} dicts. Must include the deal name field;
            probability is required unless the stage has a default.
            Example: {"63760e653af0e748fe48366a": [{"value": "Big Deal"}]}
        owner_id: User ID who owns the deal.
        currency: ISO-4217 3-letter currency code.
        tags: Comma-separated tags to apply.
    """
    try:
        client = _get_client()
        fields_values = json.loads(fields_values_json)
        result = client.create_deal(
            pipeline_id=pipeline_id,
            stage_id=stage_id,
            fields_values=fields_values,
            owner_id=owner_id or None,
            currency=currency or None,
            tags=_csv(tags) if tags else None,
        )
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid fields_values JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def update_deal(
    deal_id: str,
    fields_values_json: str = "",
    pipeline_id: str = "",
    stage_id: str = "",
    owner_id: str = "",
    tags: str = "",
) -> str:
    """Update an existing deal.

    Args:
        deal_id: The Nimble deal ID.
        fields_values_json: JSON string keyed by field id, each a list
            of {"value": ...} dicts. Send an empty list to clear a field.
        pipeline_id: Move the deal to a different pipeline.
        stage_id: Move the deal to a different stage.
        owner_id: Reassign the deal owner.
        tags: Comma-separated new tag list (replaces existing tags).
    """
    try:
        client = _get_client()
        fields_values = json.loads(fields_values_json) if fields_values_json else None
        result = client.update_deal(
            deal_id,
            fields_values=fields_values,
            pipeline_id=pipeline_id or None,
            stage_id=stage_id or None,
            owner_id=owner_id or None,
            tags=_csv(tags) if tags else None,
        )
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid fields_values JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_deal(deal_id: str) -> str:
    """Delete a deal by ID.

    Args:
        deal_id: The Nimble deal ID.
    """
    try:
        return _ok(_get_client().delete_deal(deal_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_won_deals_last_month() -> str:
    """Get the sum and count of deal amounts won in the last month."""
    try:
        return _ok(_get_client().get_won_deals_last_month())
    except Exception as e:
        return _err(e)


# ── Deal Tags ────────────────────────────────────────────────────


@mcp.tool()
def list_deal_tags(starts_with: str = "", limit: int = 30) -> str:
    """List deal tags, optionally filtered by prefix.

    Args:
        starts_with: Only return tags starting with this string.
        limit: Max tags to return.
    """
    try:
        client = _get_client()
        result = client.list_deal_tags(starts_with=starts_with or None, limit=limit)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def add_tags_to_deals(query_json: str, tags: str) -> str:
    """Assign tags to all deals matching an advanced search query.

    Args:
        query_json: JSON-encoded advanced search query for deals.
        tags: Comma-separated tags to assign.
    """
    try:
        client = _get_client()
        result = client.add_tags_to_deals(json.loads(query_json), _csv(tags))
        return _ok(result)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid query JSON: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def rename_deal_tag(tag_name: str, new_tag: str) -> str:
    """Rename a deal tag.

    Args:
        tag_name: Current tag name.
        new_tag: New tag name.
    """
    try:
        return _ok(_get_client().rename_deal_tag(tag_name, new_tag))
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_deal_tag(tag_name: str) -> str:
    """Delete/unlink a deal tag from all deals.

    Args:
        tag_name: Tag name to delete.
    """
    try:
        return _ok(_get_client().delete_deal_tag(tag_name))
    except Exception as e:
        return _err(e)


# ── Deal Notes ───────────────────────────────────────────────────


@mcp.tool()
def create_deal_note(deal_id: str, title: str, body: str = "") -> str:
    """Create a note attached to a deal.

    Args:
        deal_id: The Nimble deal ID.
        title: Note title (1-256 chars).
        body: Note body text.
    """
    try:
        client = _get_client()
        result = client.create_deal_note(deal_id, title, body_text=body or None)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def update_deal_note(
    deal_id: str, note_id: str, title: str = "", body: str = "",
) -> str:
    """Update a deal note.

    Args:
        deal_id: The Nimble deal ID.
        note_id: The note ID.
        title: New title.
        body: New body text.
    """
    try:
        client = _get_client()
        result = client.update_deal_note(
            deal_id, note_id, title=title or None, body_text=body or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_deal_note(deal_id: str, note_id: str) -> str:
    """Delete a note from a deal.

    Args:
        deal_id: The Nimble deal ID.
        note_id: The note ID.
    """
    try:
        return _ok(_get_client().delete_deal_note(deal_id, note_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_deal_overdue_activities(deal_id: str, limit: int = 30) -> str:
    """List a deal's overdue activities, most-overdue first.

    Args:
        deal_id: The Nimble deal ID.
        limit: Max activities to return.
    """
    try:
        client = _get_client()
        result = client.list_deal_overdue_activities(deal_id, limit=limit)
        return _ok(result)
    except Exception as e:
        return _err(e)


# ── Deal Fields ──────────────────────────────────────────────────


@mcp.tool()
def list_deal_fields() -> str:
    """List deal standard fields and per-pipeline fields."""
    try:
        return _ok(_get_client().list_deal_fields())
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_deal_column_catalogue() -> str:
    """List the deal column/column-group catalogue for the user."""
    try:
        return _ok(_get_client().list_deal_column_catalogue())
    except Exception as e:
        return _err(e)


# ── Deal Pipelines ───────────────────────────────────────────────


@mcp.tool()
def list_deal_pipelines() -> str:
    """List all deal pipelines and their stages in Nimble CRM."""
    try:
        return _ok(_get_client().list_deal_pipelines())
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_deal_pipeline(pipeline_id: str) -> str:
    """Get a single deal pipeline by ID.

    Args:
        pipeline_id: The Nimble pipeline ID.
    """
    try:
        return _ok(_get_client().get_deal_pipeline(pipeline_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_deal_pipeline(
    name: str,
    description: str = "",
    color: str = "",
    default_currency: str = "USD",
) -> str:
    """Create a new deal pipeline in Nimble CRM.

    Args:
        name: Pipeline name (1-200 chars).
        description: Pipeline description.
        color: Pipeline color.
        default_currency: ISO-4217 3-letter currency code.
    """
    try:
        client = _get_client()
        result = client.create_deal_pipeline(
            name=name, description=description, color=color,
            default_currency=default_currency,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def update_deal_pipeline(
    pipeline_id: str,
    name: str = "",
    description: str = "",
    color: str = "",
) -> str:
    """Update an existing deal pipeline's name, description, or color.

    Args:
        pipeline_id: The Nimble pipeline ID.
        name: New pipeline name.
        description: New pipeline description.
        color: New pipeline color.
    """
    try:
        client = _get_client()
        result = client.update_deal_pipeline(
            pipeline_id,
            name=name or None,
            description=description or None,
            color=color or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_deal_pipeline(pipeline_id: str) -> str:
    """Delete a deal pipeline by ID. All deals in it will also be deleted!

    Args:
        pipeline_id: The Nimble pipeline ID.
    """
    try:
        return _ok(_get_client().delete_deal_pipeline(pipeline_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_pipeline_deals_by_stage(
    pipeline_id: str, sort: str = "name:desc", limit: int = 10,
) -> str:
    """List a pipeline's deals grouped by stage.

    Args:
        pipeline_id: The Nimble pipeline ID.
        sort: Sort spec as "<field>:<order>".
        limit: Max deals per stage.
    """
    try:
        client = _get_client()
        result = client.list_pipeline_deals_by_stage(pipeline_id, sort=sort, limit=limit)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_pipeline_deals_by_owner(
    pipeline_id: str, sort: str = "name:desc", limit: int = 10,
) -> str:
    """List a pipeline's deals grouped by owner.

    Args:
        pipeline_id: The Nimble pipeline ID.
        sort: Sort spec as "<field>:<order>".
        limit: Max deals per owner.
    """
    try:
        client = _get_client()
        result = client.list_pipeline_deals_by_owner(pipeline_id, sort=sort, limit=limit)
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def archive_deal_pipeline(pipeline_id: str) -> str:
    """Archive a deal pipeline.

    Args:
        pipeline_id: The Nimble pipeline ID.
    """
    try:
        return _ok(_get_client().archive_deal_pipeline(pipeline_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def unarchive_deal_pipeline(pipeline_id: str) -> str:
    """Un-archive a deal pipeline.

    Args:
        pipeline_id: The Nimble pipeline ID.
    """
    try:
        return _ok(_get_client().unarchive_deal_pipeline(pipeline_id))
    except Exception as e:
        return _err(e)


@mcp.tool()
def add_pipeline_lost_reason(pipeline_id: str, reason: str) -> str:
    """Add a new lost-reason option to a pipeline.

    Args:
        pipeline_id: The Nimble pipeline ID.
        reason: Reason description.
    """
    try:
        return _ok(_get_client().add_pipeline_lost_reason(pipeline_id, reason))
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_pipeline_stage(
    pipeline_id: str,
    name: str,
    description: str = "",
    expected_days: int = 0,
    default_probability: int = 0,
) -> str:
    """Create a new stage within a deal pipeline.

    Args:
        pipeline_id: The Nimble pipeline ID.
        name: Stage name.
        description: Stage description.
        expected_days: Expected number of days a deal spends in this stage.
        default_probability: Default win probability (0-100) for deals
            entering this stage.
    """
    try:
        client = _get_client()
        result = client.create_pipeline_stage(
            pipeline_id,
            name=name,
            description=description or None,
            expected_days=expected_days or None,
            default_probability=default_probability or None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def update_pipeline_stage(
    pipeline_id: str,
    stage_id: str,
    name: str = "",
    description: str = "",
    expected_days: int = -1,
    default_probability: int = -1,
) -> str:
    """Update an existing pipeline stage.

    Args:
        pipeline_id: The Nimble pipeline ID.
        stage_id: The stage ID to update.
        name: New stage name.
        description: New stage description.
        expected_days: New expected days (pass -1 to leave unchanged).
        default_probability: New default probability 0-100 (pass -1 to leave unchanged).
    """
    try:
        client = _get_client()
        result = client.update_pipeline_stage(
            pipeline_id,
            stage_id,
            name=name or None,
            description=description or None,
            expected_days=expected_days if expected_days >= 0 else None,
            default_probability=default_probability if default_probability >= 0 else None,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def archive_pipeline_stage(pipeline_id: str, stage_id: str) -> str:
    """Archive a pipeline stage.

    Args:
        pipeline_id: The Nimble pipeline ID.
        stage_id: The stage ID to archive.
    """
    try:
        return _ok(_get_client().archive_pipeline_stage(pipeline_id, stage_id))
    except Exception as e:
        return _err(e)


# ── Messages ─────────────────────────────────────────────────────


@mcp.tool()
def list_message_drafts(
    recipients: str = "", page: int = 0, per_page: int = 30,
) -> str:
    """List draft messages in Nimble CRM.

    Args:
        recipients: Comma-separated recipient filter.
        page: Page number (starts at 0).
        per_page: Results per page.
    """
    try:
        client = _get_client()
        result = client.list_message_drafts(
            recipients=recipients or None, page=page, per_page=per_page,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def create_message_draft(
    subject: str,
    body: str,
    to: str = "",
) -> str:
    """Create a draft message in Nimble CRM.

    Args:
        subject: Message subject.
        body: Message body text.
        to: Comma-separated recipient email addresses.
    """
    try:
        client = _get_client()
        recipients = (
            [{"account_type": "email", "identifier": addr} for addr in _csv(to)]
            if to else None
        )
        result = client.create_message_draft(
            subject=subject, body=body, recipients=recipients,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
