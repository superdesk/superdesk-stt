# ---- Fixture-based parser test (simple) -------------------------------------
import json
import os
import unittest

from stt.io.feed_parsers.stt_parse_content_api import ContentAPIItemParser  # noqa: E402


def _load_fixture_items() -> list:
    """Load and normalise JSON items from the fixture file."""

    fixture_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "fixtures",
        "api/stt_content_api.json",
    )
    with open(fixture_path, "r") as fh:
        data = json.load(fh)

    if isinstance(data, dict) and "_items" in data:
        return data["_items"]
    if isinstance(data, list):
        return data
    return [data]


class ContentAPIItemParserFixtureTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.items = _load_fixture_items()

    def setUp(self):
        self.parser = ContentAPIItemParser()

    def test_fixture_parses_and_has_expected_shape(self):
        # Instantiate parser and parse the first item to validate core fields.
        first_raw = self.items[0]
        parsed = self.parser.parse(first_raw, provider={"config": {}})

        # The parser returns a list, so get the first item
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Minimal contract checks
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("type"), "text")
        self.assertEqual(parsed.get("pubstatus"), "usable")
        # Check actual values, not just presence
        from datetime import datetime

        self.assertIsInstance(parsed.get("uri"), str)
        self.assertIsInstance(parsed.get("versioncreated"), datetime)
        self.assertIsNotNone(parsed["versioncreated"].tzinfo)

        # Optional sanity checks if present in fixture
        if "headline" in parsed:
            self.assertIsInstance(parsed["headline"], str)
        if "body_html" in parsed:
            self.assertIsInstance(parsed["body_html"], str)

    def test_all_fixture_items_parse_successfully(self):
        """Test that all items in the fixture can be parsed without errors."""
        # Parse all items from the fixture
        for i, raw_item in enumerate(self.items):
            with self.subTest(item_index=i):
                parsed = self.parser.parse(raw_item, provider={"config": {}})

                # Parser returns a list
                if isinstance(parsed, list):
                    parsed = parsed[0]

                from datetime import datetime

                self.assertIsInstance(parsed, dict)
                self.assertEqual(parsed.get("type"), "text")
                self.assertEqual(parsed.get("pubstatus"), "usable")
                self.assertIsInstance(parsed.get("uri"), str)
                self.assertTrue(parsed["uri"])  # non-empty
                self.assertIsInstance(parsed.get("versioncreated"), datetime)
                self.assertIsNotNone(parsed["versioncreated"].tzinfo)

    def test_timestamp_handling_with_fixture_data(self):
        """Test timestamp normalization with real fixture data."""

        # Find an item with timestamp data
        item_with_timestamp = None
        for item in self.items:
            if any(
                field in item
                for field in ["versioncreated", "firstcreated", "_updated"]
            ):
                item_with_timestamp = item
                break

        if item_with_timestamp:
            parsed = self.parser.parse(item_with_timestamp, provider={"config": {}})
            if isinstance(parsed, list):
                parsed = parsed[0]

            # Check that timestamps are datetime objects
            from datetime import datetime

            if "versioncreated" in parsed:
                self.assertIsInstance(parsed["versioncreated"], datetime)
                self.assertIsNotNone(parsed["versioncreated"].tzinfo)

    def test_content_expiry_calculation(self):
        """Test content expiry configuration is ignored (functionality removed)."""
        first_item = self.items[0]

        # Test with expiry configuration
        provider = {"config": {"content_expiry": 48}}  # 48 hours

        parsed = self.parser.parse(first_item, provider=provider)
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Should not have expiry set (functionality removed)
        self.assertIsNone(parsed.get("expiry"))

    def test_parser_handles_minimal_items(self):
        """Test parser handles items with minimal required fields."""

        # Test with minimal item (needs headline or body_html to pass content validation)
        minimal_item = {"source": "STT", "headline": "Test headline"}

        parsed = self.parser.parse(minimal_item, provider={"config": {}})
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Should have all required defaults
        self.assertEqual(parsed["type"], "text")
        self.assertEqual(parsed["pubstatus"], "usable")
        from datetime import datetime

        self.assertIsInstance(parsed.get("versioncreated"), datetime)
        self.assertIsNotNone(parsed["versioncreated"].tzinfo)
        self.assertEqual(parsed["headline"], "Test headline")
        self.assertEqual(parsed["body_html"], "")

    def test_parser_handles_missing_optional_fields(self):
        """Test parser gracefully handles missing optional fields."""

        # Test with item missing common optional fields (needs content to pass validation)
        incomplete_item = {
            "_id": "test_item",
            "source": "STT",
            "body_html": "<p>Test content</p>",  # Added to pass content validation
            # Missing: headline, versioncreated, etc.
        }

        parsed = self.parser.parse(incomplete_item, provider={"config": {}})
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Should not raise errors and should have defaults
        from datetime import datetime

        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("type"), "text")
        self.assertEqual(parsed.get("pubstatus"), "usable")
        self.assertIsInstance(parsed.get("versioncreated"), datetime)
        self.assertIsNotNone(parsed["versioncreated"].tzinfo)
        self.assertIn("headline", parsed)
        self.assertIn("body_html", parsed)

    def test_parser_with_different_provider_configs(self):
        """Test parser behavior with different provider configurations."""
        first_item = self.items[0]

        # Test with empty config
        parsed1 = self.parser.parse(first_item, provider={"config": {}})
        if isinstance(parsed1, list):
            parsed1 = parsed1[0]

        # Test with expiry config (should be ignored)
        parsed2 = self.parser.parse(
            first_item, provider={"config": {"content_expiry": 24}}
        )
        if isinstance(parsed2, list):
            parsed2 = parsed2[0]

        # All should be valid but potentially different
        for parsed in [parsed1, parsed2]:
            self.assertIsInstance(parsed, dict)
            self.assertIn("type", parsed)

        # Expiry should not be set in either (functionality removed)
        self.assertIsNone(parsed1.get("expiry"))
        self.assertIsNone(parsed2.get("expiry"))

    def test_fixture_data_structure_validation(self):
        """Validate the structure and content of the fixture data itself."""
        # Should have items
        self.assertGreater(len(self.items), 0)

        # Check that fixture contains expected STT data structure
        first_item = self.items[0]
        self.assertIsInstance(first_item, dict)

        # Should have STT-specific fields (based on the fixture)
        expected_fields = ["source", "coverage_id"]
        for field in expected_fields:
            if field in first_item:
                self.assertIsInstance(first_item[field], str)

    def test_parser_return_format_consistency(self):
        """Test that parser always returns consistent format."""
        # Test with single item
        single_result = self.parser.parse(self.items[0], provider={"config": {}})
        self.assertIsInstance(single_result, list)
        self.assertEqual(len(single_result), 1)
        self.assertIsInstance(single_result[0], dict)

        # Test with list of items
        if len(self.items) > 1:
            multi_result = self.parser.parse(self.items[:2], provider={"config": {}})
            self.assertIsInstance(multi_result, list)
            self.assertEqual(len(multi_result), 2)
            for item in multi_result:
                self.assertIsInstance(item, dict)
