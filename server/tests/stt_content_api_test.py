# ---- Fixture-based parser test (simple) -------------------------------------
from tests import TestCase  # noqa: E402
from stt.io.feed_parsers.stt_parse_content_api import ContentAPIItemParser  # noqa: E402


class ContentAPIItemParserFixtureTestCase(TestCase):
    """Lightweight fixture-based test to ensure the parser handles the
    real Content API fixture end-to-end. This follows the same pattern used
    by other parser tests in this repo that rely on `fixture` and
    `parser_class` attributes.

    We intentionally point to the absolute fixture path requested by the
    user to avoid any ambiguity in resolution.
    """

    fixture = "api/stt_content_api.json"
    parser_class = ContentAPIItemParser
    parse_source = False  # Disable automatic XML parsing

    def parse_source_content(self):
        """Override to handle JSON fixture instead of XML."""
        import json
        import os

        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)

        with open(fixture, "r") as f:
            data = json.load(f)

        # Extract items from the fixture
        if isinstance(data, dict) and "_items" in data:
            self.items = data["_items"]
        elif isinstance(data, list):
            self.items = data
        else:
            self.items = [data]

    def test_fixture_parses_and_has_expected_shape(self):
        # Parse the JSON fixture
        self.parse_source_content()

        # Instantiate parser and parse the first item to validate core fields.
        parser = self.parser_class()
        first_raw = self.items[0]
        parsed = parser.parse(first_raw, provider={"config": {}})

        # The parser returns a list, so get the first item
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Minimal contract checks
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("type"), "text")
        self.assertEqual(parsed.get("pubstatus"), "usable")
        self.assertIn("guid", parsed)
        self.assertIn("versioncreated", parsed)

        # Optional sanity checks if present in fixture
        if "headline" in parsed:
            self.assertIsInstance(parsed["headline"], str)
        if "body_html" in parsed:
            self.assertIsInstance(parsed["body_html"], str)

    def test_all_fixture_items_parse_successfully(self):
        """Test that all items in the fixture can be parsed without errors."""
        self.parse_source_content()

        parser = self.parser_class()

        # Parse all items from the fixture
        for i, raw_item in enumerate(self.items):
            with self.subTest(item_index=i):
                parsed = parser.parse(raw_item, provider={"config": {}})

                # Parser returns a list
                if isinstance(parsed, list):
                    parsed = parsed[0]

                # Each item should have required fields
                self.assertIsInstance(parsed, dict)
                self.assertIn("type", parsed)
                self.assertIn("pubstatus", parsed)
                self.assertIn("guid", parsed)
                self.assertIn("versioncreated", parsed)

    def test_field_mapping_with_fixture_data(self):
        """Test field mapping functionality with real fixture data."""
        self.parse_source_content()

        parser = self.parser_class()
        first_item = self.items[0]

        # Test with field mapping configuration
        provider = {
            "config": {
                "field_mapping": {
                    "custom_headline": "headline",
                    "custom_body": "body_html",
                    "extra.original_source": "source",
                }
            }
        }

        parsed = parser.parse(first_item, provider=provider)
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Check that field mapping worked
        if "headline" in first_item:
            self.assertEqual(parsed.get("custom_headline"), first_item["headline"])
        if "body_html" in first_item:
            self.assertEqual(parsed.get("custom_body"), first_item["body_html"])
        if "source" in first_item:
            self.assertIn("extra", parsed)
            self.assertEqual(parsed["extra"]["original_source"], first_item["source"])

    def test_guid_generation_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        self.parse_source_content()

        parser = self.parser_class()
        first_item = self.items[0]

        # Parse the same item multiple times
        parsed1 = parser.parse(first_item, provider={"config": {}})
        parsed2 = parser.parse(first_item, provider={"config": {}})

        if isinstance(parsed1, list):
            parsed1 = parsed1[0]
        if isinstance(parsed2, list):
            parsed2 = parsed2[0]

        # GUIDs should be identical for the same input
        self.assertEqual(parsed1["guid"], parsed2["guid"])
        self.assertTrue(parsed1["guid"].startswith("urn:newsml:stt.fi:contentapi:"))

    def test_timestamp_handling_with_fixture_data(self):
        """Test timestamp normalization with real fixture data."""
        self.parse_source_content()

        parser = self.parser_class()

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
            parsed = parser.parse(item_with_timestamp, provider={"config": {}})
            if isinstance(parsed, list):
                parsed = parsed[0]

            # Check that timestamps are datetime objects
            from datetime import datetime

            if "versioncreated" in parsed:
                self.assertIsInstance(parsed["versioncreated"], datetime)
                self.assertIsNotNone(parsed["versioncreated"].tzinfo)

    def test_content_expiry_calculation(self):
        """Test content expiry calculation with provider configuration."""
        self.parse_source_content()

        parser = self.parser_class()
        first_item = self.items[0]

        # Test with expiry configuration
        provider = {"config": {"content_expiry": 48}}  # 48 hours

        parsed = parser.parse(first_item, provider=provider)
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Should have expiry set
        if parsed.get("expiry"):
            from datetime import datetime, timedelta

            self.assertIsInstance(parsed["expiry"], datetime)

            # Should be approximately 48 hours after versioncreated
            if parsed.get("versioncreated"):
                expected_expiry = parsed["versioncreated"] + timedelta(hours=48)
                time_diff = abs((parsed["expiry"] - expected_expiry).total_seconds())
                self.assertLess(time_diff, 60)  # Within 1 minute tolerance

    def test_parser_handles_minimal_items(self):
        """Test parser handles items with minimal required fields."""
        parser = self.parser_class()

        # Test with minimal item
        minimal_item = {"source": "STT"}

        parsed = parser.parse(minimal_item, provider={"config": {}})
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Should have all required defaults
        self.assertEqual(parsed["type"], "text")
        self.assertEqual(parsed["pubstatus"], "usable")
        self.assertIn("guid", parsed)
        self.assertIn("versioncreated", parsed)
        self.assertEqual(parsed["headline"], "")
        self.assertEqual(parsed["body_html"], "")

    def test_parser_handles_missing_optional_fields(self):
        """Test parser gracefully handles missing optional fields."""
        parser = self.parser_class()

        # Test with item missing common optional fields
        incomplete_item = {
            "_id": "test_item",
            "source": "STT",
            # Missing: headline, body_html, versioncreated, etc.
        }

        parsed = parser.parse(incomplete_item, provider={"config": {}})
        if isinstance(parsed, list):
            parsed = parsed[0]

        # Should not raise errors and should have defaults
        self.assertIsInstance(parsed, dict)
        self.assertIn("guid", parsed)
        self.assertIn("type", parsed)
        self.assertIn("pubstatus", parsed)
        self.assertIn("headline", parsed)
        self.assertIn("body_html", parsed)

    def test_parser_with_different_provider_configs(self):
        """Test parser behavior with different provider configurations."""
        self.parse_source_content()

        parser = self.parser_class()
        first_item = self.items[0]

        # Test with empty config
        parsed1 = parser.parse(first_item, provider={"config": {}})
        if isinstance(parsed1, list):
            parsed1 = parsed1[0]

        # Test with field mapping config
        parsed2 = parser.parse(
            first_item,
            provider={"config": {"field_mapping": {"custom_field": "headline"}}},
        )
        if isinstance(parsed2, list):
            parsed2 = parsed2[0]

        # Test with expiry config
        parsed3 = parser.parse(first_item, provider={"config": {"content_expiry": 24}})
        if isinstance(parsed3, list):
            parsed3 = parsed3[0]

        # All should be valid but potentially different
        for parsed in [parsed1, parsed2, parsed3]:
            self.assertIsInstance(parsed, dict)
            self.assertIn("guid", parsed)
            self.assertIn("type", parsed)

        # Check specific differences
        if "headline" in first_item:
            self.assertEqual(parsed2.get("custom_field"), first_item["headline"])

        # Expiry should only be set in parsed3
        self.assertIsNone(parsed1.get("expiry"))
        if parsed3.get("expiry"):
            from datetime import datetime

            self.assertIsInstance(parsed3["expiry"], datetime)

    def test_fixture_data_structure_validation(self):
        """Validate the structure and content of the fixture data itself."""
        self.parse_source_content()

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

        # Source should be STT
        if "source" in first_item:
            self.assertTrue(first_item["source"].startswith("STT"))

    def test_parser_return_format_consistency(self):
        """Test that parser always returns consistent format."""
        self.parse_source_content()

        parser = self.parser_class()

        # Test with single item
        single_result = parser.parse(self.items[0], provider={"config": {}})
        self.assertIsInstance(single_result, list)
        self.assertEqual(len(single_result), 1)
        self.assertIsInstance(single_result[0], dict)

        # Test with list of items
        if len(self.items) > 1:
            multi_result = parser.parse(self.items[:2], provider={"config": {}})
            self.assertIsInstance(multi_result, list)
            self.assertEqual(len(multi_result), 2)
            for item in multi_result:
                self.assertIsInstance(item, dict)
