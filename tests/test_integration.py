"""Integration tests against a live Nimble CRM instance.

These tests require a valid NIMBLE_API_KEY environment variable.
They are skipped automatically when the key is not set.

Run:  NIMBLE_API_KEY=<key> pytest tests/test_integration.py -v
  or: pytest -m integration -v  (if key is in environment)

Tests create real records and clean up after themselves.
"""

import json
import os
import time

import pytest

from mcp_nimble_crm.client import NimbleClient

# Skip entire module if no API key
pytestmark = pytest.mark.integration
NIMBLE_API_KEY = os.environ.get("NIMBLE_API_KEY", "")

skip_no_key = pytest.mark.skipif(
    not NIMBLE_API_KEY,
    reason="NIMBLE_API_KEY not set — skipping integration tests",
)


@pytest.fixture(scope="module")
def client():
    """Create a real NimbleClient for integration tests."""
    return NimbleClient(api_key=NIMBLE_API_KEY)


# ── Read-Only Tests (safe, no side effects) ─────────────────────────


@skip_no_key
class TestAccountReadOnly:
    def test_get_myself(self, client):
        result = client.get_myself()
        assert "email" in result
        assert "user_id" in result
        assert "company_id" in result
        print(f"  Authenticated as: {result['email']}")

    def test_list_contact_fields(self, client):
        result = client.list_contact_fields()
        # Should return field metadata (varies by account)
        assert result is not None
        assert isinstance(result, (dict, list))
        print(f"  Fields metadata type: {type(result).__name__}")


@skip_no_key
class TestContactsReadOnly:
    def test_list_contacts(self, client):
        result = client.list_contacts(per_page=5, page=1)
        assert "meta" in result
        assert "resources" in result
        total = result["meta"].get("total", 0)
        count = len(result["resources"])
        print(f"  Total contacts: {total}, returned: {count}")

    def test_list_contacts_person_filter(self, client):
        result = client.list_contacts(record_type="person", per_page=5)
        assert "resources" in result
        for contact in result["resources"]:
            assert contact.get("record_type") == "person"

    def test_list_contacts_company_filter(self, client):
        result = client.list_contacts(record_type="company", per_page=5)
        assert "resources" in result
        for contact in result["resources"]:
            assert contact.get("record_type") == "company"

    def test_list_contacts_keyword_search(self, client):
        # Search for something likely to exist (the authenticated user's name)
        myself = client.get_myself()
        name = myself.get("name", "").split()[0]  # first name
        if name:
            result = client.list_contacts(keyword=name, per_page=5)
            assert "meta" in result
            print(f"  Search for '{name}': {result['meta'].get('total', 0)} results")


# ── Write Tests (create → verify → cleanup) ─────────────────────────

TEST_PREFIX = "MCP_INTEG_TEST"  # Tag prefix to identify test records


@skip_no_key
class TestContactCRUD:
    """Full create → read → update → delete lifecycle."""

    def test_contact_lifecycle(self, client):
        # CREATE
        fields = {
            "first name": [{"value": "Integration", "modifier": ""}],
            "last name": [{"value": "TestContact", "modifier": ""}],
            "email": [{"value": "integ-test@example.com", "modifier": "work"}],
        }
        created = client.create_contact(
            "person", fields, tags=TEST_PREFIX,
        )
        contact_id = created.get("id")
        assert contact_id, f"Create failed: {created}"
        print(f"  Created contact: {contact_id}")

        try:
            # READ
            fetched = client.get_contact(contact_id)
            assert fetched["id"] == contact_id
            first_names = fetched.get("fields", {}).get("first name", [])
            assert any(f["value"] == "Integration" for f in first_names)
            print(f"  Read verified: first name = Integration")

            # UPDATE
            updated = client.update_contact(
                contact_id,
                fields={"last name": [{"value": "UpdatedName", "modifier": ""}]},
            )
            # Re-fetch to verify
            refetched = client.get_contact(contact_id)
            last_names = refetched.get("fields", {}).get("last name", [])
            assert any(f["value"] == "UpdatedName" for f in last_names)
            print(f"  Update verified: last name = UpdatedName")

        finally:
            # DELETE (always clean up)
            client.delete_contacts([contact_id])
            print(f"  Deleted contact: {contact_id}")

            # Verify deletion — API returns empty resources, client raises ValueError
            with pytest.raises(ValueError, match="not found"):
                client.get_contact(contact_id)
            print(f"  Deletion confirmed (empty resources on re-fetch)")


@skip_no_key
class TestCompanyCRUD:
    def test_company_lifecycle(self, client):
        fields = {
            "company name": [{"value": f"{TEST_PREFIX} Corp", "modifier": ""}],
        }
        created = client.create_contact("company", fields, tags=TEST_PREFIX)
        contact_id = created.get("id")
        assert contact_id, f"Create failed: {created}"
        print(f"  Created company: {contact_id}")

        try:
            fetched = client.get_contact(contact_id)
            assert fetched["record_type"] == "company"
            print(f"  Verified record_type = company")
        finally:
            client.delete_contacts([contact_id])
            print(f"  Deleted company: {contact_id}")


