import os
from unittest.mock import patch
from flask import json

import responses
from responses import matchers

from tests import TestCase
from stt.io.feeding_services.stt_content_api import STTContentAPIService
from stt.io.feed_parsers.stt_parse_content_api import ContentAPIItemParser


def fixture(filename):
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


class STTContentAPITestCase(TestCase):
    fixture = "api/stt_content_api.json"
    parser_class = ContentAPIItemParser

    async def parse_source_content(self):
        """Override to handle JSON files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture_path = os.path.join(dirname, "fixtures", self.fixture)
        with open(fixture_path, "r", encoding="utf-8") as _file:
            self.fixture_data = json.load(_file)
        # Parse the first item from the fixture for testing
        if self.fixture_data.get("_items"):
            test_item = self.fixture_data["_items"][0]
            self.parser = self.parser_class()
            parsed = await self.parser.parse(test_item, provider={"config": {}})
            self.item = parsed[0]
        else:
            self.item = {}

    def setUp(self):
        super().setUp()
        self.service = STTContentAPIService()
        self.parser = ContentAPIItemParser()

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

    @responses.activate
    def test_fetch_data_single_page(self):
        """Test _fetch_data with single page response using fixture data."""
        # Use first 2 items from fixture for testing
        test_items = self.fixture_data["_items"][:2]
        mock_response_data = {
            "_items": test_items,
            "_links": {},  # No next link
            "_meta": {"total": 2},
        }
        url = "https://api.example.com/contentapi/items"
        responses.add(
            responses.GET,
            url,
            json=mock_response_data,
            status=200,
            match=[matchers.query_param_matcher({"page": "1"})],
        )
        provider = {
            "config": {
                "url": url,
                "api_key": "Bearer TEST_TOKEN",
            }
        }
        items = self.service._fetch_data(provider, "2024-01-01T00:00:00Z")
        # Verify a single request was made
        self.assertEqual(1, len(responses.calls))
        # Verify headers
        req_headers = responses.calls[0].request.headers
        self.assertEqual("Bearer TEST_TOKEN", req_headers.get("Authorization"))
        self.assertEqual("application/json", req_headers.get("Accept"))
        # Verify items returned
        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])
        self.assertEqual(test_items[1]["uri"], items[1]["uri"])

    @responses.activate
    def test_fetch_data_pagination(self):
        """Test _fetch_data with multiple pages using fixture data."""
        # Split fixture items across two pages
        all_items = self.fixture_data["_items"][:4]
        page1_items = all_items[:2]
        page2_items = all_items[2:4]
        base_url = "https://api.example.com/contentapi/items"
        responses.add(
            responses.GET,
            base_url,
            json={
                "_items": page1_items,
                "_links": {"next": {"href": "/contentapi/items?page=2"}},
                "_meta": {"total": 4},
            },
            status=200,
            match=[matchers.query_param_matcher({"page": "1"})],
        )
        responses.add(
            responses.GET,
            base_url,
            json={
                "_items": page2_items,
                "_links": {},
                "_meta": {"total": 4},
            },
            status=200,
            match=[matchers.query_param_matcher({"page": "2"})],
        )
        provider = {
            "config": {
                "url": base_url,
                "api_key": "test_token",  # Test without Bearer prefix
            }
        }
        items = self.service._fetch_data(provider, "")
        self.assertEqual(2, len(responses.calls))
        # Check Authorization header on first call
        self.assertEqual(
            "Bearer test_token", responses.calls[0].request.headers.get("Authorization")
        )
        # Should return all items
        self.assertEqual(4, len(items))
        self.assertEqual(
            [item["uri"] for item in all_items], [item["uri"] for item in items]
        )

    @responses.activate
    def test_fetch_data_different_response_formats(self):
        """Test _fetch_data handles various API response formats: _items, items, results, docs, direct array, and fallback."""
        test_items = self.fixture_data["_items"][:2]

        # Test different response formats
        formats = [
            # Format 1: items key (simple REST style)
            {"items": test_items, "_links": {}},
            # Format 2: results key (search API style)
            {"results": test_items, "pagination": {"total": 2}},
            # Format 3: docs key (document store style)
            {"docs": test_items, "found": 2, "maxScore": 1.0},
            # Format 4: direct array (no wrapper)
            test_items,
        ]

        for i, response_format in enumerate(formats):
            with self.subTest(format_index=i):
                responses.reset()
                base_url = "https://api.example.com/contentapi/items"
                responses.add(
                    responses.GET,
                    base_url,
                    json=response_format,
                    status=200,
                    match=[matchers.query_param_matcher({"page": "1"})],
                )
                provider = {
                    "config": {
                        "url": base_url,
                        "api_key": "Bearer test_token",
                    }
                }
                items = self.service._fetch_data(provider, "")
                self.assertEqual(1, len(responses.calls))
                self.assertEqual(2, len(items))
                self.assertEqual(test_items[0]["uri"], items[0]["uri"])
                self.assertEqual(test_items[1]["uri"], items[1]["uri"])

        # Test fallback format (extracts all dict values from object)
        responses.reset()
        fallback_response = {
            "item1": test_items[0],
            "item2": test_items[1],
            "metadata": {"source": "test", "count": 2},
        }
        base_url = "https://api.example.com/contentapi/items"
        responses.add(
            responses.GET,
            base_url,
            json=fallback_response,
            status=200,
            match=[responses.matchers.query_param_matcher({"page": "1"})],
        )
        provider = {
            "config": {
                "url": base_url,
                "api_key": "Bearer test_token",
            }
        }
        items = self.service._fetch_data(provider, "")
        self.assertEqual(1, len(responses.calls))
        # Should extract ALL dict values (item1, item2, metadata)
        self.assertEqual(3, len(items))
        # Verify test items are included
        item_uris = {item.get("uri") for item in items if "uri" in item}
        expected_uris = {test_items[0]["uri"], test_items[1]["uri"]}
        self.assertEqual(expected_uris, item_uris)

    @responses.activate
    def test_fetch_data_list_response(self):
        """Test _fetch_data with direct list response."""
        test_items = self.fixture_data["_items"][:2]
        url = "https://api.example.com/contentapi/items"
        responses.add(
            responses.GET,
            url,
            json=test_items,
            status=200,
            match=[matchers.query_param_matcher({"page": "1"})],
        )
        provider = {
            "config": {
                "url": url,
                "api_key": "Bearer TOKEN123",
            }
        }
        items = self.service._fetch_data(provider, "")
        self.assertEqual(2, len(items))
        self.assertEqual(test_items[0]["uri"], items[0]["uri"])

    @responses.activate
    def test_fetch_data_error_handling(self):
        """Test error handling in _fetch_data."""
        url = "https://api.example.com/contentapi/items"
        responses.add(
            responses.GET,
            url,
            json={},
            status=404,
            match=[matchers.query_param_matcher({"page": "1"})],
        )
        provider = {
            "config": {
                "url": url,
                "api_key": "Bearer TOKEN123",
            }
        }
        with self.assertRaises(Exception):
            self.service._fetch_data(provider, "")

    async def test_parser_with_fixture_data(self):
        """Test parser with real fixture data."""
        test_item = self.fixture_data["_items"][0]

        result = await self.parser.parse(test_item, provider={"config": {}})

        # Parser should return a list
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))

        parsed_item = result[0]

        # Check required fields
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])

        # Check specific values
        self.assertEqual(
            "https://stt-uat-api.superdesk.pro/contentapi/items/urn%3Anewsml%3Astt.fi%3A%3A107136785",
            parsed_item["uri"],
        )

        from dateutil.parser import isoparse

        expected_versioncreated = isoparse("2025-08-12T12:19:53+0000")
        self.assertEqual(expected_versioncreated, parsed_item["versioncreated"])

        # Check original data is preserved
        self.assertEqual(test_item["uri"], parsed_item["uri"])
        self.assertEqual(test_item["headline"], parsed_item["headline"])

        # Check GUID generation format
        self.assertTrue(parsed_item["guid"].startswith("urn:newsml:stt.fi:contentapi:"))

    async def test_parser_content_expiry(self):
        """Test parser ignores content expiry configuration."""
        test_item = {"_id": "expiry_test", "source": "STT", "headline": "Test headline"}

        provider = {"config": {"content_expiry": 24}}  # 24 hours

        result = await self.parser.parse(test_item, provider=provider)
        parsed_item = result[0]

        # Should not have expiry set (functionality removed)
        self.assertIsNone(parsed_item.get("expiry"))

    async def test_parser_minimal_item(self):
        """Test parser with minimal required data - should be filtered out."""
        minimal_item = {"source": "STT"}

        result = await self.parser.parse(minimal_item, provider={"config": {}})

        # Should return empty list since item has no meaningful content
        self.assertIsInstance(result, list)
        self.assertEqual(0, len(result))

    async def test_parser_item_with_headline_only(self):
        """Test parser with item that has headline but no body - should be kept."""
        item_with_headline = {"source": "STT", "headline": "Test headline"}

        result = await self.parser.parse(item_with_headline, provider={"config": {}})

        # Should return one item since it has meaningful content
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))

        parsed_item = result[0]
        self.assertEqual("Test headline", parsed_item["headline"])
        self.assertEqual("", parsed_item["body_html"])

    async def test_parser_item_with_body_only(self):
        """Test parser with item that has body but no headline - should be kept."""
        item_with_body = {"source": "STT", "body_html": "<p>Test content</p>"}

        result = await self.parser.parse(item_with_body, provider={"config": {}})

        # Should return one item since it has meaningful content
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))

        parsed_item = result[0]
        self.assertEqual("", parsed_item["headline"])
        self.assertEqual("<p>Test content</p>", parsed_item["body_html"])

    async def test_parser_guid_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        test_item = self.fixture_data["_items"][0]

        result1 = await self.parser.parse(test_item, provider={"config": {}})
        result2 = await self.parser.parse(test_item, provider={"config": {}})

        self.assertEqual(result1[0]["uri"], result2[0]["uri"])

    async def test_parser_list_input(self):
        """Test parser with list input."""
        test_items = self.fixture_data["_items"][:3]

        result = await self.parser.parse(test_items, provider={"config": {}})

        self.assertEqual(3, len(result))
        for i, parsed_item in enumerate(result):
            self.assertEqual("text", parsed_item["type"])
            self.assertEqual("usable", parsed_item["pubstatus"])
            self.assertEqual(test_items[i]["uri"], parsed_item["uri"])

    @responses.activate
    async def test_update_with_parser_integration(self):
        """Test _update method with parser integration using fixture data."""
        test_items = self.fixture_data["_items"][:2]
        mock_response_data = {"_items": test_items, "_links": {}}
        url = "https://api.example.com/contentapi/items"
        responses.add(
            responses.GET,
            url,
            json=mock_response_data,
            status=200,
            match=[matchers.query_param_matcher({"page": "1"})],
        )

        # Mock the parser to avoid full Superdesk infrastructure requirements
        def mock_get_feed_parser(provider, item=None):
            return self.parser

        # Patch the get_feed_parser method
        with patch.object(
            self.service, "get_feed_parser", side_effect=mock_get_feed_parser
        ):
            provider = {
                "config": {
                    "url": url,
                    "api_key": "Bearer TOKEN123",
                },
                "feed_parser": "content_api_json",
            }
            update = {}
            items = list(await self.service._update(provider, update))
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

    def test_headline_keywords(self):
        """Test that the parsed item headline contains expected keywords."""
        self.assertEqual(
            "Yle: Pirkkalan koulupuukotuksesta epäilty 16-vuotias mielentilatutkimukseen",
            self.item["headline"],
        )

    def test_body_html_contains_keywords(self):
        """Test that body HTML contains expected keywords."""
        html = self.item.get("body_html", "")
        assert "Pirkkalan koulupuukotuksesta" in html
        assert "16-vuotias poika" in html
        assert "mielentilatutkimukseen" in html

    def test_metadata_subjects(self):
        """Test that subject metadata is properly parsed."""
        # Check that subject data is preserved
        if "subject" in self.fixture_data["_items"][0]:
            self.assertIn("subject", self.item)
            self.assertEqual(
                len(self.fixture_data["_items"][0]["subject"]),
                len(self.item["subject"]),
            )
