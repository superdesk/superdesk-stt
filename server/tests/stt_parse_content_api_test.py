# -*- coding: utf-8 -*-
import json
import pytest

from superdesk.io.commands.update_ingest import LAST_ITEM_UPDATE
from stt.io.feeding_services.stt_parse_content_api import STTContentAPIService


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    """
    Minimal stand‑in for requests.Session.
    - Provide .headers (dict), .auth, .get(...) returning page payloads
    - Record each call for assertions
    """
    def __init__(self, pages_by_num):
        self._pages = pages_by_num  # {page_number: payload}
        self.headers = {}
        self.auth = None
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        page = int(params.get("page", 1))
        payload = self._pages.get(page, {"_items": [], "_meta": {"total": 0}, "_links": {}})
        return FakeResponse(payload)


@pytest.fixture
def service():
    return STTContentAPIService()


def _two_pages():
    # Page 1 (2 items, has next)
    p1 = {
        "_items": [
            {"_id": "A", "versioncreated": "2024-01-02T10:00:00Z"},
            {"_id": "B", "versioncreated": "2024-01-03T09:00:00Z"},
        ],
        "_meta": {"total": 3},
        "_links": {"next": {"href": "/contentapi/items?page=2"}},
    }
    # Page 2 (1 item, no next)
    p2 = {
        "_items": [{"_id": "C", "versioncreated": "2024-01-04T08:00:00Z"}],
        "_meta": {"total": 3},
        "_links": {},
    }
    return {1: p1, 2: p2}


def test_update_yields_items_updates_bookmark_token_auth_and_url(monkeypatch, service):
    fake = FakeSession(_two_pages())

    # Patch requests.Session
    import requests
    monkeypatch.setattr(requests, "Session", lambda: fake)

    provider = {
        "config": {
            "base_url": "https://api.example/contentapi/",  # note trailing slash handling in code
            "endpoint": "items",
            "page_size": 2,
            "since_field": "versioncreated",
            "initial_since": "2024-01-01T00:00:00Z",
            "auth": {"type": "token", "token": "Bearer ABC123"},
            "timeout": 7,
        }
    }
    update = {}

    items = list(service._update(provider, update))

    # yielded all items in order across pages
    assert [it["_id"] for it in items] == ["A", "B", "C"]

    # normalized _type
    assert all(it["_type"] == "content_api" for it in items)

    # bookmark moved to newest versioncreated
    assert update[LAST_ITEM_UPDATE] == "2024-01-04T08:00:00Z"

    # headers & auth
    assert fake.headers["Accept"] == "application/json"
    assert fake.headers["Authorization"] == "Bearer ABC123"

    # first call: check where JSON, sort, page, max_results, timeout, and URL built correctly
    first = fake.calls[0]
    assert first["url"] == "https://api.example/contentapi/items"
    assert first["params"]["sort"] == "versioncreated"
    assert first["params"]["page"] == 1
    assert first["params"]["max_results"] == 2
    where = json.loads(first["params"]["where"])
    assert where["versioncreated"]["$gt"] == "2024-01-01T00:00:00Z"


def test_basic_auth_applied(monkeypatch, service):
    # no items so it exits quickly
    fake = FakeSession({1: {"_items": [], "_meta": {"total": 0}, "_links": {}}})

    import requests
    monkeypatch.setattr(requests, "Session", lambda: fake)

    provider = {
        "config": {
            "base_url": "https://api.example/contentapi/",
            "endpoint": "items",
            "auth": {"type": "basic", "username": "u", "password": "p"},
        }
    }
    update = {LAST_ITEM_UPDATE: "2024-01-01T00:00:00Z"}

    list(service._update(provider, update))

    assert fake.auth == ("u", "p")


def test_extra_where_and_custom_since_field(monkeypatch, service):
    fake = FakeSession({
        1: {
            "_items": [{"_id": "X", "firstcreated": "2024-02-01T00:00:00Z"}],
            "_meta": {"total": 1},
            "_links": {},
        }
    })

    import requests
    monkeypatch.setattr(requests, "Session", lambda: fake)

    provider = {
        "config": {
            "base_url": "https://api.example/contentapi/",
            "endpoint": "items",
            "since_field": "firstcreated",
            "extra_where": {"state": "published", "_type": "text"},
        }
    }
    update = {LAST_ITEM_UPDATE: "2024-01-15T00:00:00Z"}

    items = list(service._update(provider, update))
    assert len(items) == 1
    assert update[LAST_ITEM_UPDATE] == "2024-02-01T00:00:00Z"

    call = fake.calls[0]
    where = json.loads(call["params"]["where"])
    assert where["state"] == "published"
    assert where["_type"] == "text"
    assert where["firstcreated"]["$gt"] == "2024-01-15T00:00:00Z"


def test_no_new_items_keeps_bookmark_and_logs(monkeypatch, service, caplog):
    fake = FakeSession({1: {"_items": [], "_meta": {"total": 0}, "_links": {}}})

    import requests
    monkeypatch.setattr(requests, "Session", lambda: fake)

    provider = {
        "config": {
            "base_url": "https://api.example/contentapi/",
            "endpoint": "items",
        }
    }
    prev = "2024-01-10T00:00:00Z"
    update = {LAST_ITEM_UPDATE: prev}

    with caplog.at_level("INFO"):
        out = list(service._update(provider, update))

    assert out == []
    assert update[LAST_ITEM_UPDATE] == prev
    assert any("nothing new since=" in r.message for r in caplog.records)