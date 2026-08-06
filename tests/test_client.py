"""Tests for the Nimble CRM API client.

All HTTP calls are mocked — no real credentials needed.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_nimble_crm.client import NimbleClient


@pytest.fixture
def client():
    """Create a NimbleClient with a fake API key."""
    return NimbleClient(api_key="test-api-key-123")


class TestInit:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="API key required"):
            NimbleClient(api_key="")

    def test_reads_env_var(self):
        with patch.dict("os.environ", {"NIMBLE_API_KEY": "env-key"}):
            c = NimbleClient()
            assert c.api_key == "env-key"

    def test_sets_auth_header(self, client):
        assert client.session.headers["Authorization"] == "Bearer test-api-key-123"


class TestGetMyself:
    def test_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"email": "test@example.com"}'
        mock_resp.json.return_value = {"email": "test@example.com"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_myself()
            m.assert_called_once_with(
                "GET", "https://app.nimble.com/api/v1/myself",
                params=None, json=None,
            )
            assert result == {"email": "test@example.com"}


class TestListContacts:
    def test_basic_list(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.list_contacts()
            m.assert_called_once()
            call_args = m.call_args
            assert call_args[0] == ("GET", "https://app.nimble.com/api/v1/contacts")
            params = call_args[1]["params"]
            assert params["record_type"] == "all"
            assert params["per_page"] == 30
            assert params["page"] == 1

    def test_with_keyword(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contacts(keyword="acme")
            params = m.call_args[1]["params"]
            assert params["keyword"] == "acme"

    def test_person_filter(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_contacts(record_type="person")
            params = m.call_args[1]["params"]
            assert params["record_type"] == "person"


class TestSearchContacts:
    def test_advanced_query(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        query = {"and": [{"first name": {"is": "Jack"}}]}

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.search_contacts(query)
            params = m.call_args[1]["params"]
            assert json.loads(params["query"]) == query


class TestGetContact:
    def test_by_id(self, client):
        # API wraps single contact in {"resources": [contact]}
        contact_data = {"id": "abc123", "fields": {"first name": [{"value": "Jack"}]}}
        api_response = {"resources": [contact_data]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(api_response)
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_contact("abc123")
            assert "abc123" in m.call_args[0][1]
            assert result["id"] == "abc123"

    def test_not_found_raises(self, client):
        api_response = {"resources": []}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(api_response)
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(ValueError, match="not found"):
                client.get_contact("nonexistent")


class TestCreateContact:
    def test_create_person(self, client):
        created = {"id": "new123", "record_type": "person"}
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = json.dumps(created)
        mock_resp.json.return_value = created
        mock_resp.raise_for_status = MagicMock()

        fields = {
            "first name": [{"value": "Jack", "modifier": ""}],
            "last name": [{"value": "Daniels", "modifier": ""}],
        }

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_contact("person", fields, tags="lead")
            call_args = m.call_args
            assert call_args[0][0] == "POST"
            body = call_args[1]["json"]
            assert body["record_type"] == "person"
            assert body["tags"] == "lead"
            assert result["id"] == "new123"


class TestUpdateContact:
    def test_update_fields(self, client):
        updated = {"id": "abc123", "fields": {"email": [{"value": "new@test.com"}]}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(updated)
        mock_resp.json.return_value = updated
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact(
                "abc123",
                fields={"email": [{"value": "new@test.com", "modifier": "work"}]},
            )
            call_args = m.call_args
            assert call_args[0][0] == "PUT"
            assert "abc123" in call_args[0][1]

    def test_requires_fields_or_avatar(self, client):
        with pytest.raises(ValueError, match="Must provide"):
            client.update_contact("abc123")

    def test_replace_mode(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{}'
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.update_contact(
                "abc123",
                fields={"email": [{"value": "new@test.com", "modifier": "work"}]},
                replace=True,
            )
            params = m.call_args[1]["params"]
            assert params["replace"] == 1


class TestDeleteContacts:
    def test_single_delete(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "ok", "data": {"ids": ["abc123"]}}'
        mock_resp.json.return_value = {"status": "ok", "data": {"ids": ["abc123"]}}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contacts(["abc123"])
            call_args = m.call_args
            assert call_args[0][0] == "DELETE"
            assert "abc123" in call_args[0][1]

    def test_multi_delete(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "ok"}'
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_contacts(["id1", "id2", "id3"])
            url = m.call_args[0][1]
            assert "id1,id2,id3" in url


class TestNotes:
    def test_list_notes(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_notes("contact123")
            url = m.call_args[0][1]
            assert "contact123/notes" in url

    def test_create_note(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"id": "note1"}'
        mock_resp.json.return_value = {"id": "note1"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_note(["c1", "c2"], "Full note", "Preview")
            body = m.call_args[1]["json"]
            assert body["contact_ids"] == ["c1", "c2"]
            assert body["note"] == "Full note"

    def test_delete_note(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"id": "note1"}'
        mock_resp.json.return_value = {"id": "note1"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_note("note1")
            assert m.call_args[0][0] == "DELETE"


class TestTags:
    def test_replace_tags(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{}'
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.replace_tags("c1", ["Lead", "Healthcare"])
            body = m.call_args[1]["json"]
            assert body["tags"] == ["Lead", "Healthcare"]


class TestTasks:
    def test_create_task(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"id": "task1"}'
        mock_resp.json.return_value = {"id": "task1"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_task(
                "Follow up", notes="Call them", related_to=["c1"],
                due_date="2026-04-01T10:00:00",
            )
            body = m.call_args[1]["json"]
            assert body["subject"] == "Follow up"
            assert body["related_to"] == ["c1"]


class TestDeals:
    def test_list_deals(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deals()
            assert "/deals" in m.call_args[0][1]

    def test_create_deal(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"id": "deal1"}'
        mock_resp.json.return_value = {"id": "deal1"}
        mock_resp.raise_for_status = MagicMock()

        fields = {"deal name": [{"value": "Big Deal"}]}
        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.create_deal(fields, tags="enterprise", pipeline_id="pipe1")
            body = m.call_args[1]["json"]
            assert body["fields"]["deal name"][0]["value"] == "Big Deal"
            assert body["tags"] == "enterprise"

    def test_delete_deal(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{}'
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_deal("deal1")
            assert m.call_args[0][0] == "DELETE"


class TestGetDeal:
    def test_get_deal_direct_object(self, client):
        deal_data = {"id": "deal1", "fields": {"deal name": [{"value": "Big Deal"}]}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(deal_data)
        mock_resp.json.return_value = deal_data
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.get_deal("deal1")
            assert "deal1" in m.call_args[0][1]
            assert result["id"] == "deal1"

    def test_get_deal_wrapped_resources(self, client):
        deal_data = {"id": "deal1"}
        api_response = {"resources": [deal_data]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(api_response)
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp):
            result = client.get_deal("deal1")
            assert result["id"] == "deal1"

    def test_get_deal_not_found_raises(self, client):
        api_response = {"resources": []}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(api_response)
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(ValueError, match="not found"):
                client.get_deal("nonexistent")


class TestListDealsFilters:
    def test_list_deals_with_filters(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deals(pipeline_id="p1", stage_id="s1", owner_id="u1")
            params = m.call_args[1]["params"]
            assert params["pipeline_id"] == "p1"
            assert params["stage_id"] == "s1"
            assert params["owner_id"] == "u1"


class TestDealTags:
    def test_replace_deal_tags(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{}'
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.replace_deal_tags("deal1", ["Enterprise", "Hot"])
            body = m.call_args[1]["json"]
            assert body["tags"] == ["Enterprise", "Hot"]
            assert "deal1" in m.call_args[0][1]


class TestDealPipelines:
    def test_list_pipelines(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"resources": []}'
        mock_resp.json.return_value = {"resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_pipelines()
            assert "/deals/pipelines" in m.call_args[0][1]

    def test_create_pipeline(self, client):
        created = {"id": "pipe1", "name": "Sales"}
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = json.dumps(created)
        mock_resp.json.return_value = created
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_deal_pipeline("Sales", ["Lead", "Proposal", "Won"])
            body = m.call_args[1]["json"]
            assert body["name"] == "Sales"
            assert body["stages"] == ["Lead", "Proposal", "Won"]
            assert result["id"] == "pipe1"

    def test_update_pipeline(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{}'
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

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
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{}'
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.delete_deal_pipeline("pipe1")
            assert m.call_args[0][0] == "DELETE"
            assert "pipe1" in m.call_args[0][1]


class TestMessages:
    def test_list_messages(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"meta": {}, "resources": []}'
        mock_resp.json.return_value = {"meta": {}, "resources": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_messages()
            assert "/messages" in m.call_args[0][1]

    def test_create_message_draft(self, client):
        created = {"id": "draft1"}
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = json.dumps(created)
        mock_resp.json.return_value = created
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            result = client.create_message_draft(
                subject="Hello", body="Hi there", to=["a@example.com"],
            )
            body = m.call_args[1]["json"]
            assert body["subject"] == "Hello"
            assert body["to"] == ["a@example.com"]
            assert result["id"] == "draft1"


class TestDealFieldsMetadata:
    def test_list_deal_fields(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"tabs": []}'
        mock_resp.json.return_value = {"tabs": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "request", return_value=mock_resp) as m:
            client.list_deal_fields()
            assert "/deals/fields" in m.call_args[0][1]


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
