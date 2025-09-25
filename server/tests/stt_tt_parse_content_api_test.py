# -*- coding: utf-8 -*-
import json
import os
import unittest

from stt.io.feed_parsers.stt_tt_parse_content_api import ContentAPITTItemParser


def fixture(filename):
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


class ContentAPITTItemParserTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = ContentAPITTItemParser()

        # Load test fixture
        with open(fixture("api/stt_tt_content_api.json")) as _file:
            self.fixture_data = json.load(_file)

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

        self.assertTrue(
            parsed_item["guid"].startswith("urn:newsml:stt.fi:stt_tt_content_api:")
        )

    def test_parser_content_expiry(self):
        """Test parser with content expiry config (expiry handled by ingest system)."""
        test_item = {
            "uri": "http://tt.se/media/text/test-expiry",
            "source": "STT",
            "type": "text",
            "headline": "Test headline",
            "body_text": "Test content",
            "versioncreated": "2025-09-24T10:00:00Z",
        }

        provider = {"config": {"content_expiry": 24}}  # 24 hours

        result = self.parser.parse(test_item, provider=provider)

        # Parser should return a list
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))
        parsed_item = result[0]

        # Check that expiry is not set by parser (managed by ingest system)
        self.assertNotIn("expiry", parsed_item)

        # Check that the required fields are present
        self.assertEqual("text", parsed_item["type"])
        self.assertEqual("usable", parsed_item["pubstatus"])
        self.assertIn("guid", parsed_item)
        self.assertIn("versioncreated", parsed_item)

    def test_parser_minimal_item(self):
        """Test parser with minimal required data."""
        minimal_item = {
            "uri": "http://tt.se/media/text/test-minimal",
            "source": "STT",
            "type": "text",
            "headline": "Test minimal headline",
            "body_text": "Test content",
        }

        result = self.parser.parse(minimal_item, provider={"config": {}})

        # Parser should return a list
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

        # Parser should return lists
        self.assertIsInstance(result1, list)
        self.assertIsInstance(result2, list)
        self.assertEqual(1, len(result1))
        self.assertEqual(1, len(result2))

        self.assertEqual(result1[0]["guid"], result2[0]["guid"])

    def test_fixture_data_structure(self):
        """Validate the structure of the fixture data."""
        # Should have hits
        self.assertIn("hits", self.fixture_data)
        self.assertGreater(len(self.fixture_data["hits"]), 0)

        # Check first item structure
        first_item = self.fixture_data["hits"][0]
        self.assertIsInstance(first_item, dict)

        # Should have TT-specific fields
        expected_fields = ["uri", "source"]
        for field in expected_fields:
            if field in first_item:
                self.assertIsInstance(first_item[field], str)

        # Source should be TT-related
        if "source" in first_item:
            self.assertTrue(first_item["source"].startswith("TT"))


if __name__ == "__main__":
    unittest.main()
