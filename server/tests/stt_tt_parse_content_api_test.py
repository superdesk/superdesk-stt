# -*- coding: utf-8 -*-
import os
import unittest
from datetime import timedelta
from flask import json

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

        # Parser should return a dict
        self.assertIsInstance(result, dict)

        # Check required fields
        self.assertEqual("text", result["type"])
        self.assertEqual("usable", result["pubstatus"])
        self.assertIn("guid", result)
        self.assertIn("versioncreated", result)

        # Check original data is preserved
        self.assertEqual(test_item["uri"], result["uri"])
        self.assertEqual(test_item["headline"], result["headline"])

        # Check GUID generation
        self.assertTrue(
            result["guid"].startswith("urn:newsml:stt.fi:stt_tt_content_api:")
        )

    def test_parser_content_expiry(self):
        """Test parser content expiry calculation."""
        test_item = {"_id": "expiry_test", "source": "STT"}

        provider = {"config": {"content_expiry": 24}}  # 24 hours

        result = self.parser.parse(test_item, provider=provider)

        self.assertIsNotNone(result.get("expiry"))

        # Verify expiry is set to approximately 24 hours from versioncreated
        expected_expiry = result["versioncreated"] + timedelta(hours=24)
        time_diff = abs((result["expiry"] - expected_expiry).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute tolerance

    def test_parser_minimal_item(self):
        """Test parser with minimal required data."""
        minimal_item = {"source": "STT"}

        result = self.parser.parse(minimal_item, provider={"config": {}})

        # Should have all required defaults
        self.assertEqual("text", result["type"])
        self.assertEqual("usable", result["pubstatus"])
        self.assertIn("guid", result)
        self.assertIn("versioncreated", result)
        self.assertEqual("", result["headline"])
        self.assertEqual("", result["body_html"])

    def test_parser_guid_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        test_item = self.fixture_data["hits"][0]

        result1 = self.parser.parse(test_item, provider={"config": {}})
        result2 = self.parser.parse(test_item, provider={"config": {}})

        self.assertEqual(result1["guid"], result2["guid"])

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
