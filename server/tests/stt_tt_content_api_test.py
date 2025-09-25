# -*- coding: utf-8 -*-
import json
import os
import unittest
import requests
from unittest.mock import patch

from stt.io.feeding_services.stt_tt_content_api import STTTTContentAPIService
from stt.io.feed_parsers.stt_tt_parse_content_api import ContentAPITTItemParser

# Shared realistic TT items for tests that need concrete payloads
TEST_TT_ITEMS = [
    {
        "uri": "http://tt.se/media/text/250924-konjunkturlaget6uv-ae8053fa",
        "associations": {
            "a001": {
                "representationtype": "incomplete",
                "description_text": "Besökare på ett köpcentrum. Arkivbild. ",
                "mimetype": "image/jpeg",
                "renditions": {
                    "r01": {
                        "sizeinbytes": 434445,
                        "usage": "Preview",
                        "variant": "Normal",
                        "width": 1024,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-konjunkturlaget6uv-ae8053fa/a001_NormalPreview.jpg"
                        ),
                        "height": 683,
                    },
                    "r00": {
                        "sizeinbytes": 14486162,
                        "usage": "Hires",
                        "variant": "Normal",
                        "width": 5568,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-konjunkturlaget6uv-ae8053fa/a001_NormalHires.jpg"
                        ),
                        "height": 3712,
                    },
                    "r03": {
                        "sizeinbytes": 40566,
                        "usage": "Thumbnail",
                        "variant": "Normal",
                        "width": 256,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://thumbnail.tt.se/media/text/"
                            "250924-konjunkturlaget6uv-ae8053fa/a001_NormalThumbnail.jpg"
                        ),
                        "height": 171,
                    },
                    "r02": {
                        "sizeinbytes": 434445,
                        "usage": "Preview",
                        "variant": "Watermark",
                        "width": 1024,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-konjunkturlaget6uv-ae8053fa/a001_WatermarkPreview.jpg"
                        ),
                        "height": 683,
                    },
                },
                "type": "picture",
                "byline": "Amir Nabizadeh/TT",
                "uri": "http://tt.se/media/image/sdlg3pTraNl8TI",
            }
        },
        "altids": {
            "originaltransmissionreference": "ae8053fa-9100-460d-9589-ee2a75535877"
        },
        "webprio": 2,
        "body_text": "KI: Ekonomin lyfter nästa år… (truncated in tests)",
        "language": "sv",
        "source": "TT",
        "type": "text",
        "versioncreated": "2025-09-24T08:16:02Z",
        "headline": "KI: Ekonomin lyfter nästa år",
        "slug": "konjunkturläget-6-UV",
        "pubstatus": "usable",
    },
    {
        "uri": "http://tt.se/media/text/250924-bookmarkpabo-4068424",
        "associations": {
            "a001": {
                "representationtype": "complete",
                "description_text": "",
                "renditions": {
                    "r01": {
                        "unit": "PX",
                        "usage": "Hires",
                        "variant": "Normal",
                        "width": 8000,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-bookmarkpabo-4068424/a001_NormalHires.jpg"
                        ),
                        "height": 4500,
                    },
                    "r00": {
                        "unit": "PX",
                        "usage": "Thumbnail",
                        "variant": "Normal",
                        "width": 512,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://thumbnail.tt.se/media/text/"
                            "250924-bookmarkpabo-4068424/a001_NormalThumbnail.jpg"
                        ),
                        "height": 288,
                    },
                    "r03": {
                        "unit": "PX",
                        "usage": "Preview",
                        "variant": "Watermark",
                        "width": 1024,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-bookmarkpabo-4068424/a001_WatermarkPreview.jpg"
                        ),
                        "height": 576,
                    },
                    "r02": {
                        "unit": "PX",
                        "usage": "Preview",
                        "variant": "Cropped",
                        "width": 1024,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-bookmarkpabo-4068424/a001_CroppedPreview.jpg"
                        ),
                        "height": 1024,
                    },
                    "r05": {
                        "unit": "PX",
                        "usage": "Thumbnail",
                        "variant": "Cropped",
                        "width": 512,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://thumbnail.tt.se/media/text/"
                            "250924-bookmarkpabo-4068424/a001_CroppedThumbnail.jpg"
                        ),
                        "height": 512,
                    },
                    "r04": {
                        "unit": "PX",
                        "usage": "Preview",
                        "variant": "Normal",
                        "width": 1024,
                        "mimetype": "image/jpeg",
                        "href": (
                            "https://beta.tt.se/media/text/"
                            "250924-bookmarkpabo-4068424/a001_NormalPreview.jpg"
                        ),
                        "height": 576,
                    },
                },
                "type": "picture",
                "uri": "http://tt.se/media/image/68847ef9304c48267feaaac57dda0fa6",
            }
        },
        "language": "sv",
        "source": "ViaTT",
        "type": "text",
        "versioncreated": "2025-09-24T10:12:00+02:00",
        "headline": "Bookmark på Bokmässan 2025",
        "slug": "bookmarkpåbokmässan2025",
        "pubstatus": "usable",
    },
]


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
        self.headers = {"content-type": "application/json"}

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class STTContentAPITestCase(unittest.TestCase):
    def setUp(self):
        self.service = STTTTContentAPIService()
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

        # Check new pagination fields
        self.assertIn("page_size", fields)
        self.assertIn("max_pages", fields)
        self.assertFalse(fields["page_size"]["required"])
        self.assertFalse(fields["max_pages"]["required"])
        self.assertEqual("50", fields["page_size"]["default"])
        self.assertEqual("200", fields["max_pages"]["default"])

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

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_single_page(self, mock_get):
        """Test _fetch_tt_data with single page response using fixture data."""
        # Use first 2 items from fixture for testing
        test_items = self.fixture_data["hits"][:2]
        mock_response_data = {
            "hits": test_items,
        }

        # First call returns data, subsequent calls return empty
        # (simulates single page)
        mock_get.side_effect = [
            MockResponse(mock_response_data),  # First page with data
            MockResponse({"hits": []}),  # Second page empty (stops pagination)
        ]

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TEST_TOKEN",
            }
        }

        items = self.service._fetch_tt_data(provider)

        # Verify pagination: expect 2 calls (first with data, second empty)
        self.assertEqual(2, mock_get.call_count)

        # Check first call has pagination params
        first_call_args = mock_get.call_args_list[0]
        first_url = first_call_args[0][0]
        self.assertIn("s=50", first_url)  # page size
        self.assertIn("fr=0", first_url)  # offset
        self.assertEqual(
            "ApiKey Bearer TEST_TOKEN",
            first_call_args[1]["headers"]["Authorization"],
        )
        self.assertEqual("application/json", first_call_args[1]["headers"]["Accept"])
        self.assertEqual(300, first_call_args[1]["timeout"])

        # Verify items returned
        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])
        self.assertEqual(test_items[1]["uri"], items[1]["uri"])

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_hits_format(self, mock_get):
        """Test _fetch_tt_data with hits response format."""
        # Test with hits field response format
        all_items = self.fixture_data["hits"][:2]

        mock_response_data = {"hits": all_items}
        # First call returns data, second call returns empty (simulates single page)
        mock_get.side_effect = [
            MockResponse(mock_response_data),  # First page with data
            MockResponse({"hits": []}),  # Second page empty (stops pagination)
        ]

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "test_token",  # Test without ApiKey prefix
            }
        }

        items = self.service._fetch_tt_data(provider)

        # Should have made two requests (pagination logic)
        self.assertEqual(2, mock_get.call_count)

        # Check request
        call_args = mock_get.call_args
        self.assertEqual("ApiKey test_token", call_args[1]["headers"]["Authorization"])

        # Should return all items
        self.assertEqual(2, len(items))
        self.assertEqual(
            [item["uri"] for item in all_items],
            [item["uri"] for item in items],
        )

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_different_response_formats(self, mock_get):
        """Test _fetch_tt_data with different API response formats."""
        test_items = self.fixture_data["hits"][:2]

        # Test with direct list response
        mock_response_data = test_items

        # Simulate pagination: first call returns data, second returns empty
        mock_get.side_effect = [
            MockResponse(mock_response_data),  # First page with data
            MockResponse([]),  # Second page empty (stops pagination)
        ]

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        items = self.service._fetch_tt_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_list_response(self, mock_get):
        """Test _fetch_tt_data with direct list response."""
        test_items = self.fixture_data["hits"][:2]

        # Simulate pagination: first call returns data, second returns empty
        mock_get.side_effect = [
            MockResponse(test_items),  # First page with data
            MockResponse([]),  # Second page empty (stops pagination)
        ]

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        items = self.service._fetch_tt_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_error_handling(self, mock_get):
        """Test error handling in _fetch_tt_data."""
        mock_get.return_value = MockResponse({}, status_code=404)

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "Bearer TOKEN123",
            }
        }

        with self.assertRaises(Exception):
            self.service._fetch_tt_data(provider)

    def test_parser_with_fixture_data(self):
        """Test parser with real fixture data."""
        test_item = self.fixture_data["hits"][0]

        result = self.parser.parse(test_item, provider={"config": {}})

        # Parser should return a list of dicts
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
        self.assertTrue(
            parsed_item["guid"].startswith("urn:newsml:stt.fi:stt_tt_content_api:")
        )

    def test_parser_minimal_item(self):
        """Test parser with minimal required data."""
        minimal_item = {
            "uri": "http://tt.se/media/text/test-minimal",
            "source": "STT",
            "type": "text",
            "headline": "Test minimal headline",
        }

        result = self.parser.parse(minimal_item, provider={"config": {}})
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))
        parsed_item = result[0]

        # Should have all required defaults
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("guid", parsed_item)
        self.assertIn("versioncreated", parsed_item)
        self.assertEqual("Test minimal headline", parsed_item["headline"])
        self.assertEqual("", parsed_item["body_html"])

    def test_parser_guid_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        test_item = self.fixture_data["hits"][0]

        result1 = self.parser.parse(test_item, provider={"config": {}})
        result2 = self.parser.parse(test_item, provider={"config": {}})

        self.assertIsInstance(result1, list)
        self.assertIsInstance(result2, list)
        self.assertEqual(1, len(result1))
        self.assertEqual(1, len(result2))
        self.assertEqual(result1[0]["guid"], result2[0]["guid"])

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_update_with_parser_integration(self, mock_get):
        """Test _update method with parser integration using fixture data."""
        test_items = self.fixture_data["hits"][:2]
        mock_response_data = {"hits": test_items}

        # Simulate pagination: first call returns data, second returns empty
        mock_get.side_effect = [
            MockResponse(mock_response_data),  # First page with data
            MockResponse({"hits": []}),  # Second page empty (stops pagination)
        ]

        # Mock the parser since it's not registered in test environment
        with patch.object(self.service, "get_feed_parser", return_value=self.parser):
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

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_top_level_array(self, mock_get):
        test_items = TEST_TT_ITEMS
        # Simulate pagination: first call returns data, second returns empty
        mock_get.side_effect = [
            MockResponse(json_data=test_items, status_code=200),  # First page with data
            MockResponse(
                json_data=[], status_code=200
            ),  # Second page empty (stops pagination)
        ]

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }

        items = self.service._fetch_tt_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual(
            [
                "http://tt.se/media/text/250924-konjunkturlaget6uv-ae8053fa",
                "http://tt.se/media/text/250924-bookmarkpabo-4068424",
            ],
            [it["uri"] for it in items],
        )

        self.assertEqual(2, mock_get.call_count)

        # Check the second call (which is what call_args refers to)
        second_call_args = mock_get.call_args_list[1]
        second_url = second_call_args[0][0]

        # Second call should have pagination offset
        self.assertIn(provider["config"]["url"], second_url)
        self.assertIn("s=50", second_url)  # page_size
        self.assertIn("fr=50", second_url)  # offset for second page

        # Check headers on second call
        self.assertEqual(300, second_call_args[1].get("timeout"))
        self.assertIn("headers", second_call_args[1])
        self.assertEqual(
            "ApiKey MY_TOKEN", second_call_args[1]["headers"]["Authorization"]
        )
        self.assertEqual("application/json", second_call_args[1]["headers"]["Accept"])

    @patch.object(STTTTContentAPIService, "_get_with_retry")
    def test_fetch_data_dict_of_id_mapping(self, mock_get):
        hits_mapping = {
            "x": TEST_TT_ITEMS[0],
            "y": TEST_TT_ITEMS[1],
            "z": "not a dict",
        }
        # Simulate pagination: first call returns data, second returns empty
        mock_get.side_effect = [
            MockResponse(
                json_data={"hits": hits_mapping}, status_code=200
            ),  # First page with data
            MockResponse(
                json_data={"hits": {}}, status_code=200
            ),  # Second page empty (stops pagination)
        ]

        provider = {
            "config": {
                "url": "https://api.example.com/contentapi/items",
                "api_key": "MY_TOKEN",
            }
        }

        items = self.service._fetch_tt_data(provider)

        self.assertEqual(2, len(items))
        self.assertEqual(
            {
                "http://tt.se/media/text/250924-konjunkturlaget6uv-ae8053fa",
                "http://tt.se/media/text/250924-bookmarkpabo-4068424",
            },
            {item["uri"] for item in items},
        )

    @patch("superdesk.errors.IngestApiError.apiGeneralError")
    @patch.object(STTTTContentAPIService, "_get_with_retry")
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

        with self.assertRaises(requests.exceptions.HTTPError):
            self.service._fetch_tt_data(provider)

        # The error is raised directly, not wrapped by mock_api_error
        mock_api_error.assert_not_called()

    @patch("superdesk.errors.IngestApiError.apiGeneralError")
    @patch.object(STTTTContentAPIService, "_get_with_retry")
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
            self.service._fetch_tt_data(provider)

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
        with patch.object(self.service, "_fetch_tt_data", return_value=items_to_fetch):

            class DummyParser:
                def parse(self, item, provider):
                    if "a" in item:
                        return [{"x": 1}]  # Parser now returns list
                    return [{"z": 3}]  # Parser now returns list

            # Mock the get_feed_parser method since _update now uses it
            with patch.object(
                self.service, "get_feed_parser", return_value=DummyParser()
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
        with patch.object(self.service, "_fetch_tt_data", return_value=items_to_fetch):

            class FailingParser:
                def parse(self, item, provider):
                    if "bad" in item:
                        raise ValueError("boom")
                    return [{"ok_parsed": True}]  # Parser now returns list

            # Mock the get_feed_parser method since _update now uses it
            with patch.object(
                self.service, "get_feed_parser", return_value=FailingParser()
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
