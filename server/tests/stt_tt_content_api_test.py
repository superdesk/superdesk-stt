# -*- coding: utf-8 -*-
import os
import unittest
import requests
from unittest.mock import patch
from flask import json

from stt.io.feeding_services.stt_tt_content_api import STTContentAPIService
from stt.io.feed_parsers.stt_tt_parse_content_api import ContentAPITTItemParser


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


class MockResponseWithJsonException:
    def __init__(self, json_data=None, status_code=200, json_exc=None):
        self._json_data = json_data
        self.status_code = status_code
        self._json_exc = json_exc

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json_data


class STTContentAPITestCase(unittest.TestCase):
    def setUp(self):
        self.service = STTContentAPIService()
        self.parser = ContentAPITTItemParser()

        # Load test fixture
        with open(fixture("api/stt_tt_content_api.json")) as _file:
            self.fixture_data = json.load(_file)

    def test_instance(self):
        """Test service instance creation and basic properties."""
        self.assertEqual("stt_tt_content_api", self.service.NAME)
        self.assertEqual("STT TT Content API", self.service.label)
        self.assertFalse(self.service.HTTP_AUTH)

        # Check required fields
        fields = {field["id"]: field for field in self.service.fields}
        self.assertIn("url", fields)
        self.assertIn("api_key", fields)
        self.assertTrue(fields["url"]["required"])
        self.assertTrue(fields["api_key"]["required"])

    def test_headers_helper(self):
        """Test the _headers helper method."""
        headers = self.service._headers("test_api_key")

        self.assertEqual("application/json", headers["Accept"])
        self.assertEqual("ApiKey test_api_key", headers["Authorization"])

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

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_single_page(self, mock_get):
        """Test _fetch_data with single page response using fixture data."""
        # Use first 2 items from fixture for testing
        test_items = self.fixture_data["hits"][:2]
        mock_response_data = {
            "hits": test_items,
        }

        mock_get.return_value = MockResponse(mock_response_data)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TEST_TOKEN",
            }
        }

        items = self.service._fetch_data(provider)

        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual("https://api.example.com/contentapi/items", call_args[0][0])
        self.assertEqual(
            "ApiKey Bearer TEST_TOKEN", call_args[1]["headers"]["Authorization"]
        )
        self.assertEqual("application/json", call_args[1]["headers"]["Accept"])
        self.assertEqual(300, call_args[1]["timeout"])

        # Verify items returned
        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])
        self.assertEqual(test_items[1]["uri"], items[1]["uri"])

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_hits_format(self, mock_get):
        """Test _fetch_data with hits response format."""
        # Test with hits field response format
        all_items = self.fixture_data["hits"][:2]

        mock_response_data = {"hits": all_items}
        mock_get.return_value = MockResponse(mock_response_data)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "test_token",  # Test without ApiKey prefix
            }
        }

        items = self.service._fetch_data(provider)

        # Should have made one request
        self.assertEqual(1, mock_get.call_count)

        # Check request
        call_args = mock_get.call_args
        self.assertEqual("ApiKey test_token", call_args[1]["headers"]["Authorization"])

        # Should return all items
        self.assertEqual(2, len(items))
        self.assertEqual(
            [item["uri"] for item in all_items], [item["uri"] for item in items]
        )

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_different_response_formats(self, mock_get):
        """Test _fetch_data with different API response formats."""
        test_items = self.fixture_data["hits"][:2]

        # Test with direct list response
        mock_response_data = test_items

        mock_get.return_value = MockResponse(mock_response_data)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        items = self.service._fetch_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_list_response(self, mock_get):
        """Test _fetch_data with direct list response."""
        test_items = self.fixture_data["hits"][:2]

        mock_get.return_value = MockResponse(test_items)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        items = self.service._fetch_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
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
        test_item = self.fixture_data["hits"][0]

        result = self.parser.parse(test_item, provider={"config": {}})

        # Parser should return a dict
        self.assertIsInstance(result, dict)

        parsed_item = result

        # Check required fields
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("guid", parsed_item)
        self.assertIn("versioncreated", parsed_item)

        # Check original data is preserved
        self.assertEqual(test_item["uri"], parsed_item["uri"])
        self.assertEqual(test_item["headline"], parsed_item["headline"])

        # Check GUID generation
        self.assertTrue(
            parsed_item["guid"].startswith("urn:newsml:stt.fi:stt_tt_content_api:")
        )

    def test_parser_content_expiry(self):
        """Test parser content expiry calculation."""
        test_item = {"_id": "expiry_test", "source": "STT"}

        provider = {"config": {"content_expiry": 24}}  # 24 hours

        result = self.parser.parse(test_item, provider=provider)
        parsed_item = result

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
        parsed_item = result

        # Should have all required defaults
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("guid", parsed_item)
        self.assertIn("versioncreated", parsed_item)
        self.assertEqual("", parsed_item["headline"])
        self.assertEqual("", parsed_item["body_html"])

    def test_parser_guid_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        test_item = self.fixture_data["hits"][0]

        result1 = self.parser.parse(test_item, provider={"config": {}})
        result2 = self.parser.parse(test_item, provider={"config": {}})

        self.assertEqual(result1["guid"], result2["guid"])

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_update_with_parser_integration(self, mock_get):
        """Test _update method with parser integration using fixture data."""
        test_items = self.fixture_data["hits"][:2]
        mock_response_data = {"hits": test_items}

        mock_get.return_value = MockResponse(mock_response_data)

        # The service already uses the parser directly, no need to mock parser discovery
        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            },
        }
        update = {}

        items = list(self.service._update(provider, update))

        # Should have processed all items
        self.assertEqual(2, len(items))

        # Check that items were parsed correctly
        for parsed_item in items:
            self.assertEqual("text", parsed_item["type"])
            self.assertEqual("usable", parsed_item["pubstatus"])
            self.assertIn("guid", parsed_item)

    def test_fixture_data_structure(self):
        """Validate the structure of the fixture data."""
        # Should have hits
        self.assertIn("hits", self.fixture_data)
        self.assertGreater(len(self.fixture_data["hits"]), 0)

        # Check first item structure
        first_item = self.fixture_data["hits"][0]
        self.assertIsInstance(first_item, dict)

        # Should have STT-specific fields
        expected_fields = ["uri", "source"]
        for field in expected_fields:
            if field in first_item:
                self.assertIsInstance(first_item[field], str)

        # Source should be TT-related
        if "source" in first_item:
            self.assertTrue(first_item["source"].startswith("TT"))

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_top_level_array(self, mock_get):
        test_items = [{"id": 1}, {"id": 2}, "not a dict", 123, {"id": 3}]
        mock_get.return_value = MockResponse(json_data=test_items, status_code=200)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }

        items = self.service._fetch_data(provider)

        self.assertEqual([{"id": 1}, {"id": 2}, {"id": 3}], items)

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertEqual(provider["config"]["url"], mock_get.call_args[0][0])
        self.assertEqual(300, kwargs.get("timeout"))
        # Ensure headers include ApiKey prefix and no params are sent
        self.assertIn("headers", kwargs)
        self.assertEqual("ApiKey MY_TOKEN", kwargs["headers"]["Authorization"])
        self.assertEqual("application/json", kwargs["headers"]["Accept"])
        self.assertNotIn("params", kwargs)

    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_dict_of_id_mapping(self, mock_get):
        hits_mapping = {
            "a": {"id": "A"},
            "b": {"id": "B"},
            "c": "not a dict",
        }
        mock_get.return_value = MockResponse(
            json_data={"hits": hits_mapping}, status_code=200
        )

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }

        items = self.service._fetch_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual({"A", "B"}, {item["id"] for item in items})

    @patch("superdesk.errors.IngestApiError.apiGeneralError")
    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_http_error_raises_ingest_api_error(
        self, mock_get, mock_api_error
    ):
        mock_get.return_value = MockResponse(json_data=None, status_code=500)
        mock_api_error.side_effect = lambda ex, provider: RuntimeError(str(ex))

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }

        with self.assertRaises(RuntimeError) as ctx:
            self.service._fetch_data(provider)

        self.assertIn("HTTP 500 from TT Content API", str(ctx.exception))
        mock_api_error.assert_called_once()
        args, kwargs = mock_api_error.call_args
        self.assertIsInstance(args[0], Exception)
        self.assertIn("HTTP 500", str(args[0]))
        self.assertEqual(provider, args[1])

    @patch("superdesk.errors.IngestApiError.apiGeneralError")
    @patch("stt.io.feeding_services.stt_tt_content_api.requests.get")
    def test_fetch_data_json_parse_error_raises_ingest_api_error(
        self, mock_get, mock_api_error
    ):
        mock_get.return_value = MockResponseWithJsonException(
            json_exc=ValueError("bad json"), status_code=200
        )
        mock_api_error.side_effect = lambda ex, provider: RuntimeError(str(ex))

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }

        with self.assertRaises(RuntimeError) as ctx:
            self.service._fetch_data(provider)

        self.assertIn("JSON parse error", str(ctx.exception))
        mock_api_error.assert_called_once()
        args, kwargs = mock_api_error.call_args
        self.assertIsInstance(args[0], Exception)
        self.assertIn("bad json", str(args[0]))
        self.assertEqual(provider, args[1])

    def test_update_flattens_parsed_items(self):
        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }
        items_to_fetch = [{"a": 1}, {"b": 2}]
        with patch.object(self.service, "_fetch_data", return_value=items_to_fetch):

            class DummyParser:
                def parse(self, item, provider):
                    if "a" in item:
                        return {"x": 1}
                    return {"z": 3}

            # Mock the ContentAPITTItemParser directly since it's used in _update
            with patch(
                "stt.io.feeding_services.stt_tt_content_api.ContentAPITTItemParser",
                return_value=DummyParser(),
            ):
                result = list(self.service._update(provider, update={}))

        self.assertEqual(2, len(result))
        self.assertEqual([{"x": 1}, {"z": 3}], result)

    @patch("superdesk.errors.ParserError.parseMessageError")
    def test_update_parser_exception_wrapped_in_parser_error(self, mock_parse_error):
        mock_parse_error.side_effect = lambda ex, provider, data=None: RuntimeError(
            "wrapped"
        )
        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }
        items_to_fetch = [{"ok": 1}, {"bad": 2}]
        with patch.object(self.service, "_fetch_data", return_value=items_to_fetch):

            class FailingParser:
                def parse(self, item, provider):
                    if "bad" in item:
                        raise ValueError("boom")
                    return {"ok_parsed": True}

            # Mock the ContentAPITTItemParser directly since it's used in _update
            with patch(
                "stt.io.feeding_services.stt_tt_content_api.ContentAPITTItemParser",
                return_value=FailingParser(),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    list(self.service._update(provider, update={}))

        self.assertEqual("wrapped", str(ctx.exception))
        mock_parse_error.assert_called_once()
        args, kwargs = mock_parse_error.call_args
        self.assertIsInstance(args[0], Exception)
        self.assertEqual(provider, args[1])
        self.assertEqual({"bad": 2}, kwargs.get("data"))


if __name__ == "__main__":
    unittest.main()
