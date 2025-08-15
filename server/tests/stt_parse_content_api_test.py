# -*- coding: utf-8 -*-
import os
import unittest
import requests
from unittest.mock import patch
from flask import json

from stt.io.feeding_services.stt_content_api import STTContentAPIService
from stt.io.feed_parsers.stt_parse_content_api import ContentAPIItemParser


def fixture(filename):
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(json_data) if json_data else ""

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class STTContentAPITestCase(unittest.TestCase):
    def setUp(self):
        self.service = STTContentAPIService()
        self.parser = ContentAPIItemParser()

        # Load test fixture
        with open(fixture("api/stt_content_api.json")) as _file:
            self.fixture_data = json.load(_file)

    def test_instance(self):
        """Test service instance creation and basic properties."""
        self.assertEqual("stt_content_api", self.service.NAME)
        self.assertEqual("STT Content API", self.service.label)
        self.assertFalse(self.service.HTTP_AUTH)

        # Check required fields
        fields = {field["id"]: field for field in self.service.fields}
        self.assertIn("url", fields)
        self.assertIn("api_key", fields)
        self.assertTrue(fields["url"]["required"])
        self.assertTrue(fields["api_key"]["required"])

    def test_bearer_token_helper(self):
        """Test the _bearer helper method."""
        # Test with raw token
        self.assertEqual("Bearer raw_token", self.service._bearer("raw_token"))

        # Test with Bearer prefix already
        self.assertEqual(
            "Bearer existing_token", self.service._bearer("Bearer existing_token")
        )

    def test_headers_helper(self):
        """Test the _headers helper method."""
        headers = self.service._headers("test_api_key")

        self.assertEqual("application/json", headers["Accept"])
        self.assertEqual("Bearer test_api_key", headers["Authorization"])

    def test_build_params_helper(self):
        """Test the _build_params helper method."""
        params = self.service._build_params("2024-01-01T00:00:00Z", 5)

        self.assertEqual({"page": 5}, params)

    def test_config_validation(self):
        """Test configuration validation in _test method."""
        # Test missing URL
        provider = {"config": {"api_key": "test"}}

        with self.assertRaises(Exception):
            self.service._test(provider)

        # Test missing API key
        provider = {"config": {"url": "https://example.com"}}

        with self.assertRaises(Exception):
            self.service._test(provider)

    @patch("stt.io.feeding_services.stt_content_api.requests.get")
    def test_fetch_data_single_page(self, mock_get):
        """Test _fetch_data with single page response using fixture data."""
        # Use first 2 items from fixture for testing
        test_items = self.fixture_data["_items"][:2]
        mock_response_data = {
            "_items": test_items,
            "_links": {},  # No next link
            "_meta": {"total": 2},
        }

        mock_get.return_value = MockResponse(mock_response_data)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TEST_TOKEN",
            }
        }

        items = self.service._fetch_data(provider, "2024-01-01T00:00:00Z")

        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual("https://api.example.com/contentapi/items", call_args[0][0])
        self.assertEqual(1, call_args[1]["params"]["page"])
        self.assertEqual("Bearer TEST_TOKEN", call_args[1]["headers"]["Authorization"])
        self.assertEqual("application/json", call_args[1]["headers"]["Accept"])
        self.assertEqual(30, call_args[1]["timeout"])

        # Verify items returned
        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])
        self.assertEqual(test_items[1]["uri"], items[1]["uri"])

    @patch("stt.io.feeding_services.stt_content_api.requests.get")
    def test_fetch_data_pagination(self, mock_get):
        """Test _fetch_data with multiple pages using fixture data."""
        # Split fixture items across two pages
        all_items = self.fixture_data["_items"][:4]
        page1_items = all_items[:2]
        page2_items = all_items[2:4]

        def mock_response(url, params=None, headers=None, timeout=None):
            page = params.get("page", 1)
            if page == 1:
                return MockResponse(
                    {
                        "_items": page1_items,
                        "_links": {"next": {"href": "/contentapi/items?page=2"}},
                        "_meta": {"total": 4},
                    }
                )
            elif page == 2:
                return MockResponse(
                    {
                        "_items": page2_items,
                        "_links": {},  # No next link
                        "_meta": {"total": 4},
                    }
                )
            else:
                return MockResponse({"_items": [], "_links": {}})

        mock_get.side_effect = mock_response

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "test_token",  # Test without Bearer prefix
            }
        }

        items = self.service._fetch_data(provider, "")

        # Should have made two requests
        self.assertEqual(2, mock_get.call_count)

        # Check first request
        first_call = mock_get.call_args_list[0]
        self.assertEqual(1, first_call[1]["params"]["page"])
        self.assertEqual("Bearer test_token", first_call[1]["headers"]["Authorization"])

        # Check second request
        second_call = mock_get.call_args_list[1]
        self.assertEqual(2, second_call[1]["params"]["page"])

        # Should return all items
        self.assertEqual(4, len(items))
        self.assertEqual(
            [item["uri"] for item in all_items], [item["uri"] for item in items]
        )

    @patch("stt.io.feeding_services.stt_content_api.requests.get")
    def test_fetch_data_different_response_formats(self, mock_get):
        """Test _fetch_data with different API response formats."""
        test_items = self.fixture_data["_items"][:2]

        # Test with 'items' field instead of '_items'
        mock_response_data = {"items": test_items, "_links": {}}

        mock_get.return_value = MockResponse(mock_response_data)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        items = self.service._fetch_data(provider, "")

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @patch("stt.io.feeding_services.stt_content_api.requests.get")
    def test_fetch_data_list_response(self, mock_get):
        """Test _fetch_data with direct list response."""
        test_items = self.fixture_data["_items"][:2]

        mock_get.return_value = MockResponse(test_items)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        items = self.service._fetch_data(provider, "")

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @patch("stt.io.feeding_services.stt_content_api.requests.get")
    def test_fetch_data_error_handling(self, mock_get):
        """Test error handling in _fetch_data."""
        mock_get.return_value = MockResponse({}, status_code=404)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        with self.assertRaises(Exception):
            self.service._fetch_data(provider, "")

    def test_parser_with_fixture_data(self):
        """Test parser with real fixture data."""
        test_item = self.fixture_data["_items"][0]

        result = self.parser.parse(test_item, provider={"config": {}})

        # Parser should return a list
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))

        parsed_item = result[0]

        # Check required fields
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("guid", parsed_item)
        self.assertIn("versioncreated", parsed_item)

        # Check original data is preserved
        self.assertEqual(test_item["uri"], parsed_item["uri"])
        self.assertEqual(test_item["headline"], parsed_item["headline"])

        # Check GUID generation
        self.assertTrue(parsed_item["guid"].startswith("urn:newsml:stt.fi:contentapi:"))

    def test_parser_content_expiry(self):
        """Test parser content expiry calculation."""
        test_item = {"_id": "expiry_test", "source": "STT"}

        provider = {"config": {"content_expiry": 24}}  # 24 hours

        result = self.parser.parse(test_item, provider=provider)
        parsed_item = result[0]

        self.assertIsNotNone(parsed_item.get("expiry"))

        # Verify expiry is set to approximately 24 hours from versioncreated
        from datetime import timedelta

        expected_expiry = parsed_item["versioncreated"] + timedelta(hours=24)
        time_diff = abs((parsed_item["expiry"] - expected_expiry).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute tolerance

    def test_parser_minimal_item(self):
        """Test parser with minimal required data."""
        minimal_item = {"source": "STT"}

        result = self.parser.parse(minimal_item, provider={"config": {}})
        parsed_item = result[0]

        # Should have all required defaults
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("guid", parsed_item)
        self.assertIn("versioncreated", parsed_item)
        self.assertEqual("", parsed_item["headline"])
        self.assertEqual("", parsed_item["body_html"])

    def test_parser_guid_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        test_item = self.fixture_data["_items"][0]

        result1 = self.parser.parse(test_item, provider={"config": {}})
        result2 = self.parser.parse(test_item, provider={"config": {}})

        self.assertEqual(result1[0]["guid"], result2[0]["guid"])

    def test_parser_list_input(self):
        """Test parser with list input."""
        test_items = self.fixture_data["_items"][:3]

        result = self.parser.parse(test_items, provider={"config": {}})

        self.assertEqual(3, len(result))
        for i, parsed_item in enumerate(result):
            self.assertEqual("text", parsed_item["type"])
            self.assertEqual("usable", parsed_item["pubstatus"])
            self.assertEqual(test_items[i]["uri"], parsed_item["uri"])

    @patch("stt.io.feeding_services.stt_content_api.requests.get")
    def test_update_with_parser_integration(self, mock_get):
        """Test _update method with parser integration using fixture data."""
        test_items = self.fixture_data["_items"][:2]
        mock_response_data = {"_items": test_items, "_links": {}}

        mock_get.return_value = MockResponse(mock_response_data)

        # Mock the parser to avoid full Superdesk infrastructure requirements
        def mock_get_feed_parser(provider, item=None):
            return self.parser

        # Patch the get_feed_parser method
        with patch.object(
            self.service, "get_feed_parser", side_effect=mock_get_feed_parser
        ):
            provider = {
                "config": {
                    "url": "https://api.example.com/contentapi/items",
                    "api_key": "Bearer TOKEN123",
                },
                "feed_parser": "content_api_json",
            }
            update = {}

            items = list(self.service._update(provider, update))

            # Should have processed all items
            self.assertEqual(2, len(items))

            # Check that items were parsed correctly
            for i, item in enumerate(items):
                self.assertEqual("text", item["type"])
                self.assertEqual("usable", item["pubstatus"])
                self.assertEqual(test_items[i]["uri"], item["uri"])

    def test_fixture_data_structure(self):
        """Validate the structure of the fixture data."""
        # Should have _items
        self.assertIn("_items", self.fixture_data)
        self.assertGreater(len(self.fixture_data["_items"]), 0)

        # Check first item structure
        first_item = self.fixture_data["_items"][0]
        self.assertIsInstance(first_item, dict)

        # Should have STT-specific fields
        expected_fields = ["uri", "source"]
        for field in expected_fields:
            if field in first_item:
                self.assertIsInstance(first_item[field], str)

        # Source should be STT-related
        if "source" in first_item:
            self.assertTrue(first_item["source"].startswith("STT"))


if __name__ == "__main__":
    unittest.main()