@skip_no_key
class TestNoteCRUD:
    def test_note_lifecycle(self, client):
        # First create a contact to attach notes to
        fields = {
            "first name": [{"value": "NoteTest", "modifier": ""}],
            "last name": [{"value": "Contact", "modifier": ""}],
        }
        contact = client.create_contact("person", fields, tags=TEST_PREFIX)
        contact_id = contact["id"]
        print(f"  Created contact for notes: {contact_id}")

        try:
            # CREATE NOTE
            note = client.create_note(
                [contact_id],
                f"<p>{TEST_PREFIX}: Integration test note body</p>",
                f"{TEST_PREFIX}: Test note",
            )
            note_id = note.get("id")
            assert note_id, f"Note create failed: {note}"
            print(f"  Created note: {note_id}")

            # LIST NOTES
            notes_list = client.list_notes(contact_id)
            assert "resources" in notes_list
            note_ids = [n["id"] for n in notes_list["resources"]]
            assert note_id in note_ids
            print(f"  Listed notes: found {len(notes_list['resources'])}")

            # GET NOTE
            fetched_note = client.get_note(note_id)
            assert fetched_note["id"] == note_id
            assert TEST_PREFIX in fetched_note.get("note_preview", "")
            print(f"  Fetched note verified")

            # UPDATE NOTE
            client.update_note(
                note_id,
                [contact_id],
                f"<p>{TEST_PREFIX}: Updated note body</p>",
                f"{TEST_PREFIX}: Updated note",
            )
            updated_note = client.get_note(note_id)
            assert "Updated" in updated_note.get("note_preview", "")
            print(f"  Updated note verified")

            # DELETE NOTE
            client.delete_note(note_id)
            print(f"  Deleted note: {note_id}")

        finally:
            client.delete_contacts([contact_id])
            print(f"  Cleaned up contact: {contact_id}")


@skip_no_key
class TestTagOperations:
    def test_replace_tags(self, client):
        # Create a contact
        fields = {
            "first name": [{"value": "TagTest", "modifier": ""}],
            "last name": [{"value": "Contact", "modifier": ""}],
        }
        contact = client.create_contact("person", fields, tags=TEST_PREFIX)
        contact_id = contact["id"]

        try:
            # Replace tags
            client.replace_tags(contact_id, ["Alpha", "Beta", "Gamma"])

            # Verify
            fetched = client.get_contact(contact_id)
            tag_names = [t["tag"] for t in fetched.get("tags", [])]
            assert "Alpha" in tag_names
            assert "Beta" in tag_names
            assert "Gamma" in tag_names
            # Original TEST_PREFIX tag should be gone (replace is destructive)
            assert TEST_PREFIX not in tag_names
            print(f"  Tags replaced: {tag_names}")

        finally:
            client.delete_contacts([contact_id])


@skip_no_key
class TestTaskCreate:
    def test_create_task(self, client):
        # Create a contact to relate the task to
        fields = {
            "first name": [{"value": "TaskTest", "modifier": ""}],
            "last name": [{"value": "Contact", "modifier": ""}],
        }
        contact = client.create_contact("person", fields, tags=TEST_PREFIX)
        contact_id = contact["id"]

        try:
            task = client.create_task(
                subject=f"{TEST_PREFIX}: Follow up call",
                notes="Integration test task",
                related_to=[contact_id],
                due_date="2026-12-31T10:00:00",
            )
            assert task.get("id"), f"Task create failed: {task}"
            assert task["subject"] == f"{TEST_PREFIX}: Follow up call"
            print(f"  Created task: {task['id']}")
            # Note: no delete endpoint for tasks in the API

        finally:
            client.delete_contacts([contact_id])


@skip_no_key
class TestSearchContacts:
    def test_advanced_search(self, client):
        # Create a uniquely-named contact to search for
        unique_name = f"{TEST_PREFIX}_{int(time.time())}"
        fields = {
            "first name": [{"value": unique_name, "modifier": ""}],
            "last name": [{"value": "Searchable", "modifier": ""}],
        }
        contact = client.create_contact("person", fields, tags=TEST_PREFIX)
        contact_id = contact["id"]

        try:
            # Brief pause for indexing
            time.sleep(2)

            # Search by the unique first name
            result = client.search_contacts(
                {"and": [{"first name": {"is": unique_name}}]},
            )
            found_ids = [r["id"] for r in result.get("resources", [])]
            assert contact_id in found_ids, (
                f"Expected {contact_id} in search results, got {found_ids}"
            )
            print(f"  Advanced search found contact: {contact_id}")

        finally:
            client.delete_contacts([contact_id])


@skip_no_key
class TestDeals:
    def test_list_deals(self, client):
        result = client.list_deals(per_page=5)
        # Deals endpoint may return different structure — just verify no error
        assert result is not None
        print(f"  Deals response type: {type(result).__name__}")
        if isinstance(result, dict) and "resources" in result:
            print(f"  Total deals: {result.get('meta', {}).get('total', 'unknown')}")


# ── Cleanup Safety Net ──────────────────────────────────────────────


@skip_no_key
class TestCleanupOrphans:
    """Find and delete any test records left from failed runs."""

    def test_cleanup_orphaned_test_contacts(self, client):
        result = client.list_contacts(keyword=TEST_PREFIX, per_page=100)
        orphans = [r["id"] for r in result.get("resources", [])]
        if orphans:
            client.delete_contacts(orphans)
            print(f"  Cleaned up {len(orphans)} orphaned test contacts")
        else:
            print(f"  No orphaned test contacts found")
