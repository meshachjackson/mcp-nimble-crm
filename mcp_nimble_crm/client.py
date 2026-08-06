"""Nimble CRM API client.

Handles authentication and all REST API calls to the Nimble CRM API.
Fully independent from the MCP server layer — usable standalone.

Authentication: Bearer token via API key.
Base URLs:
    v1 -- https://app.nimble.com/api/v1  (contacts, notes, tags, fields
          metadata, contact pipelines, activities, tasks, messages)
    v2 -- https://app.nimble.com/api/v2  (deals, deal pipelines, deal
          fields, deal tags, lead pipeline transitions)

Scope note: binary file upload/download endpoints (deal files, contact
avatar uploads via Azure Blob SDK) are intentionally not implemented
here — they require a separate multipart/Azure Blob integration that
is out of scope for a JSON REST client. Everything else documented in
Nimble's official API reference (readthedocs / Redocly OpenAPI spec)
is covered.
"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL_V1 = "https://app.nimble.com/api/v1"
BASE_URL_V2 = "https://app.nimble.com/api/v2"


class NimbleClient:
    """Client for the Nimble CRM REST API (v1 and v2).

    API key is read from NIMBLE_API_KEY environment variable,
    or can be passed directly.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("NIMBLE_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Nimble API key required. Set NIMBLE_API_KEY environment "
                "variable, or pass it directly."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "mcp-nimble-crm/0.2",
        })

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        *,
        base_url: str = BASE_URL_V1,
    ) -> dict[str, Any] | list[Any]:
        """Make an authenticated request to the Nimble API."""
        url = f"{base_url}{path}"
        resp = self.session.request(
            method, url, params=params, json=json_body,
        )
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.text.strip():
            return {}
        return resp.json()

    def _request_v2(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._request(
            method, path, params=params, json_body=json_body,
            base_url=BASE_URL_V2,
        )

    # ══════════════════════════════════════════════════════════════
    # V1 — User / Account
    # ══════════════════════════════════════════════════════════════

    def get_myself(self) -> dict[str, Any]:
        """Get current authenticated user info."""
        return self._request("GET", "/myself")

    # ══════════════════════════════════════════════════════════════
    # V1 — Contacts
    # ══════════════════════════════════════════════════════════════

    def list_contacts(
        self,
        *,
        record_type: str = "all",
        keyword: str | None = None,
        fields: str | None = None,
        tags: int = 1,
        per_page: int = 30,
        page: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """List contacts with optional keyword search.

        `keyword` and `query` (see `search_contacts`) are mutually
        exclusive on Nimble's side.
        """
        params: dict[str, Any] = {
            "record_type": record_type,
            "tags": tags,
            "per_page": per_page,
            "page": page,
        }
        if keyword:
            params["keyword"] = keyword
        if fields:
            params["fields"] = fields
        if sort:
            params["sort"] = sort
        return self._request("GET", "/contacts", params=params)

    def search_contacts(
        self,
        query: dict[str, Any],
        *,
        fields: str | None = None,
        tags: int = 1,
        per_page: int = 30,
        page: int = 1,
    ) -> dict[str, Any]:
        """Search contacts with an advanced NSE query.

        Query format: {"and": [{"field": {"operator": "value"}}]}
        See Nimble's "Advanced search query syntax" docs for the full
        operator set (is, contain, starts_with, range, in_the_last,
        gt/gte/lt/lte, etc). Note: if `query` is provided, Nimble
        ignores any `record_type` filter.
        """
        params: dict[str, Any] = {
            "query": json.dumps(query),
            "tags": tags,
            "per_page": per_page,
            "page": page,
        }
        if fields:
            params["fields"] = fields
        return self._request("GET", "/contacts", params=params)

    def list_contact_ids(
        self,
        *,
        record_type: str = "all",
        keyword: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> dict[str, Any]:
        """List contact IDs only (faster than a full contact listing)."""
        params: dict[str, Any] = {
            "record_type": record_type,
            "per_page": per_page,
            "page": page,
        }
        if keyword:
            params["keyword"] = keyword
        return self._request("GET", "/contacts/ids", params=params)

    def get_contacts_by_ids(
        self,
        contact_ids: list[str],
        *,
        fields: str | None = None,
        tags: bool | None = None,
    ) -> dict[str, Any]:
        """Return standard contact listings for up to 30 explicit IDs."""
        params: dict[str, Any] = {"id": ",".join(contact_ids)}
        if fields:
            params["fields"] = fields
        if tags is not None:
            params["tags"] = tags
        return self._request("GET", "/contact", params=params)

    def get_contact(
        self,
        contact_id: str,
        *,
        fields: str | None = None,
        tags: int = 1,
    ) -> dict[str, Any]:
        """Get a single contact by ID.

        Returns the contact object directly (unwrapped from the
        API's {"resources": [...]} envelope).
        """
        params: dict[str, Any] = {"tags": tags}
        if fields:
            params["fields"] = fields
        result = self._request("GET", f"/contact/{contact_id}", params=params)
        resources = result.get("resources", [])
        if not resources:
            raise ValueError(f"Contact {contact_id} not found")
        return resources[0]

    def create_contact(
        self,
        record_type: str,
        fields: dict[str, list[dict[str, str]]],
        *,
        tags: str | None = None,
        avatar_url: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new contact.

        Args:
            record_type: 'person' or 'company'.
            fields: Dict of field name -> list of {value, modifier} dicts.
                Example: {"first name": [{"value": "Jack", "modifier": ""}]}
            tags: Comma-separated tags (max 5 on creation).
            avatar_url: URL to avatar image.
            owner_id: User ID to assign as owner. Pass None to leave
                unassigned/default (Nimble applies its own default).
        """
        body: dict[str, Any] = {
            "record_type": record_type,
            "fields": fields,
        }
        if tags:
            body["tags"] = tags
        if avatar_url:
            body["avatar_url"] = avatar_url
        if owner_id:
            body["owner_id"] = owner_id
        return self._request("POST", "/contact", json_body=body)

    def update_contact(
        self,
        contact_id: str,
        *,
        fields: dict[str, list[dict[str, str]]] | None = None,
        avatar_url: str | None = None,
        is_important: bool | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Update an existing contact.

        Args:
            contact_id: The contact ID.
            fields: Dict of field name -> list of {value, modifier} dicts.
            avatar_url: URL to avatar image.
            is_important: Star/unstar the contact.
            replace: If True, sends `type=1` so Nimble replaces all
                values for each field type. If False (`type=0`),
                values are merged with existing ones.
        """
        body: dict[str, Any] = {}
        if fields:
            body["fields"] = fields
        if avatar_url:
            body["avatar_url"] = avatar_url
        if is_important is not None:
            body["is_important"] = is_important
        if not body:
            raise ValueError("Must provide fields, avatar_url, or is_important to update")
        params = {"type": "1" if replace else "0"}
        return self._request(
            "PUT", f"/contact/{contact_id}",
            params=params, json_body=body,
        )

    def delete_contact(
        self,
        contact_id: str,
        *,
        deletion_method: str = "regular",
        cleanup_email_lists: bool = False,
    ) -> dict[str, Any]:
        """Delete a single contact by ID.

        Args:
            contact_id: The contact ID.
            deletion_method: 'regular' (errors if relations block
                deletion) or 'force' (delete despite relations).
            cleanup_email_lists: If True, also remove matching email
                list entries.
        """
        params: dict[str, Any] = {
            "deletion_method": deletion_method,
            "cleanup_email_lists": cleanup_email_lists,
        }
        return self._request("DELETE", f"/contact/{contact_id}", params=params)

    def delete_contacts(self, contact_ids: list[str]) -> dict[str, Any]:
        """Delete one or more contacts by ID (comma-joined path form)."""
        ids_str = ",".join(contact_ids)
        return self._request("DELETE", f"/contact/{ids_str}")

    def delete_contacts_by_query(
        self,
        *,
        keyword: list[str] | None = None,
        query: dict[str, Any] | None = None,
        record_type: str = "all",
        preflight_checks: bool = False,
    ) -> dict[str, Any]:
        """Bulk-delete contacts matching a search query or keyword list.

        Requires bulk delete permission for the authenticated user.
        If `query` is provided, `record_type` is ignored by Nimble.
        """
        params: dict[str, Any] = {
            "record_type": record_type,
            "preflight_checks": preflight_checks,
        }
        if keyword:
            params["keyword"] = keyword
        if query:
            params["query"] = json.dumps(query)
        return self._request("DELETE", "/contacts", params=params)

    def list_contact_fields_metadata_legacy(self) -> dict[str, Any]:
        """(DEPRECATED) List legacy contact fields/groups metadata."""
        return self._request("GET", "/contacts/metadata")

    # ══════════════════════════════════════════════════════════════
    # V1 — Contact Notes
    # ══════════════════════════════════════════════════════════════

    def list_notes(
        self,
        contact_id: str,
        *,
        per_page: int = 5,
        page: int = 1,
    ) -> dict[str, Any]:
        """List notes for a contact."""
        params = {"per_page": per_page, "page": page}
        return self._request(
            "GET", f"/contacts/{contact_id}/notes", params=params,
        )

    def get_note(self, note_id: str) -> dict[str, Any]:
        """Get a single note by ID."""
        return self._request("GET", f"/contacts/notes/{note_id}")

    def create_note(
        self,
        contact_ids: list[str],
        note: str,
        note_preview: str,
    ) -> dict[str, Any]:
        """Create a note attached to one or more contacts (1-10 contacts)."""
        body = {
            "contact_ids": contact_ids,
            "note": note,
            "note_preview": note_preview,
        }
        return self._request("POST", "/contacts/notes", json_body=body)

    def create_contact_note(
        self,
        contact_id: str,
        note: str,
        *,
        note_preview: str | None = None,
    ) -> dict[str, Any]:
        """Create a note attached to a single contact via its own route.

        Simpler alternative to `create_note` when only one contact is
        involved. `note_preview` defaults to the full note if omitted.
        """
        body: dict[str, Any] = {"note": note}
        if note_preview:
            body["note_preview"] = note_preview
        return self._request(
            "POST", f"/contacts/{contact_id}/notes", json_body=body,
        )

    def update_note(
        self,
        note_id: str,
        contact_ids: list[str],
        note: str,
        note_preview: str,
    ) -> dict[str, Any]:
        """Update an existing note."""
        body = {
            "contact_ids": contact_ids,
            "note": note,
            "note_preview": note_preview,
        }
        return self._request(
            "PUT", f"/contacts/notes/{note_id}", json_body=body,
        )

    def delete_note(self, note_id: str) -> dict[str, Any]:
        """Delete a note by ID."""
        return self._request("DELETE", f"/contacts/notes/{note_id}")

    # ══════════════════════════════════════════════════════════════
    # V1 — Contact Tags
    # ══════════════════════════════════════════════════════════════

    def replace_tags(
        self, contact_id: str, tags: list[str],
    ) -> dict[str, Any]:
        """Replace all tags on a contact.

        WARNING: This is a full replace — tags not in the list will be removed.
        """
        body = {"tags": tags}
        return self._request(
            "PUT", f"/contacts/{contact_id}/tags", json_body=body,
        )

    # ══════════════════════════════════════════════════════════════
    # V1 — Contacts Fields Metadata (tabs, groups, fields, choices)
    # ══════════════════════════════════════════════════════════════

    def list_contact_fields(self) -> dict[str, Any]:
        """List all contact field metadata (tabs, groups, fields)."""
        return self._request("GET", "/contacts/fields")

    def create_contact_field(
        self,
        *,
        name: str,
        field_type: dict[str, Any],
        presentation: dict[str, Any],
        tab_id: str,
        group_id: str | None,
        insert_after: str | None,
        multiples: bool = False,
    ) -> dict[str, Any]:
        """Create a new custom contact field."""
        body: dict[str, Any] = {
            "name": name,
            "field_type": field_type,
            "presentation": presentation,
            "tab_id": tab_id,
            "group_id": group_id,
            "insert_after": insert_after,
            "multiples": multiples,
        }
        return self._request("POST", "/contacts/fields", json_body=body)

    def update_contact_field(
        self,
        field_id: str,
        *,
        name: str | None = None,
        presentation: dict[str, Any] | None = None,
        group_id: str | None = None,
        tab_id: str | None = None,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing custom contact field."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if presentation is not None:
            body["presentation"] = presentation
        if group_id is not None:
            body["group_id"] = group_id
        if tab_id is not None:
            body["tab_id"] = tab_id
        if insert_after is not None:
            body["insert_after"] = insert_after
        return self._request(
            "PUT", f"/contacts/fields/{field_id}", json_body=body,
        )

    def delete_contact_field(
        self, field_id: str, *, preflight_checks: bool,
    ) -> dict[str, Any]:
        """Delete a custom contact field."""
        params = {"preflight_checks": preflight_checks}
        return self._request(
            "DELETE", f"/contacts/fields/{field_id}", params=params,
        )

    def create_contact_field_group(
        self,
        *,
        name: str,
        tab_id: str,
        logo_id: str,
        insert_after: str | None,
    ) -> dict[str, Any]:
        """Create a new contact fields group."""
        body: dict[str, Any] = {
            "name": name,
            "tab_id": tab_id,
            "logo_id": logo_id,
            "insert_after": insert_after,
        }
        return self._request("POST", "/contacts/fields/groups", json_body=body)

    def update_contact_field_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        logo_id: str | None = None,
        tab_id: str | None = None,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing contact fields group."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if logo_id is not None:
            body["logo_id"] = logo_id
        if tab_id is not None:
            body["tab_id"] = tab_id
        if insert_after is not None:
            body["insert_after"] = insert_after
        return self._request(
            "PUT", f"/contacts/fields/groups/{group_id}", json_body=body,
        )

    def delete_contact_field_group(
        self, group_id: str, *, preflight_checks: bool,
    ) -> dict[str, Any]:
        """Delete a contact fields group."""
        params = {"preflight_checks": preflight_checks}
        return self._request(
            "DELETE", f"/contacts/fields/groups/{group_id}", params=params,
        )

    def create_contact_field_tab(
        self,
        *,
        tab_name: str,
        contact_types: list[str],
        insert_after: str | None,
    ) -> dict[str, Any]:
        """Create a new contact fields tab."""
        body: dict[str, Any] = {
            "tab_name": tab_name,
            "contact_types": contact_types,
            "insert_after": insert_after,
        }
        return self._request("POST", "/contacts/fields/tabs", json_body=body)

    def update_contact_field_tab(
        self,
        tab_id: str,
        *,
        tab_name: str | None = None,
        contact_types: str | None = None,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing contact fields tab."""
        body: dict[str, Any] = {}
        if tab_name is not None:
            body["tab_name"] = tab_name
        if contact_types is not None:
            body["contact_types"] = contact_types
        if insert_after is not None:
            body["insert_after"] = insert_after
        return self._request(
            "PUT", f"/contacts/fields/tabs/{tab_id}", json_body=body,
        )

    def delete_contact_field_tab(
        self, tab_id: str, *, preflight_checks: bool,
    ) -> dict[str, Any]:
        """Delete a contact fields tab."""
        params = {"preflight_checks": preflight_checks}
        return self._request(
            "DELETE", f"/contacts/fields/tabs/{tab_id}", params=params,
        )

    def create_contact_field_choice(
        self,
        field_id: str,
        *,
        choice_id: str,
        value: str,
        insert_after: str | None,
    ) -> dict[str, Any]:
        """Create a dropdown/choice option for a contact field."""
        body: dict[str, Any] = {
            "id": choice_id,
            "value": value,
            "insert_after": insert_after,
        }
        return self._request(
            "POST", f"/contacts/fields/{field_id}/choices", json_body=body,
        )

    def update_contact_field_choice(
        self,
        field_id: str,
        choice_id: str,
        *,
        value: str | None = None,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Update a dropdown/choice option for a contact field."""
        body: dict[str, Any] = {"id": choice_id}
        if value is not None:
            body["value"] = value
        if insert_after is not None:
            body["insert_after"] = insert_after
        return self._request(
            "PUT", f"/contacts/fields/{field_id}/choices/{choice_id}",
            json_body=body,
        )

    def delete_contact_field_choice(
        self, field_id: str, choice_id: str, *, preflight_checks: bool,
    ) -> dict[str, Any]:
        """Delete a dropdown/choice option from a contact field."""
        params = {"preflight_checks": preflight_checks}
        return self._request(
            "DELETE", f"/contacts/fields/{field_id}/choices/{choice_id}",
            params=params,
        )

    def unmark_primary_field(
        self, contact_id: str, *, field_id: str, position: int,
    ) -> dict[str, Any]:
        """Remove the is_primary flag from a multi-value field entry."""
        body = {"field_id": field_id, "position": position}
        return self._request(
            "DELETE", f"/contact/{contact_id}/field", json_body=body,
        )

    def mark_primary_field(
        self, contact_id: str, *, field_id: str, position: int,
    ) -> dict[str, Any]:
        """Mark a multi-value field entry as the primary value."""
        body = {"field_id": field_id, "position": position}
        return self._request(
            "PUT", f"/contact/{contact_id}/field", json_body=body,
        )

    # ══════════════════════════════════════════════════════════════
    # V1 — Contacts Pipelines (listing) + V2 Lead Transitions
    # ══════════════════════════════════════════════════════════════

    def list_contact_pipelines(self) -> dict[str, Any]:
        """List contact/lead pipelines visible to the requesting user."""
        return self._request("GET", "/contacts/pipelines")

    def exit_lead_successful(
        self,
        lead_id: str,
        pipeline_id: str,
        *,
        actual_exit_date: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Exit a lead from a pipeline as won ('successful')."""
        body: dict[str, Any] = {}
        if actual_exit_date is not None:
            body["actual_exit_date"] = actual_exit_date
        if notes is not None:
            body["notes"] = notes
        return self._request_v2(
            "POST", f"/leads/{lead_id}/{pipeline_id}/successful", json_body=body,
        )

    def exit_lead_unsuccessful(
        self,
        lead_id: str,
        pipeline_id: str,
        *,
        actual_exit_date: str | None = None,
        notes: str | None = None,
        lost_reason: str | None = None,
    ) -> dict[str, Any]:
        """Exit a lead from a pipeline as lost ('unsuccessful')."""
        body: dict[str, Any] = {}
        if actual_exit_date is not None:
            body["actual_exit_date"] = actual_exit_date
        if notes is not None:
            body["notes"] = notes
        if lost_reason is not None:
            body["lost_reason"] = lost_reason
        return self._request_v2(
            "POST", f"/leads/{lead_id}/{pipeline_id}/unsuccessful", json_body=body,
        )

    def move_lead_to_stage(
        self, lead_id: str, pipeline_id: str, stage_id: str,
    ) -> dict[str, Any]:
        """Move a lead into a pipeline stage (also enters pipeline)."""
        body = {"stage_id": stage_id}
        return self._request_v2(
            "POST", f"/leads/{lead_id}/{pipeline_id}/move", json_body=body,
        )

    def undo_lead_transition(
        self, lead_id: str, pipeline_id: str,
    ) -> dict[str, Any]:
        """Undo a recent won/lost transition for a lead."""
        return self._request_v2(
            "POST", f"/leads/{lead_id}/{pipeline_id}/undo",
        )

    def clear_lead_transitions(
        self, lead_id: str, pipeline_id: str,
    ) -> dict[str, Any]:
        """Clear all lead transitions for the current pipeline run."""
        return self._request_v2(
            "DELETE", f"/leads/{lead_id}/{pipeline_id}",
        )

    # ══════════════════════════════════════════════════════════════
    # V1 — Activities
    # ══════════════════════════════════════════════════════════════

    def list_activities(
        self,
        *,
        direction: str,
        limit: int | None = None,
        types: list[str] | None = None,
        contacts: list[str] | None = None,
        deals: list[str] | None = None,
        completed: bool | None = None,
    ) -> dict[str, Any]:
        """List activities (pending or past) matching filters.

        Args:
            direction: 'pending' (future) or 'past' (old) activities.
        """
        params: dict[str, Any] = {"direction": direction}
        if limit is not None:
            params["limit"] = limit
        if types:
            params["types"] = types
        if contacts:
            params["contacts"] = contacts
        if deals:
            params["deals"] = deals
        if completed is not None:
            params["completed"] = completed
        return self._request("GET", "/activities", params=params)

    # ══════════════════════════════════════════════════════════════
    # V1 — Tasks
    # ══════════════════════════════════════════════════════════════

    def create_task(
        self,
        subject: str,
        *,
        notes: str | None = None,
        related_contacts: list[str] | None = None,
        related_deals: list[str] | None = None,
        due_date: str | None = None,
        assigned_to: str | None = None,
        is_important: bool | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a task.

        Contacts/deals are associated via the `related` object;
        Nimble's `related_to` field is a legacy read-only response
        field and is not accepted on create.

        Args:
            subject: Task title.
            notes: Additional notes.
            related_contacts: Contact IDs to associate.
            related_deals: Deal IDs to associate.
            due_date: Due date (ISO-8601-ish string per Nimble).
            assigned_to: User ID to assign the task to.
            is_important: Flag the task as important.
            tags: Tags to apply to the task.
        """
        body: dict[str, Any] = {"subject": subject}
        if notes:
            body["notes"] = notes
        related: dict[str, Any] = {}
        if related_contacts:
            related["contacts"] = related_contacts
        if related_deals:
            related["deals"] = related_deals
        if related:
            body["related"] = related
        if due_date:
            body["due_date"] = due_date
        if assigned_to:
            body["assigned_to"] = assigned_to
        if is_important is not None:
            body["is_important"] = is_important
        if tags:
            body["tags"] = tags
        return self._request("POST", "/tasks", json_body=body)

    # ══════════════════════════════════════════════════════════════
    # V2 — Deals
    # ══════════════════════════════════════════════════════════════

    def list_deals(
        self,
        *,
        sort: str = "name:desc",
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List all of the current user's deals.

        Args:
            sort: Required by Nimble as "<field>:<order>", e.g.
                "name:asc" or "amount:desc". Note: system timestamp
                fields like "created"/"updated" and "deal_number" are
                NOT sortable on this endpoint (Nimble returns 409);
                stick to standard deal fields like "name" or "amount".
            limit: Max deals to return.
        """
        params: dict[str, Any] = {"sort": sort}
        if limit is not None:
            params["limit"] = limit
        return self._request_v2("GET", "/deals", params=params)

    def get_deal(self, deal_id: str) -> dict[str, Any]:
        """Get a single deal by ID."""
        return self._request_v2("GET", f"/deals/{deal_id}")

    def create_deal(
        self,
        *,
        pipeline_id: str,
        stage_id: str,
        fields_values: dict[str, list[dict[str, Any]]],
        owner_id: str | None = None,
        currency: str | None = None,
        related_contacts: list[dict[str, Any]] | None = None,
        related_external_contacts: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new deal (deals_v2).

        Args:
            pipeline_id: Pipeline to place the deal in.
            stage_id: Stage within that pipeline.
            fields_values: Dict keyed by field id (or field name via
                the `_with_names` variant Nimble also accepts), each
                a list of {"value": ...} dicts. At minimum needs the
                deal name field; probability is required unless the
                stage has a `default_probability`.
            owner_id: User ID who owns the deal.
            currency: ISO-4217 3-letter currency code.
            related_contacts: List of {"contact_id": ..., "note": ...}.
            related_external_contacts: List of {"contact_info": ..., "note": ...}.
            tags: Tags to apply to the deal.
        """
        body: dict[str, Any] = {
            "pipeline_id": pipeline_id,
            "stage_id": stage_id,
            "fields_values": fields_values,
        }
        if owner_id:
            body["owner_id"] = owner_id
        if currency:
            body["currency"] = currency
        if related_contacts:
            body["related_contacts"] = related_contacts
        if related_external_contacts:
            body["related_external_contacts"] = related_external_contacts
        if tags:
            body["tags"] = tags
        return self._request_v2("POST", "/deals", json_body=body)

    def update_deal(
        self,
        deal_id: str,
        *,
        fields_values: dict[str, list[dict[str, Any]]] | None = None,
        pipeline_id: str | None = None,
        stage_id: str | None = None,
        owner_id: str | None = None,
        currency: str | None = None,
        related_contacts: list[dict[str, Any]] | None = None,
        related_external_contacts: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing deal.

        To clear a field, send an empty list for it in `fields_values`
        (e.g. {"field_id": []}). To clear contacts, pass an empty list
        for `related_contacts` / `related_external_contacts`.
        """
        body: dict[str, Any] = {}
        if fields_values is not None:
            body["fields_values"] = fields_values
        if pipeline_id is not None:
            body["pipeline_id"] = pipeline_id
        if stage_id is not None:
            body["stage_id"] = stage_id
        if owner_id is not None:
            body["owner_id"] = owner_id
        if currency is not None:
            body["currency"] = currency
        if related_contacts is not None:
            body["related_contacts"] = related_contacts
        if related_external_contacts is not None:
            body["related_external_contacts"] = related_external_contacts
        if tags is not None:
            body["tags"] = tags
        if not body:
            raise ValueError("Must provide at least one field to update")
        return self._request_v2("PUT", f"/deals/{deal_id}", json_body=body)

    def delete_deal(self, deal_id: str) -> dict[str, Any]:
        """Delete a deal by ID."""
        return self._request_v2("DELETE", f"/deals/{deal_id}")

    def get_won_deals_last_month(self) -> dict[str, Any]:
        """Get the sum/count of deal amounts won in the last month."""
        return self._request_v2("GET", "/deals/widget/won_last_month")

    # ── Deal Tags ────────────────────────────────────────────────

    def list_deal_tags(
        self, *, starts_with: str | None = None, limit: int | None = None,
    ) -> dict[str, Any]:
        """List deal tags, optionally filtered by prefix."""
        params: dict[str, Any] = {}
        if starts_with:
            params["starts_with"] = starts_with
        if limit is not None:
            params["limit"] = limit
        return self._request_v2("GET", "/deals/tags", params=params)

    def add_tags_to_deals(
        self,
        query: dict[str, Any],
        tags: list[str],
        *,
        preflight_checks: bool = False,
    ) -> dict[str, Any]:
        """Assign tags to all deals matching an advanced search query."""
        body: dict[str, Any] = {
            "query": query,
            "tags": tags,
            "preflight_checks": preflight_checks,
        }
        return self._request_v2("POST", "/deals/tags", json_body=body)

    def rename_deal_tag(self, tag_name: str, new_tag: str) -> dict[str, Any]:
        """Rename a deal tag."""
        body = {"new_tag": new_tag}
        return self._request_v2(
            "PUT", f"/deals/tags/{tag_name}", json_body=body,
        )

    def delete_deal_tag(
        self, tag_name: str, *, preflight_checks: bool = False,
    ) -> dict[str, Any]:
        """Delete/unlink a deal tag from all deals."""
        body = {"preflight_checks": preflight_checks}
        return self._request_v2(
            "DELETE", f"/deals/tags/{tag_name}", json_body=body,
        )

    # ── Deal Notes ───────────────────────────────────────────────

    def create_deal_note(
        self, deal_id: str, title: str, *, body_text: str | None = None,
    ) -> dict[str, Any]:
        """Create a note attached to a deal."""
        body: dict[str, Any] = {"title": title}
        if body_text is not None:
            body["body"] = body_text
        return self._request_v2(
            "POST", f"/deals/{deal_id}/notes", json_body=body,
        )

    def update_deal_note(
        self,
        deal_id: str,
        note_id: str,
        *,
        title: str | None = None,
        body_text: str | None = None,
    ) -> dict[str, Any]:
        """Update a deal note."""
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if body_text is not None:
            body["body"] = body_text
        return self._request_v2(
            "PUT", f"/deals/{deal_id}/notes/{note_id}", json_body=body,
        )

    def delete_deal_note(self, deal_id: str, note_id: str) -> dict[str, Any]:
        """Delete a deal note."""
        return self._request_v2("DELETE", f"/deals/{deal_id}/notes/{note_id}")

    def list_deal_overdue_activities(
        self,
        deal_id: str,
        *,
        limit: int | None = None,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        """List a deal's overdue activities, most-overdue first."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if types:
            params["types"] = types
        return self._request_v2(
            "GET", f"/deals/{deal_id}/overdue", params=params,
        )

    # ══════════════════════════════════════════════════════════════
    # V2 — Deals Fields
    # ══════════════════════════════════════════════════════════════

    def list_deal_column_catalogue(self) -> dict[str, Any]:
        """List the deal column/column-group catalogue for the user."""
        return self._request_v2("GET", "/deals/column_catalogue")

    def list_deal_fields(self) -> dict[str, Any]:
        """List deal standard fields and per-pipeline fields."""
        return self._request_v2("GET", "/deals/fields")

    # ══════════════════════════════════════════════════════════════
    # V2 — Deals Pipelines
    # ══════════════════════════════════════════════════════════════

    def list_deal_pipelines(self) -> dict[str, Any]:
        """List all deal pipelines and their stages."""
        return self._request_v2("GET", "/deals/pipelines")

    def get_deal_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Get a single deal pipeline by ID."""
        return self._request_v2("GET", f"/deals/pipelines/{pipeline_id}")

    def create_deal_pipeline(
        self,
        *,
        name: str,
        description: str = "",
        color: str = "",
        lost_reasons: list[str] | None = None,
        stages: list[dict[str, Any]] | None = None,
        fields_tab_members: list[dict[str, Any]] | None = None,
        default_currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a new deal pipeline."""
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "color": color,
            "lost_reasons": lost_reasons or [],
            "stages": stages or [],
            "fields_tab_members": fields_tab_members or [],
            "default_currency": default_currency,
        }
        return self._request_v2("POST", "/deals/pipelines", json_body=body)

    def update_deal_pipeline(
        self,
        pipeline_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing deal pipeline's name/description/color."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        if not body:
            raise ValueError("Must provide name, description, or color to update")
        return self._request_v2(
            "PUT", f"/deals/pipelines/{pipeline_id}", json_body=body,
        )

    def delete_deal_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Delete a deal pipeline (and all deals within it!) by ID."""
        return self._request_v2("DELETE", f"/deals/pipelines/{pipeline_id}")

    def list_pipeline_deals_by_stage(
        self,
        pipeline_id: str,
        *,
        sort: str = "name:desc",
        limit: int | None = None,
        query: str | None = None,
        stage_id: str | None = None,
        stuck: bool | None = None,
    ) -> dict[str, Any]:
        """List a pipeline's deals grouped by stage."""
        params: dict[str, Any] = {"sort": sort}
        if limit is not None:
            params["limit"] = limit
        if query is not None:
            params["query"] = query
        if stage_id is not None:
            params["stage_id"] = stage_id
        if stuck is not None:
            params["stuck"] = stuck
        return self._request_v2(
            "GET", f"/deals/pipelines/{pipeline_id}/deals", params=params,
        )

    def list_pipeline_deals_by_owner(
        self,
        pipeline_id: str,
        *,
        sort: str = "name:desc",
        limit: int | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        """List a pipeline's deals grouped by owner."""
        params: dict[str, Any] = {"sort": sort}
        if limit is not None:
            params["limit"] = limit
        if query is not None:
            params["query"] = query
        return self._request_v2(
            "GET", f"/deals/pipelines/{pipeline_id}/owners", params=params,
        )

    def archive_deal_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Archive a deal pipeline."""
        return self._request_v2(
            "POST", f"/deals/pipelines/{pipeline_id}/archive",
        )

    def unarchive_deal_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Un-archive a deal pipeline."""
        return self._request_v2(
            "POST", f"/deals/pipelines/{pipeline_id}/unarchive",
        )

    def add_pipeline_lost_reason(
        self, pipeline_id: str, reason: str,
    ) -> dict[str, Any]:
        """Add a new lost-reason option to a pipeline."""
        body = {"reason": reason}
        return self._request_v2(
            "POST", f"/deals/pipelines/{pipeline_id}/lost_reasons",
            json_body=body,
        )

    def create_pipeline_stage(
        self,
        pipeline_id: str,
        *,
        name: str,
        description: str | None = None,
        insert_after: str | None = None,
        expected_days: int | None = None,
        default_probability: int | None = None,
    ) -> dict[str, Any]:
        """Create a new stage within a deal pipeline."""
        body: dict[str, Any] = {"name": name, "pipeline_id": pipeline_id}
        if description is not None:
            body["description"] = description
        if insert_after is not None:
            body["insert_after"] = insert_after
        if expected_days is not None:
            body["expected_days"] = expected_days
        if default_probability is not None:
            body["default_probability"] = default_probability
        return self._request_v2(
            "POST", f"/deals/pipelines/{pipeline_id}/stages", json_body=body,
        )

    def update_pipeline_stage(
        self,
        pipeline_id: str,
        stage_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        expected_days: int | None = None,
        default_probability: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing pipeline stage."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if expected_days is not None:
            body["expected_days"] = expected_days
        if default_probability is not None:
            body["default_probability"] = default_probability
        return self._request_v2(
            "PUT", f"/deals/pipelines/{pipeline_id}/stages/{stage_id}",
            json_body=body,
        )

    def archive_pipeline_stage(
        self, pipeline_id: str, stage_id: str,
    ) -> dict[str, Any]:
        """Archive a pipeline stage."""
        return self._request_v2(
            "DELETE", f"/deals/pipelines/{pipeline_id}/stages/{stage_id}",
        )

    # ══════════════════════════════════════════════════════════════
    # V2 — Deals Pipelines Fields (custom fields, groups, choices)
    # ══════════════════════════════════════════════════════════════

    def create_pipeline_field(
        self,
        pipeline_id: str,
        *,
        name: str,
        field_type: dict[str, Any],
        presentation: dict[str, Any],
        insert_after: str | None = None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a custom field on a deal pipeline."""
        body: dict[str, Any] = {
            "name": name,
            "field_type": field_type,
            "presentation": presentation,
        }
        if insert_after is not None:
            body["insert_after"] = insert_after
        if group_id is not None:
            body["group_id"] = group_id
        return self._request_v2(
            "POST", f"/deals/pipelines/{pipeline_id}/fields", json_body=body,
        )

    def update_pipeline_field(
        self,
        pipeline_id: str,
        field_id: str,
        *,
        name: str | None = None,
        presentation: dict[str, Any] | None = None,
        insert_after: str | None = None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a custom field on a deal pipeline."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if presentation is not None:
            body["presentation"] = presentation
        if insert_after is not None:
            body["insert_after"] = insert_after
        if group_id is not None:
            body["group_id"] = group_id
        return self._request_v2(
            "PUT", f"/deals/pipelines/{pipeline_id}/fields/{field_id}",
            json_body=body,
        )

    def delete_pipeline_field(
        self, pipeline_id: str, field_id: str, *, preflight_checks: bool,
    ) -> dict[str, Any]:
        """Delete a custom field from a deal pipeline."""
        body = {"preflight_checks": preflight_checks}
        return self._request_v2(
            "DELETE", f"/deals/pipelines/{pipeline_id}/fields/{field_id}",
            json_body=body,
        )

    def create_pipeline_field_choice(
        self,
        pipeline_id: str,
        field_id: str,
        choice: dict[str, Any],
        *,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Create a choice option on a custom pipeline field."""
        body: dict[str, Any] = {"choice": choice, "insert_after": insert_after}
        return self._request_v2(
            "POST",
            f"/deals/pipelines/{pipeline_id}/fields/{field_id}/choices",
            json_body=body,
        )

    def update_pipeline_field_choice(
        self,
        pipeline_id: str,
        field_id: str,
        choice_id: str,
        *,
        value: str | None = None,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Update a choice option on a custom pipeline field."""
        body: dict[str, Any] = {}
        if value is not None:
            body["value"] = value
        if insert_after is not None:
            body["insert_after"] = insert_after
        return self._request_v2(
            "PUT",
            f"/deals/pipelines/{pipeline_id}/fields/{field_id}/choices/{choice_id}",
            json_body=body,
        )

    def delete_pipeline_field_choice(
        self,
        pipeline_id: str,
        field_id: str,
        choice_id: str,
        *,
        preflight_checks: bool,
    ) -> dict[str, Any]:
        """Delete a choice option from a custom pipeline field."""
        body = {"preflight_checks": preflight_checks}
        return self._request_v2(
            "DELETE",
            f"/deals/pipelines/{pipeline_id}/fields/{field_id}/choices/{choice_id}",
            json_body=body,
        )

    def create_pipeline_field_group(
        self,
        pipeline_id: str,
        *,
        group_name: str,
        logo_id: str | None = None,
        insert_after: str | None = None,
        fields: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a custom field group on a deal pipeline."""
        body: dict[str, Any] = {"group_name": group_name}
        if logo_id is not None:
            body["logo_id"] = logo_id
        if insert_after is not None:
            body["insert_after"] = insert_after
        if fields is not None:
            body["fields"] = fields
        return self._request_v2(
            "POST", f"/deals/pipelines/{pipeline_id}/groups", json_body=body,
        )

    def update_pipeline_field_group(
        self,
        pipeline_id: str,
        group_id: str,
        *,
        group_name: str | None = None,
        logo_id: str | None = None,
        insert_after: str | None = None,
    ) -> dict[str, Any]:
        """Update a custom field group on a deal pipeline."""
        body: dict[str, Any] = {}
        if group_name is not None:
            body["group_name"] = group_name
        if logo_id is not None:
            body["logo_id"] = logo_id
        if insert_after is not None:
            body["insert_after"] = insert_after
        return self._request_v2(
            "PUT", f"/deals/pipelines/{pipeline_id}/groups/{group_id}",
            json_body=body,
        )

    def delete_pipeline_field_group(
        self, pipeline_id: str, group_id: str,
    ) -> dict[str, Any]:
        """Delete a custom field group from a deal pipeline."""
        return self._request_v2(
            "DELETE", f"/deals/pipelines/{pipeline_id}/groups/{group_id}",
        )

    # ══════════════════════════════════════════════════════════════
    # V1 — Messages
    # ══════════════════════════════════════════════════════════════

    def list_message_drafts(
        self,
        *,
        recipients: str | None = None,
        sender: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """List draft messages."""
        params: dict[str, Any] = {}
        if recipients is not None:
            params["recipients"] = recipients
        if sender is not None:
            params["sender"] = sender
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        return self._request("GET", "/messages/drafts", params=params)

    def create_message_draft(
        self,
        *,
        subject: str | None = None,
        body: str | None = None,
        recipients: list[dict[str, Any]] | None = None,
        cc: list[dict[str, Any]] | None = None,
        bcc: list[dict[str, Any]] | None = None,
        sender: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a draft message.

        `recipients`/`cc`/`bcc`/`sender` use Nimble's MessagingAccount
        shape, e.g. {"account_type": "email", "identifier": "a@b.com"}.
        """
        payload: dict[str, Any] = {}
        if subject is not None:
            payload["subject"] = subject
        if body is not None:
            payload["body"] = body
        if recipients is not None:
            payload["recipients"] = recipients
        if cc is not None:
            payload["cc"] = cc
        if bcc is not None:
            payload["bcc"] = bcc
        if sender is not None:
            payload["sender"] = sender
        return self._request("POST", "/messages/drafts", json_body=payload)
