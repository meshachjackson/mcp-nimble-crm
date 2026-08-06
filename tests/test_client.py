"""Tests for the Nimble CRM API client.

All HTTP calls are mocked — no real credentials needed. Coverage spans
every documented v1 and v2 endpoint implemented in `NimbleClient`
(binary file upload/download endpoints are out of scope; see the
module docstring in client.py).
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_nimble_crm.client import BASE_URL_V1, BASE_URL_V2, NimbleClient


def _mock_response(json_data=None, status_code=200):
    """Build a MagicMock standing in for a requests.Response."""
    data = {} if json_data is None else json_data
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(data)
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def client():
    """Create a NimbleClient with a fake API key."""
    return NimbleClient(api_key="test-api-key-123")


# ══════════════════════════════════════════════════════════════════
# Init
# ══════════════════════════════════════════════════════════════════


class TestInit:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="API key required"):
            NimbleClient(api_key="")

    def test_reads_env_var(self):
        with patch.dict("os.environ", {"NIMBLE_API_KEY": "env-key"}, clear=False):
            c = NimbleClient()
            assert c.api_key == "env-key"

    def test_sets_auth_header(self, client):
        assert client.session.headers["Authorization"] == "Bearer test-api-key-123"


# ══════════════════════════════════════════════════════════════════
# User / Account
# ══════════════════════════════════════════════════════════════════


class TestGetMyself:
    def test_success(self, client):
        mock_resp = _mock_response({"email": "test@example.com"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_myself()
            m.assert_called_once_with(
                "GET", f"{BASE_URL_V1}/myself", params=None, json=None,
            )
            assert result == {"email": "test@example.com"}


# ══════════════════════════════════════════════════════════════════
# Contacts
# ══════════════════════════════════════════════════════════════════


class TestListContacts:
    def test_basic_list(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contacts()
            call_args = m.call_args
            assert call_args[0] == ("GET", f"{BASE_URL_V1}/contacts")
            params = call_args[1]["params"]
            assert params["record_type"] == "all"
            assert params["per_page"] == 30
            assert params["page"] == 1

    def test_with_keyword(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contacts(keyword="acme")
            assert m.call_args[1]["params"]["keyword"] == "acme"

    def test_person_filter(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contacts(record_type="person")
            assert m.call_args[1]["params"]["record_type"] == "person"

    def test_with_sort(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contacts(sort="name:asc")
            assert m.call_args[1]["params"]["sort"] == "name:asc"


class TestSearchContacts:
    def test_advanced_query(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        query = {"and": [{"first name": {"is": "Jack"}}]}
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.search_contacts(query)
            params = m.call_args[1]["params"]
            assert json.loads(params["query"]) == query


class TestListContactIds:
    def test_basic(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contact_ids(keyword="foo")
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/contacts/ids")
            assert m.call_args[1]["params"]["keyword"] == "foo"


class TestGetContactsByIds:
    def test_multiple_ids(self, client):
        mock_resp = _mock_response({"resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.get_contacts_by_ids(["a1", "a2"], fields="first name")
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/contact")
            params = m.call_args[1]["params"]
            assert params["id"] == "a1,a2"
            assert params["fields"] == "first name"


class TestGetContact:
    def test_by_id(self, client):
        contact_data = {"id": "abc123", "fields": {"first name": [{"value": "Jack"}]}}
        api_response = {"resources": [contact_data]}
        mock_resp = _mock_response(api_response)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_contact("abc123")
            assert "abc123" in m.call_args[0][1]
            assert result["id"] == "abc123"

    def test_not_found_raises(self, client):
        mock_resp = _mock_response({"resources": []})
        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(ValueError, match="not found"):
                client.get_contact("nonexistent")


class TestCreateContact:
    def test_create_person(self, client):
        created = {"id": "new123", "record_type": "person"}
        mock_resp = _mock_response(created, status_code=201)
        fields = {
            "first name": [{"value": "Jack", "modifier": ""}],
            "last name": [{"value": "Daniels", "modifier": ""}],
        }
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_contact("person", fields, tags="lead")
            body = m.call_args[1]["json"]
            assert body["record_type"] == "person"
            assert body["tags"] == "lead"
            assert result["id"] == "new123"

    def test_create_with_owner(self, client):
        mock_resp = _mock_response({"id": "new123"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_contact("company", {}, owner_id="u1")
            assert m.call_args[1]["json"]["owner_id"] == "u1"


class TestUpdateContact:
    def test_update_fields_merge_mode(self, client):
        mock_resp = _mock_response({"id": "abc123"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact(
                "abc123",
                fields={"email": [{"value": "new@test.com", "modifier": "work"}]},
            )
            call_args = m.call_args
            assert call_args[0][0] == "PUT"
            assert "abc123" in call_args[0][1]
            assert call_args[1]["params"]["type"] == "0"

    def test_requires_a_field(self, client):
        with pytest.raises(ValueError, match="Must provide"):
            client.update_contact("abc123")

    def test_replace_mode(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact(
                "abc123",
                fields={"email": [{"value": "new@test.com", "modifier": "work"}]},
                replace=True,
            )
            assert m.call_args[1]["params"]["type"] == "1"

    def test_is_important_flag(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact("abc123", is_important=True)
            assert m.call_args[1]["json"]["is_important"] is True


class TestDeleteContact:
    def test_delete_single_with_options(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contact("abc123", deletion_method="force", cleanup_email_lists=True)
            assert m.call_args[0][0] == "DELETE"
            assert "abc123" in m.call_args[0][1]
            params = m.call_args[1]["params"]
            assert params["deletion_method"] == "force"
            assert params["cleanup_email_lists"] is True


class TestDeleteContacts:
    def test_single_delete(self, client):
        mock_resp = _mock_response({"status": "ok", "data": {"ids": ["abc123"]}})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contacts(["abc123"])
            call_args = m.call_args
            assert call_args[0][0] == "DELETE"
            assert "abc123" in call_args[0][1]

    def test_multi_delete(self, client):
        mock_resp = _mock_response({"status": "ok"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contacts(["id1", "id2", "id3"])
            url = m.call_args[0][1]
            assert "id1,id2,id3" in url


class TestDeleteContactsByQuery:
    def test_by_keyword(self, client):
        mock_resp = _mock_response({"status": "ok"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contacts_by_query(keyword=["acme"], record_type="company")
            assert m.call_args[0] == ("DELETE", f"{BASE_URL_V1}/contacts")
            params = m.call_args[1]["params"]
            assert params["keyword"] == ["acme"]
            assert params["record_type"] == "company"

    def test_by_query(self, client):
        mock_resp = _mock_response({"status": "ok"})
        query = {"and": [{"tag": {"is": "stale"}}]}
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contacts_by_query(query=query, preflight_checks=True)
            params = m.call_args[1]["params"]
            assert json.loads(params["query"]) == query
            assert params["preflight_checks"] is True


class TestLegacyMetadata:
    def test_list_legacy_metadata(self, client):
        mock_resp = _mock_response({"fields": {}, "groups": {}})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contact_fields_metadata_legacy()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/contacts/metadata")


# ══════════════════════════════════════════════════════════════════
# Contact Notes
# ══════════════════════════════════════════════════════════════════


class TestNotes:
    def test_list_notes(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_notes("contact123")
            assert "contact123/notes" in m.call_args[0][1]

    def test_get_note(self, client):
        mock_resp = _mock_response({"id": "note1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.get_note("note1")
            assert "notes/note1" in m.call_args[0][1]

    def test_create_note(self, client):
        mock_resp = _mock_response({"id": "note1"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_note(["c1", "c2"], "Full note", "Preview")
            body = m.call_args[1]["json"]
            assert body["contact_ids"] == ["c1", "c2"]
            assert body["note"] == "Full note"

    def test_create_contact_note_single(self, client):
        mock_resp = _mock_response({"id": "note1"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_contact_note("c1", "Hello", note_preview="Hi")
            assert "c1/notes" in m.call_args[0][1]
            body = m.call_args[1]["json"]
            assert body["note"] == "Hello"
            assert body["note_preview"] == "Hi"

    def test_update_note(self, client):
        mock_resp = _mock_response({"id": "note1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_note("note1", ["c1"], "Updated", "Updated preview")
            assert m.call_args[0][0] == "PUT"

    def test_delete_note(self, client):
        mock_resp = _mock_response({"id": "note1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_note("note1")
            assert m.call_args[0][0] == "DELETE"


# ══════════════════════════════════════════════════════════════════
# Contact Tags
# ══════════════════════════════════════════════════════════════════


class TestTags:
    def test_replace_tags(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.replace_tags("c1", ["Lead", "Healthcare"])
            body = m.call_args[1]["json"]
            assert body["tags"] == ["Lead", "Healthcare"]


# ══════════════════════════════════════════════════════════════════
# Contacts Fields Metadata
# ══════════════════════════════════════════════════════════════════


class TestContactFieldsMetadata:
    def test_list_fields(self, client):
        mock_resp = _mock_response({"tabs": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contact_fields()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/contacts/fields")

    def test_create_field(self, client):
        mock_resp = _mock_response({"tab_id": "t1"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_contact_field(
                name="Twitter Handle",
                field_type={"field_kind": "string"},
                presentation={},
                tab_id="tab1",
                group_id="grp1",
                insert_after=None,
            )
            body = m.call_args[1]["json"]
            assert body["name"] == "Twitter Handle"
            assert body["tab_id"] == "tab1"
            assert body["group_id"] == "grp1"

    def test_update_field(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact_field("field1", name="Renamed")
            assert "field1" in m.call_args[0][1]
            assert m.call_args[1]["json"]["name"] == "Renamed"

    def test_delete_field(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contact_field("field1", preflight_checks=True)
            assert m.call_args[0][0] == "DELETE"
            assert m.call_args[1]["params"]["preflight_checks"] is True

    def test_create_group(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_contact_field_group(
                name="Social", tab_id="tab1", logo_id="logo1", insert_after=None,
            )
            body = m.call_args[1]["json"]
            assert body["name"] == "Social"

    def test_update_group(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact_field_group("grp1", name="Renamed Group")
            assert "grp1" in m.call_args[0][1]

    def test_delete_group(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contact_field_group("grp1", preflight_checks=False)
            assert m.call_args[0][0] == "DELETE"

    def test_create_tab(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_contact_field_tab(
                tab_name="Custom Tab", contact_types=["person"], insert_after=None,
            )
            body = m.call_args[1]["json"]
            assert body["tab_name"] == "Custom Tab"

    def test_update_tab(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact_field_tab("tab1", tab_name="Renamed Tab")
            assert "tab1" in m.call_args[0][1]

    def test_delete_tab(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contact_field_tab("tab1", preflight_checks=True)
            assert m.call_args[0][0] == "DELETE"

    def test_create_choice(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_contact_field_choice(
                "field1", choice_id="1", value="Gold", insert_after=None,
            )
            assert "field1/choices" in m.call_args[0][1]

    def test_update_choice(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact_field_choice("field1", "choice1", value="Platinum")
            assert "field1/choices/choice1" in m.call_args[0][1]

    def test_delete_choice(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contact_field_choice("field1", "choice1", preflight_checks=False)
            assert m.call_args[0][0] == "DELETE"

    def test_unmark_primary(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.unmark_primary_field("c1", field_id="f1", position=0)
            assert m.call_args[0][0] == "DELETE"
            assert "c1/field" in m.call_args[0][1]

    def test_mark_primary(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.mark_primary_field("c1", field_id="f1", position=1)
            assert m.call_args[0][0] == "PUT"


# ══════════════════════════════════════════════════════════════════
# Contact Pipelines / Lead Transitions (v2)
# ══════════════════════════════════════════════════════════════════


class TestContactPipelines:
    def test_list_pipelines(self, client):
        mock_resp = _mock_response({"pipelines": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contact_pipelines()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/contacts/pipelines")

    def test_exit_lead_successful(self, client):
        mock_resp = _mock_response({"id": "lead1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.exit_lead_successful("lead1", "pipe1", notes="Closed won")
            assert m.call_args[0] == (
                "POST", f"{BASE_URL_V2}/leads/lead1/pipe1/successful",
            )
            assert m.call_args[1]["json"]["notes"] == "Closed won"

    def test_exit_lead_unsuccessful(self, client):
        mock_resp = _mock_response({"id": "lead1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.exit_lead_unsuccessful("lead1", "pipe1", lost_reason="Budget")
            assert m.call_args[0] == (
                "POST", f"{BASE_URL_V2}/leads/lead1/pipe1/unsuccessful",
            )
            assert m.call_args[1]["json"]["lost_reason"] == "Budget"

    def test_move_lead_to_stage(self, client):
        mock_resp = _mock_response({"id": "lead1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.move_lead_to_stage("lead1", "pipe1", "stage2")
            assert m.call_args[0] == (
                "POST", f"{BASE_URL_V2}/leads/lead1/pipe1/move",
            )
            assert m.call_args[1]["json"]["stage_id"] == "stage2"

    def test_undo_lead_transition(self, client):
        mock_resp = _mock_response({"id": "lead1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.undo_lead_transition("lead1", "pipe1")
            assert m.call_args[0] == (
                "POST", f"{BASE_URL_V2}/leads/lead1/pipe1/undo",
            )

    def test_clear_lead_transitions(self, client):
        mock_resp = _mock_response({"id": "lead1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.clear_lead_transitions("lead1", "pipe1")
            assert m.call_args[0] == (
                "DELETE", f"{BASE_URL_V2}/leads/lead1/pipe1",
            )


# ══════════════════════════════════════════════════════════════════
# Activities
# ══════════════════════════════════════════════════════════════════


class TestActivities:
    def test_list_pending(self, client):
        mock_resp = _mock_response({"activities": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_activities(direction="pending", limit=10)
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/activities")
            params = m.call_args[1]["params"]
            assert params["direction"] == "pending"
            assert params["limit"] == 10

    def test_list_with_filters(self, client):
        mock_resp = _mock_response({"activities": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_activities(
                direction="past", contacts=["c1"], deals=["d1"], completed=True,
            )
            params = m.call_args[1]["params"]
            assert params["contacts"] == ["c1"]
            assert params["deals"] == ["d1"]
            assert params["completed"] is True


# ══════════════════════════════════════════════════════════════════
# Tasks
# ══════════════════════════════════════════════════════════════════


class TestTasks:
    def test_create_task_minimal(self, client):
        mock_resp = _mock_response({"id": "task1"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_task("Follow up")
            assert m.call_args[0] == ("POST", f"{BASE_URL_V1}/tasks")
            assert m.call_args[1]["json"]["subject"] == "Follow up"

    def test_create_task_with_related(self, client):
        mock_resp = _mock_response({"id": "task1"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_task(
                "Follow up",
                notes="Call them",
                related_contacts=["c1"],
                related_deals=["d1"],
                due_date="2026-04-01T10:00:00",
                tags=["urgent"],
            )
            body = m.call_args[1]["json"]
            assert body["related"] == {"contacts": ["c1"], "deals": ["d1"]}
            assert body["tags"] == ["urgent"]


# ══════════════════════════════════════════════════════════════════
# Deals (v2)
# ══════════════════════════════════════════════════════════════════


class TestListDeals:
    def test_list_deals_default_sort(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deals()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals")
            assert m.call_args[1]["params"]["sort"] == "updated:desc"

    def test_list_deals_with_limit(self, client):
        mock_resp = _mock_response({"meta": {}, "resources": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deals(sort="name:asc", limit=5)
            params = m.call_args[1]["params"]
            assert params["sort"] == "name:asc"
            assert params["limit"] == 5


class TestGetDeal:
    def test_get_deal(self, client):
        mock_resp = _mock_response({"deal_id": "deal1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_deal("deal1")
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/deal1")
            assert result["deal_id"] == "deal1"


class TestCreateDeal:
    def test_create_deal(self, client):
        created = {"deal_id": "deal1"}
        mock_resp = _mock_response(created)
        fields_values = {"field1": [{"value": "Big Deal"}]}
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_deal(
                pipeline_id="pipe1",
                stage_id="stage1",
                fields_values=fields_values,
                tags=["enterprise"],
            )
            assert m.call_args[0] == ("POST", f"{BASE_URL_V2}/deals")
            body = m.call_args[1]["json"]
            assert body["pipeline_id"] == "pipe1"
            assert body["stage_id"] == "stage1"
            assert body["fields_values"] == fields_values
            assert body["tags"] == ["enterprise"]
            assert result["deal_id"] == "deal1"

    def test_create_deal_with_contacts(self, client):
        mock_resp = _mock_response({"deal_id": "deal1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_deal(
                pipeline_id="pipe1",
                stage_id="stage1",
                fields_values={},
                related_contacts=[{"contact_id": "c1", "note": "primary"}],
                currency="USD",
            )
            body = m.call_args[1]["json"]
            assert body["related_contacts"] == [{"contact_id": "c1", "note": "primary"}]
            assert body["currency"] == "USD"


class TestUpdateDeal:
    def test_update_fields_values(self, client):
        mock_resp = _mock_response({"deal_id": "deal1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_deal("deal1", fields_values={"field1": [{"value": "New"}]})
            assert m.call_args[0] == ("PUT", f"{BASE_URL_V2}/deals/deal1")
            assert m.call_args[1]["json"]["fields_values"] == {"field1": [{"value": "New"}]}

    def test_update_requires_a_field(self, client):
        with pytest.raises(ValueError, match="Must provide"):
            client.update_deal("deal1")

    def test_update_stage_and_pipeline(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_deal("deal1", pipeline_id="pipe2", stage_id="stage3")
            body = m.call_args[1]["json"]
            assert body["pipeline_id"] == "pipe2"
            assert body["stage_id"] == "stage3"


class TestDeleteDeal:
    def test_delete_deal(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_deal("deal1")
            assert m.call_args[0] == ("DELETE", f"{BASE_URL_V2}/deals/deal1")


class TestWonLastMonth:
    def test_get_won_last_month(self, client):
        mock_resp = _mock_response({"last_month_won_amount": 100})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_won_deals_last_month()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/widget/won_last_month")
            assert result["last_month_won_amount"] == 100


# ══════════════════════════════════════════════════════════════════
# Deal Tags (v2)
# ══════════════════════════════════════════════════════════════════


class TestDealTags:
    def test_list_deal_tags(self, client):
        mock_resp = _mock_response({"tags": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_tags(starts_with="en")
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/tags")
            assert m.call_args[1]["params"]["starts_with"] == "en"

    def test_add_tags_to_deals(self, client):
        mock_resp = _mock_response({"push_data": {}})
        query = {"and": [{"stage": {"is": "Won"}}]}
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.add_tags_to_deals(query, ["closed"])
            assert m.call_args[0] == ("POST", f"{BASE_URL_V2}/deals/tags")
            body = m.call_args[1]["json"]
            assert body["query"] == query
            assert body["tags"] == ["closed"]

    def test_rename_deal_tag(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.rename_deal_tag("old", "new")
            assert m.call_args[0] == ("PUT", f"{BASE_URL_V2}/deals/tags/old")
            assert m.call_args[1]["json"]["new_tag"] == "new"

    def test_delete_deal_tag(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_deal_tag("stale", preflight_checks=True)
            assert m.call_args[0] == ("DELETE", f"{BASE_URL_V2}/deals/tags/stale")
            assert m.call_args[1]["json"]["preflight_checks"] is True


# ══════════════════════════════════════════════════════════════════
# Deal Notes (v2)
# ══════════════════════════════════════════════════════════════════


class TestDealNotes:
    def test_create_deal_note(self, client):
        mock_resp = _mock_response({"note_id": "n1"}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_deal_note("deal1", "Title", body_text="Body")
            assert m.call_args[0] == ("POST", f"{BASE_URL_V2}/deals/deal1/notes")
            body = m.call_args[1]["json"]
            assert body["title"] == "Title"
            assert body["body"] == "Body"

    def test_update_deal_note(self, client):
        mock_resp = _mock_response({"note_id": "n1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_deal_note("deal1", "n1", title="New title")
            assert m.call_args[0] == ("PUT", f"{BASE_URL_V2}/deals/deal1/notes/n1")

    def test_delete_deal_note(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_deal_note("deal1", "n1")
            assert m.call_args[0] == ("DELETE", f"{BASE_URL_V2}/deals/deal1/notes/n1")

    def test_list_overdue_activities(self, client):
        mock_resp = _mock_response({"activities": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_overdue_activities("deal1", limit=5)
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/deal1/overdue")
            assert m.call_args[1]["params"]["limit"] == 5


# ══════════════════════════════════════════════════════════════════
# Deal Fields (v2)
# ══════════════════════════════════════════════════════════════════


class TestDealFieldsMetadata:
    def test_list_deal_fields(self, client):
        mock_resp = _mock_response({"standard_fields": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_fields()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/fields")

    def test_list_column_catalogue(self, client):
        mock_resp = _mock_response({"items": {}})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_column_catalogue()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/column_catalogue")


# ══════════════════════════════════════════════════════════════════
# Deal Pipelines (v2)
# ══════════════════════════════════════════════════════════════════


class TestDealPipelines:
    def test_list_pipelines(self, client):
        mock_resp = _mock_response({"pipelines": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_pipelines()
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/pipelines")

    def test_get_pipeline(self, client):
        mock_resp = _mock_response({"pipeline_id": "pipe1"})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.get_deal_pipeline("pipe1")
            assert m.call_args[0] == ("GET", f"{BASE_URL_V2}/deals/pipelines/pipe1")

    def test_create_pipeline(self, client):
        created = {"pipeline_id": "pipe1", "name": "Sales"}
        mock_resp = _mock_response(created, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_deal_pipeline(name="Sales", default_currency="USD")
            body = m.call_args[1]["json"]
            assert body["name"] == "Sales"
            assert body["default_currency"] == "USD"
            assert result["pipeline_id"] == "pipe1"

    def test_update_pipeline(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_deal_pipeline("pipe1", name="Renamed")
            call_args = m.call_args
            assert call_args[0][0] == "PUT"
            assert "pipe1" in call_args[0][1]
            assert call_args[1]["json"]["name"] == "Renamed"

    def test_update_pipeline_requires_field(self, client):
        with pytest.raises(ValueError, match="Must provide"):
            client.update_deal_pipeline("pipe1")

    def test_delete_pipeline(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_deal_pipeline("pipe1")
            assert m.call_args[0] == ("DELETE", f"{BASE_URL_V2}/deals/pipelines/pipe1")

    def test_list_pipeline_deals_by_stage(self, client):
        mock_resp = _mock_response({"stages": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_pipeline_deals_by_stage("pipe1", stage_id="s1", stuck=True)
            assert "pipe1/deals" in m.call_args[0][1]
            params = m.call_args[1]["params"]
            assert params["stage_id"] == "s1"
            assert params["stuck"] is True

    def test_list_pipeline_deals_by_owner(self, client):
        mock_resp = _mock_response({"groups": []})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_pipeline_deals_by_owner("pipe1")
            assert "pipe1/owners" in m.call_args[0][1]

    def test_archive_pipeline(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.archive_deal_pipeline("pipe1")
            assert m.call_args[0] == (
                "POST", f"{BASE_URL_V2}/deals/pipelines/pipe1/archive",
            )

    def test_unarchive_pipeline(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.unarchive_deal_pipeline("pipe1")
            assert m.call_args[0] == (
                "POST", f"{BASE_URL_V2}/deals/pipelines/pipe1/unarchive",
            )

    def test_add_lost_reason(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.add_pipeline_lost_reason("pipe1", "Too expensive")
            assert m.call_args[1]["json"]["reason"] == "Too expensive"


class TestPipelineStages:
    def test_create_stage(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_pipeline_stage(
                "pipe1", name="Negotiation", expected_days=5, default_probability=60,
            )
            assert "pipe1/stages" in m.call_args[0][1]
            body = m.call_args[1]["json"]
            assert body["name"] == "Negotiation"
            assert body["expected_days"] == 5
            assert body["default_probability"] == 60

    def test_update_stage(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_pipeline_stage("pipe1", "stage1", name="Renamed Stage")
            assert "pipe1/stages/stage1" in m.call_args[0][1]

    def test_archive_stage(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.archive_pipeline_stage("pipe1", "stage1")
            assert m.call_args[0][0] == "DELETE"
            assert "pipe1/stages/stage1" in m.call_args[0][1]


class TestPipelineFields:
    def test_create_field(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_pipeline_field(
                "pipe1", name="Region",
                field_type={"field_kind": "string"}, presentation={},
            )
            assert "pipe1/fields" in m.call_args[0][1]
            assert m.call_args[1]["json"]["name"] == "Region"

    def test_update_field(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_pipeline_field("pipe1", "field1", name="Renamed")
            assert "pipe1/fields/field1" in m.call_args[0][1]

    def test_delete_field(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_pipeline_field("pipe1", "field1", preflight_checks=True)
            assert m.call_args[0][0] == "DELETE"
            assert m.call_args[1]["json"]["preflight_checks"] is True

    def test_create_field_choice(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_pipeline_field_choice(
                "pipe1", "field1", {"id": "1", "value": "West"},
            )
            assert "pipe1/fields/field1/choices" in m.call_args[0][1]

    def test_update_field_choice(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_pipeline_field_choice("pipe1", "field1", "choice1", value="East")
            assert "choices/choice1" in m.call_args[0][1]

    def test_delete_field_choice(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_pipeline_field_choice(
                "pipe1", "field1", "choice1", preflight_checks=False,
            )
            assert m.call_args[0][0] == "DELETE"

    def test_create_field_group(self, client):
        mock_resp = _mock_response({}, status_code=201)
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_pipeline_field_group("pipe1", group_name="Extra Info")
            assert "pipe1/groups" in m.call_args[0][1]
            assert m.call_args[1]["json"]["group_name"] == "Extra Info"

    def test_update_field_group(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_pipeline_field_group("pipe1", "grp1", group_name="Renamed")
            assert "pipe1/groups/grp1" in m.call_args[0][1]

    def test_delete_field_group(self, client):
        mock_resp = _mock_response({})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_pipeline_field_group("pipe1", "grp1")
            assert m.call_args[0][0] == "DELETE"
            assert "pipe1/groups/grp1" in m.call_args[0][1]


# ══════════════════════════════════════════════════════════════════
# Messages
# ══════════════════════════════════════════════════════════════════


class TestMessages:
    def test_list_message_drafts(self, client):
        mock_resp = _mock_response({"drafts": [], "meta": {}})
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_message_drafts(recipients="a@b.com", page=1, per_page=10)
            assert m.call_args[0] == ("GET", f"{BASE_URL_V1}/messages/drafts")
            params = m.call_args[1]["params"]
            assert params["recipients"] == "a@b.com"
            assert params["page"] == 1

    def test_create_message_draft(self, client):
        created = {"draft_id": "draft1"}
        mock_resp = _mock_response(created)
        recipients = [{"account_type": "email", "identifier": "a@example.com"}]
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_message_draft(
                subject="Hello", body="Hi there", recipients=recipients,
            )
            assert m.call_args[0] == ("POST", f"{BASE_URL_V1}/messages/drafts")
            body = m.call_args[1]["json"]
            assert body["subject"] == "Hello"
            assert body["recipients"] == recipients
            assert result["draft_id"] == "draft1"


# ══════════════════════════════════════════════════════════════════
# Error Handling
# ══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    def test_http_error_propagates(self, client):
        from requests.exceptions import HTTPError

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = HTTPError("404 Not Found")

        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(HTTPError):
                client.get_contact("nonexistent")

    def test_empty_response(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp):
            result = client.delete_deal("deal1")
            assert result == {}
