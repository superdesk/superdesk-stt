# -*- coding: utf-8 -*-
from collections.abc import Callable
import json
import os
from datetime import datetime, timezone
from unittest.mock import patch
import re

from yarl import URL
import aiohttp

from superdesk.tests import TestCase
from superdesk.tests.http_mocks import mock_http, CallbackResult

from stt.io.feeding_services.stt_tt_content_api import STTTTContentAPIService
from stt.io.feed_parsers.stt_tt_parse_content_api import ContentAPITTItemParser


ITEMS_URL = "https://api.example.com/contentapi/items"
MATCH_ITEMS_URL = re.compile(rf"^{ITEMS_URL}(\?.*)?$")


def create_mock_callback(
    first_page_results: list[dict],
) -> Callable[[URL], CallbackResult]:
    def _mock_callback(url: URL, **kwargs) -> CallbackResult:
        # First call returns data, second call returns empty (simulates single page)
        if url.query.get("fr") == "0":
            return CallbackResult(status=200, payload={"hits": first_page_results})

        return CallbackResult(status=200, payload={"hits": []})

    return _mock_callback


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


class STTContentAPITestCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.service = STTTTContentAPIService()
        self.parser = ContentAPITTItemParser()

        # Load test fixture
        with open(fixture("api/stt_tt_content_api.json")) as _file:
            self.fixture_data = json.load(_file)

        self.http_mock = mock_http(self)

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

    async def test_config_validation(self):
        """Test configuration validation in _test method."""
        # Test missing URL
        provider = {"config": {"api_key": "test"}}

        with self.assertRaises(Exception):
            await self.service._test(provider)

        # Test missing API key
        provider = {"config": {"url": "https://example.com"}}

        with self.assertRaises(Exception):
            await self.service._test(provider)

    async def test_fetch_data_single_page(self):
        """Test _fetch_tt_data with single page response using fixture data."""
        # Use first 2 items from fixture for testing
        test_items = self.fixture_data["hits"][:2]
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(test_items), repeat=True
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "Bearer TEST_TOKEN",
            }
        }

        items = await self.service._fetch_tt_data(provider, {})

        # Verify pagination: expect 2 calls (first with data, second empty)
        call_types = list(self.http_mock.requests.keys())
        self.assertEqual(2, len(call_types))
        call = self.http_mock.requests[call_types[0]][0]

        # Check first call has pagination params
        _, first_call_url = call_types[0]
        headers = call.kwargs.get("headers", {})
        self.assertEqual(first_call_url.query["s"], "50")
        self.assertEqual(first_call_url.query["fr"], "0")
        self.assertEqual("ApiKey Bearer TEST_TOKEN", headers["Authorization"])
        self.assertEqual("application/json", headers["Accept"])
        self.assertEqual(60, call.kwargs.get("timeout").total)

        # Verify items returned
        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])
        self.assertEqual(test_items[1]["uri"], items[1]["uri"])

    async def test_fetch_data_hits_format(self):
        """Test _fetch_tt_data with hits response format."""
        # Test with hits field response format
        all_items = self.fixture_data["hits"][:2]
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(all_items), repeat=True
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "test_token",  # Test without ApiKey prefix
            }
        }

        items = await self.service._fetch_tt_data(provider, {})

        # Should have made two requests (pagination logic)
        call_types = list(self.http_mock.requests.keys())
        self.assertEqual(2, len(call_types))
        call = self.http_mock.requests[call_types[0]][0]
        headers = call.kwargs.get("headers", {})
        self.assertEqual("ApiKey test_token", headers["Authorization"])

        # Should return all items
        self.assertEqual(2, len(items))
        self.assertEqual(
            [item["uri"] for item in all_items],
            [item["uri"] for item in items],
        )

    async def test_fetch_data_different_response_formats(self):
        """Test _fetch_tt_data with different API response formats."""
        test_items = self.fixture_data["hits"][:2]
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(test_items), repeat=True
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "Bearer TOKEN123",
            }
        }

        items = await self.service._fetch_tt_data(provider, {})

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    async def test_fetch_data_adds_trs_with_last_updated(self):
        """When update contains last_updated, include trs in query."""
        self.http_mock.get(
            MATCH_ITEMS_URL,
            callback=create_mock_callback([TEST_TT_ITEMS[0]]),
            repeat=True,
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
            }
        }
        update = {"last_updated": "2025-09-24T10:00:00Z"}

        _ = await self.service._fetch_tt_data(provider, update)

        # First call URL should contain trs param derived from the last_update date
        call_types = list(self.http_mock.requests.keys())
        self.assertEqual(2, len(call_types))
        _, first_call_url = call_types[0]
        self.assertEqual(first_call_url.query["fr"], "0")
        self.assertEqual(first_call_url.query["trs"], "2025-09-24")

    async def test_fetch_data_uses_trs_fallback_since_minutes(self):
        """When no last_updated, use now - since_minutes as trs."""
        self.http_mock.get(
            MATCH_ITEMS_URL,
            callback=create_mock_callback([TEST_TT_ITEMS[0]]),
            repeat=True,
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
                "since_minutes": "120",
            }
        }
        update = {}

        # Freeze datetime.now in the target module
        with patch("stt.io.feeding_services.stt_tt_content_api.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(
                2025, 9, 25, 12, 0, 0, tzinfo=timezone.utc
            )
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            # timezone is used in code; pass through the real timezone
            mock_dt.timezone = timezone

            _ = await self.service._fetch_tt_data(provider, update)

        # Expected trs = 2025-09-25 (12:00 - 120 minutes truncated to date)
        call_types = list(self.http_mock.requests.keys())
        self.assertEqual(2, len(call_types))
        _, first_call_url = call_types[0]
        self.assertEqual(first_call_url.query["fr"], "0")
        self.assertEqual(first_call_url.query["trs"], "2025-09-25")

    async def test_timeout_configurable(self):
        """Provider timeout should override default."""

        self.http_mock.get(MATCH_ITEMS_URL, status=200, payload={"hits": []})
        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
                "timeout": "15",
            }
        }
        update = {}

        _ = await self.service._fetch_tt_data(provider, update)

        call_types = list(self.http_mock.requests.keys())
        call = self.http_mock.requests[call_types[0]][0]
        self.assertEqual(15, call.kwargs.get("timeout").total)

    async def test_trs_enforced_even_when_legacy_config_disables(self):
        """Legacy configs with use_trs=False should still yield trs in query."""
        self.http_mock.get(MATCH_ITEMS_URL, status=200, payload={"hits": []})
        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
                "use_trs": False,
            }
        }
        update = {"last_updated": "2025-09-24T10:00:00Z"}

        _ = await self.service._fetch_tt_data(provider, update)

        call_types = list(self.http_mock.requests.keys())
        _, first_call_url = call_types[0]
        self.assertEqual(first_call_url.query["fr"], "0")
        self.assertEqual(first_call_url.query["trs"], "2025-09-24")

    async def test_fetch_data_list_response(self):
        """Test _fetch_tt_data with direct list response."""
        test_items = self.fixture_data["hits"][:2]
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(test_items), repeat=True
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "Bearer TOKEN123",
            }
        }

        items = await self.service._fetch_tt_data(provider, {})

        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    async def test_fetch_data_error_handling(self):
        """Test error handling in _fetch_tt_data."""

        self.http_mock.get(MATCH_ITEMS_URL, status=404, payload={})
        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "Bearer TOKEN123",
            }
        }

        with self.assertRaises(Exception):
            await self.service._fetch_tt_data(provider, {})

    async def test_parser_with_fixture_data(self):
        """Test parser with real fixture data."""
        test_item = self.fixture_data["hits"][0]

        result = await self.parser.parse(test_item, provider={"config": {}})

        # Parser should return a list of dicts
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))

        parsed_item = result[0]

        # Check required fields
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("uri", parsed_item)
        self.assertIn("versioncreated", parsed_item)

        # Check original data is preserved
        self.assertEqual(test_item["uri"], parsed_item["uri"])
        self.assertEqual(test_item["headline"], parsed_item["headline"])

    async def test_parser_minimal_item(self):
        """Test parser with minimal required data."""
        minimal_item = {
            "uri": "http://tt.se/media/text/test-minimal",
            "source": "STT",
            "type": "text",
            "headline": "Test minimal headline",
        }

        result = await self.parser.parse(minimal_item, provider={"config": {}})
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))
        parsed_item = result[0]

        # Should have all required defaults
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("versioncreated", parsed_item)
        self.assertEqual("Test minimal headline", parsed_item["headline"])
        self.assertEqual("", parsed_item["body_html"])

    async def test_update_with_parser_integration(self):
        """Test _update method with parser integration using fixture data."""
        test_items = self.fixture_data["hits"][:2]
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(test_items), repeat=True
        )

        # Mock the parser since it's not registered in test environment
        with patch.object(self.service, "get_feed_parser", return_value=self.parser):
            provider = {
                "config": {
                    "url": ITEMS_URL,
                    "api_key": "Bearer TOKEN123",
                },
            }
            update = {}

            items = await self.service._update(provider, update)

            # Should have processed all items and return a single batch
            self.assertEqual(1, len(items))
            parsed_batch = items[0]
            self.assertEqual(2, len(parsed_batch))

            # Check that items were parsed correctly
            for parsed_item in parsed_batch:
                self.assertEqual("text", parsed_item["type"])
                self.assertEqual("usable", parsed_item["pubstatus"])

    async def test_fetch_data_top_level_array(self):
        test_items = TEST_TT_ITEMS
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(test_items), repeat=True
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
            }
        }

        items = await self.service._fetch_tt_data(provider, {})

        self.assertEqual(2, len(items))
        self.assertEqual(
            [
                "http://tt.se/media/text/250924-konjunkturlaget6uv-ae8053fa",
                "http://tt.se/media/text/250924-bookmarkpabo-4068424",
            ],
            [it["uri"] for it in items],
        )

        call_types = list(self.http_mock.requests.keys())
        self.assertEqual(2, len(call_types))

        _, second_call_url = call_types[1]
        second_call = self.http_mock.requests[call_types[1]][0]
        second_call_headers = second_call.kwargs.get("headers", {})

        # Second call should have pagination offset
        self.assertEqual(second_call_url.query["s"], "50")
        self.assertEqual(second_call_url.query["fr"], "50")

        self.assertEqual(60, second_call.kwargs.get("timeout").total)
        self.assertEqual("ApiKey MY_TOKEN", second_call_headers["Authorization"])
        self.assertEqual("application/json", second_call_headers["Accept"])

    async def test_fetch_data_dict_of_id_mapping(self):
        hits_mapping = {
            "x": TEST_TT_ITEMS[0],
            "y": TEST_TT_ITEMS[1],
            "z": "not a dict",
        }
        self.http_mock.get(
            MATCH_ITEMS_URL, callback=create_mock_callback(hits_mapping), repeat=True
        )

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
            }
        }

        items = await self.service._fetch_tt_data(provider, {})

        self.assertEqual(2, len(items))
        self.assertEqual(
            {
                "http://tt.se/media/text/250924-konjunkturlaget6uv-ae8053fa",
                "http://tt.se/media/text/250924-bookmarkpabo-4068424",
            },
            {item["uri"] for item in items},
        )

    @patch("superdesk.errors.IngestApiError.apiGeneralError")
    async def test_fetch_data_http_error_raises_ingest_api_error(self, mock_api_error):
        self.http_mock.get(MATCH_ITEMS_URL, status=500, repeat=True)
        mock_api_error.side_effect = lambda ex, provider: RuntimeError(str(ex))

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
            }
        }

        with self.assertRaises(aiohttp.client_exceptions.ClientResponseError):
            await self.service._fetch_tt_data(provider, {})

        # The error is raised directly, not wrapped by mock_api_error
        mock_api_error.assert_not_called()

    @patch("superdesk.errors.IngestApiError.apiGeneralError")
    async def test_fetch_data_json_parse_error_raises_ingest_api_error(
        self, mock_api_error
    ):
        self.http_mock.get(
            MATCH_ITEMS_URL,
            status=200,
            body="not-a-valid-json-string",
            content_type="application/json",
        )
        mock_api_error.side_effect = lambda ex, provider: RuntimeError(str(ex))

        provider = {
            "config": {
                "url": ITEMS_URL,
                "api_key": "MY_TOKEN",
            }
        }

        with self.assertRaises(RuntimeError) as ctx:
            await self.service._fetch_tt_data(provider, {})

        self.assertIn("JSON parse error", str(ctx.exception))
        mock_api_error.assert_called_once()
        args, kwargs = mock_api_error.call_args
        self.assertIsInstance(args[0], Exception)
        self.assertEqual(provider, args[1])

    async def test_update_returns_batch_of_parsed_items(self):
        provider = {
            "config": {
                "url": ITEMS_URL,
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
                result = await self.service._update(provider, update={})

        self.assertEqual(1, len(result))
        batch = result[0]
        self.assertEqual(2, len(batch))
        self.assertEqual([{"x": 1}, {"z": 3}], batch)

    @patch("superdesk.errors.ParserError.parseMessageError")
    async def test_update_parser_exception_wrapped_in_parser_error(
        self, mock_parse_error
    ):
        mock_parse_error.side_effect = lambda ex, provider, data=None: RuntimeError(
            "wrapped"
        )
        provider = {
            "config": {
                "url": ITEMS_URL,
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
                    await self.service._update(provider, update={})

        self.assertEqual("wrapped", str(ctx.exception))
        mock_parse_error.assert_called_once()
        args, kwargs = mock_parse_error.call_args
        self.assertIsInstance(args[0], Exception)
        self.assertEqual(provider, args[1])
        self.assertEqual({"bad": 2}, kwargs.get("data"))
