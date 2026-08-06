"""Nimble CRM API client.

Handles authentication and all REST API calls to the Nimble CRM API.
Fully independent from the MCP server layer — usable standalone.

Authentication: Bearer token via API key.
Base URL: https://app.nimble.com/api/v1/
"""

import logging
import os
from typing import Any
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://app.nimble.com/api/v1"


class NimbleClient:
    """Client for the Nimble CRM REST API.

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
            "User-Agent": "mcp-nimble-crm/0.1",
        })

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Make an authenticated request to the Nimble API."""
        url = f"{BASE_URL}{path}"
        resp = self.session.request(
            method, url, params=params, json=json_body,
        )
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.text.strip():
            return {}
        return resp.json()

    # ── User / Account ──────────────────────────────────────────────

    def get_myself(self) -> dict[str, Any]:
        """Get current authenticated user info."""
        return self._request("GET", "/myself")

    # ── Contacts ────────────────────────────────────────────────────

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
        """List contacts with optional keyword search."""
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
        """Search contacts with advanced query.

        Query format: {"and": [{"field": {"operator": "value"}}]}
        Operators: is, is_not, contains, does_not_contain,
                   is_empty, is_not_empty, range
        """
        import json
        params: dict[str, Any] = {
            "query": json.dumps(query),
            "tags": tags,
            "per_page": per_page,
            "page": page,
        }
        if fields:
            params["fields"] = fields
        return self._request("GET", "/contacts", params=params)

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
        # API wraps single contact in {"resources": [contact]}
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
    ) -> dict[str, Any]:
        """Create a new contact.

        Args:
            record_type: 'person' or 'company'.
            fields: Dict of field name -> list of {value, modifier} dicts.
                Example: {"first name": [{"value": "Jack", "modifier": ""}]}
            tags: Comma-separated tags (max 5 on creation).
            avatar_url: URL to avatar image.
        """
        body: dict[str, Any] = {
            "record_type": record_type,
            "fields": fields,
        }
        if tags:
            body["tags"] = tags
        if avatar_url:
            body["avatar_url"] = avatar_url
        return self._request("POST", "/contact", json_body=body)

    def update_contact(
        self,
        contact_id: str,
        *,
        fields: dict[str, list[dict[str, str]]] | None = None,
        avatar_url: str | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Update an existing contact.

        Args:
            contact_id: The contact ID.
            fields: Dict of field name -> list of {value, modifier} dicts.
            avatar_url: URL to avatar image.
            replace: If True, replaces all values for each field type.
                     If False, merges with existing values.
        """
        body: dict[str, Any] = {}
        if fields:
            body["fields"] = fields
        if avatar_url:
            body["avatar_url"] = avatar_url
        if not body:
            raise ValueError("Must provide fields or avatar_url to update")
        params = {"replace": 1} if replace else None
        return self._request(
            "PUT", f"/contact/{contact_id}",
            params=params, json_body=body,
        )

    def delete_contacts(self, contact_ids: list[str]) -> dict[str, Any]:
        """Delete one or more contacts by ID."""
        ids_str = ",".join(contact_ids)
        return self._request("DELETE", f"/contact/{ids_str}")

    # ── Notes ───────────────────────────────────────────────────────

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
            "GET", f"/contact/{contact_id}/notes", params=params,
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
        """Create a note attached to one or more contacts.

        Args:
            contact_ids: List of 1-10 contact IDs.
            note: Full note text (can contain HTML).
            note_preview: Short plain-text preview.
        """
        body = {
            "contact_ids": contact_ids,
            "note": note,
            "note_preview": note_preview,
        }
        return self._request("POST", "/contacts/notes", json_body=body)

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

    # ── Tags ────────────────────────────────────────────────────────

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

    # ── Tasks ───────────────────────────────────────────────────────

    def create_task(
        self,
        subject: str,
        *,
        notes: str | None = None,
        related_to: list[str] | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a task.

        Args:
            subject: Task title (2-128 chars).
            notes: Additional notes.
            related_to: List of contact IDs to associate.
            due_date: Due date in YYYY-MM-DDTHH:MM:SS format.
        """
        body: dict[str, Any] = {"subject": subject}
        if notes:
            body["notes"] = notes
        if related_to:
            body["related_to"] = related_to
        if due_date:
            body["due_date"] = due_date
        return self._request("POST", "/activities/task", json_body=body)

    # ── Deals ───────────────────────────────────────────────────────

    def list_deals(
        self,
        *,
        per_page: int = 30,
        page: int = 1,
        pipeline_id: str | None = None,
        stage_id: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        """List all deals.

        Args:
            per_page: Results per page (default 30).
            page: Page number (starts at 1).
            pipeline_id: Filter to deals in a specific pipeline.
            stage_id: Filter to deals in a specific pipeline stage.
            owner_id: Filter to deals owned by a specific user.
        """
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if stage_id:
            params["stage_id"] = stage_id
        if owner_id:
            params["owner_id"] = owner_id
        return self._request("GET", "/deals", params=params)

    def get_deal(self, deal_id: str) -> dict[str, Any]:
        """Get a single deal by ID.

        Returns the deal object directly (unwrapped from the
        API's {"resources": [...]} envelope, if present).
        """
        result = self._request("GET", f"/deal/{deal_id}")
        if isinstance(result, dict) and "resources" in result:
            resources = result.get("resources", [])
            if not resources:
                raise ValueError(f"Deal {deal_id} not found")
            return resources[0]
        return result

    def create_deal(
        self,
        fields: dict[str, list[dict[str, str]]],
        *,
        tags: str | None = None,
        pipeline_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new deal.

        Args:
            fields: Dict of field name -> list of {value} dicts.
                Example: {"deal name": [{"value": "Enterprise Deal"}]}
            tags: Comma-separated tags.
            pipeline_id: Pipeline ID to place the deal in.
        """
        body: dict[str, Any] = {"fields": fields}
        if tags:
            body["tags"] = tags
        if pipeline_id:
            body["pipeline_id"] = pipeline_id
        return self._request("POST", "/deal", json_body=body)

    def update_deal(
        self,
        deal_id: str,
        fields: dict[str, list[dict[str, str]]],
    ) -> dict[str, Any]:
        """Update an existing deal."""
        body: dict[str, Any] = {"fields": fields}
        return self._request("PUT", f"/deal/{deal_id}", json_body=body)

    def delete_deal(self, deal_id: str) -> dict[str, Any]:
        """Delete a deal by ID."""
        return self._request("DELETE", f"/deal/{deal_id}")

    def replace_deal_tags(
        self, deal_id: str, tags: list[str],
    ) -> dict[str, Any]:
        """Replace all tags on a deal.

        WARNING: This is a full replace — tags not in the list will be removed.
        """
        body = {"tags": tags}
        return self._request(
            "PUT", f"/deals/{deal_id}/tags", json_body=body,
        )

    # ── Deal Pipelines ────────────────────────────────────────────────

    def list_deal_pipelines(self) -> dict[str, Any]:
        """List all deal pipelines and their stages."""
        return self._request("GET", "/deals/pipelines")

    def create_deal_pipeline(
        self,
        name: str,
        stages: list[str],
    ) -> dict[str, Any]:
        """Create a new deal pipeline.

        Args:
            name: Pipeline name.
            stages: Ordered list of stage names.
        """
        body: dict[str, Any] = {"name": name, "stages": stages}
        return self._request("POST", "/deals/pipelines", json_body=body)

    def update_deal_pipeline(
        self,
        pipeline_id: str,
        *,
        name: str | None = None,
        stages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing deal pipeline."""
        body: dict[str, Any] = {}
        if name:
            body["name"] = name
        if stages is not None:
            body["stages"] = stages
        if not body:
            raise ValueError("Must provide name or stages to update")
        return self._request(
            "PUT", f"/deals/pipelines/{pipeline_id}", json_body=body,
        )

    def delete_deal_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Delete a deal pipeline by ID."""
        return self._request("DELETE", f"/deals/pipelines/{pipeline_id}")

    # ── Messages ────────────────────────────────────────────────────

    def list_messages(
        self,
        *,
        per_page: int = 30,
        page: int = 1,
    ) -> dict[str, Any]:
        """List messages."""
        params = {"per_page": per_page, "page": page}
        return self._request("GET", "/messages", params=params)

    def create_message_draft(
        self,
        *,
        subject: str,
        body: str,
        contact_ids: list[str] | None = None,
        to: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a draft message.

        Args:
            subject: Message subject.
            body: Message body text.
            contact_ids: Contact IDs to associate with the draft.
            to: Recipient email addresses.
        """
        payload: dict[str, Any] = {"subject": subject, "body": body}
        if contact_ids:
            payload["contact_ids"] = contact_ids
        if to:
            payload["to"] = to
        return self._request("POST", "/messages/drafts", json_body=payload)

    # ── Metadata ────────────────────────────────────────────────────

    def list_contact_fields(self) -> dict[str, Any]:
        """List all contact field metadata (tabs, groups, fields)."""
        return self._request("GET", "/contacts/fields")

    def list_deal_fields(self) -> dict[str, Any]:
        """List all deal field metadata (standard and pipeline fields)."""
        return self._request("GET", "/deals/fields")
