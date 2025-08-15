# -*- coding: utf-8 -*-
import pytest

from stt.io.feeding_services.stt_content_api import STTContentAPIService


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class MockRequests:
    """Mock requests module for testing."""

    def __init__(self, responses):
        self.responses = responses  # list of responses to return in order
        self.calls = []
        self.call_index = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(
            {"url": url, "params": params, "headers": headers, "timeout": timeout}
        )

        if self.call_index < len(self.responses):
            response = self.responses[self.call_index]
            self.call_index += 1
            return FakeResponse(response)
        else:
            # Return empty response for additional calls
            return FakeResponse({"_items": [], "_links": {}})


@pytest.fixture
def service():
    return STTContentAPIService()


def test_fetch_data_basic_functionality(monkeypatch, service):
    """Test basic _fetch_data functionality with simple pagination."""

    # Mock responses for two pages
    responses = [
        # Page 1 - has next link
        {
            "_items": [
                {
                    "_id": "A",
                    "versioncreated": "2024-01-02T10:00:00Z",
                    "headline": "First item",
                },
                {
                    "_id": "B",
                    "versioncreated": "2024-01-03T09:00:00Z",
                    "headline": "Second item",
                },
            ],
            "_links": {"next": {"href": "/contentapi/items?page=2"}},
        },
        # Page 2 - no next link
        {
            "_items": [
                {
                    "_id": "C",
                    "versioncreated": "2024-01-04T08:00:00Z",
                    "headline": "Third item",
                }
            ],
            "_links": {},
        },
    ]

    mock_requests = MockRequests(responses)

    # Patch requests module
    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "Bearer ABC123",
        }
    }

    items = service._fetch_data(provider, "2024-01-01T00:00:00Z")

    # Should get all items from both pages
    assert len(items) == 3
    assert [item["_id"] for item in items] == ["A", "B", "C"]

    # Check that two requests were made
    assert len(mock_requests.calls) == 2

    # Check first request
    first_call = mock_requests.calls[0]
    assert first_call["url"] == "https://api.example.com/contentapi/items"
    assert first_call["params"]["page"] == 1
    assert first_call["headers"]["Authorization"] == "Bearer ABC123"
    assert first_call["headers"]["Accept"] == "application/json"
    assert first_call["timeout"] == 30

    # Check second request
    second_call = mock_requests.calls[1]
    assert second_call["params"]["page"] == 2


def test_fetch_data_single_page(monkeypatch, service):
    """Test _fetch_data with single page response (no next link)."""

    responses = [
        {
            "_items": [
                {
                    "_id": "SINGLE",
                    "versioncreated": "2024-01-01T12:00:00Z",
                    "headline": "Single item",
                }
            ],
            "_links": {},  # No next link
        }
    ]

    mock_requests = MockRequests(responses)

    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "test_token",  # Test without Bearer prefix
        }
    }

    items = service._fetch_data(provider, "")

    assert len(items) == 1
    assert items[0]["_id"] == "SINGLE"

    # Should only make one request
    assert len(mock_requests.calls) == 1

    # Check that Bearer prefix was added
    assert mock_requests.calls[0]["headers"]["Authorization"] == "Bearer test_token"


def test_fetch_data_empty_response(monkeypatch, service):
    """Test _fetch_data when API returns empty items."""

    responses = [
        {
            "_items": [],
            "_links": {},
        }
    ]

    mock_requests = MockRequests(responses)

    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "Bearer TOKEN123",
        }
    }

    items = service._fetch_data(provider, "")

    assert len(items) == 0
    assert len(mock_requests.calls) == 1


def test_fetch_data_api_response_formats(monkeypatch, service):
    """Test different API response formats (list vs dict with _items)."""

    responses = [
        # Test list format
        [
            {"_id": "LIST1", "headline": "From list"},
            {"_id": "LIST2", "headline": "From list 2"},
        ]
    ]

    mock_requests = MockRequests(responses)

    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "Bearer TOKEN123",
        }
    }

    items = service._fetch_data(provider, "")

    assert len(items) == 2
    assert [item["_id"] for item in items] == ["LIST1", "LIST2"]


def test_fetch_data_items_field_response(monkeypatch, service):
    """Test API response with 'items' field instead of '_items'."""

    responses = [
        {
            "items": [
                {"_id": "ITEMS1", "headline": "From items field"},
                {"_id": "ITEMS2", "headline": "From items field 2"},
            ],
            "_links": {},
        }
    ]

    mock_requests = MockRequests(responses)

    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "Bearer TOKEN123",
        }
    }

    items = service._fetch_data(provider, "")

    assert len(items) == 2
    assert [item["_id"] for item in items] == ["ITEMS1", "ITEMS2"]


def test_bearer_token_helper():
    """Test the _bearer helper method."""
    service = STTContentAPIService()

    # Test with raw token
    assert service._bearer("raw_token") == "Bearer raw_token"

    # Test with Bearer prefix already
    assert service._bearer("Bearer existing_token") == "Bearer existing_token"


def test_headers_helper():
    """Test the _headers helper method."""
    service = STTContentAPIService()

    headers = service._headers("test_api_key")

    assert headers["Accept"] == "application/json"
    assert headers["Authorization"] == "Bearer test_api_key"


def test_build_params_helper():
    """Test the _build_params helper method."""
    service = STTContentAPIService()

    params = service._build_params("2024-01-01T00:00:00Z", 5)

    assert params == {"page": 5}
    # Verify since_iso parameter is accepted but not used in current implementation


def test_config_validation(service):
    """Test configuration validation in _test method."""

    # Test missing URL
    provider = {"config": {"api_key": "test"}}

    with pytest.raises(Exception):  # Should raise ParserError.parseMessageError
        service._test(provider)

    # Test missing API key
    provider = {"config": {"url": "https://example.com"}}

    with pytest.raises(Exception):  # Should raise ParserError.parseMessageError
        service._test(provider)


def test_fetch_data_error_handling(monkeypatch, service):
    """Test error handling in _fetch_data."""

    class MockErrorRequests:
        def get(self, url, params=None, headers=None, timeout=None):
            # Simulate HTTP error
            return FakeResponse({}, status_code=404)

    mock_requests = MockErrorRequests()

    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "Bearer TOKEN123",
        }
    }

    with pytest.raises(Exception):  # Should raise IngestApiError
        service._fetch_data(provider, "")


def test_update_with_parser_config(monkeypatch, service):
    """Test _update method with proper feed_parser configuration."""

    responses = [
        {
            "_items": [{"_id": "TEST", "headline": "Test item"}],
            "_links": {},
        }
    ]

    mock_requests = MockRequests(responses)

    import stt.io.feeding_services.stt_content_api as content_api_module

    monkeypatch.setattr(content_api_module, "requests", mock_requests)

    # Mock the parser to avoid full Superdesk infrastructure
    class MockParser:
        def parse(self, item, provider):
            return [{"parsed": True, "original_id": item.get("_id")}]

    def mock_get_feed_parser(provider, item=None):
        return MockParser()

    # Patch the get_feed_parser method
    monkeypatch.setattr(service, "get_feed_parser", mock_get_feed_parser)

    provider = {
        "config": {
            "url": "https://api.example.com/contentapi/items",
            "api_key": "Bearer TOKEN123",
        },
        "feed_parser": "content_api_json",
    }
    update = {}

    items = list(service._update(provider, update))

    assert len(items) == 1
    assert items[0]["parsed"] is True
    assert items[0]["original_id"] == "TEST"
