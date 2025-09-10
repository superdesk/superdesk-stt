import json
import os
from tests import TestCase
from stt.stt_tt_new_parse_ninjs import STTTTNEWNINJSFeedParser


def load_file(file_path: str) -> dict:
    """Load and parse a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class STTTTNEWNINJSFeedParserTest(TestCase):
    fixture = "json/stt_new_ninjs.json"
    parser_class = STTTTNEWNINJSFeedParser

    def parse_source_content(self):
        """Override to handle JSON files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        provider = {"name": "Test"}
        with self.ctx:
            parser = self.parser_class()
            self.json_data = load_file(fixture)
            self.item = parser.parse(fixture, provider)[0]

    def test_headline_and_metadata(self):
        # The parser extracts picture associations from text items
        # For picture items, it uses description_text from associations
        self.assertEqual(
            self.item["headline"],
            "I somras skedde två rasistiskt motiverade knivdåd på ett köpcentrum i Uleåborg, med bara några dagars mellanrum. Arkivbild.",
        )
        self.assertIn("source", self.item)
        self.assertIn("extra", self.item)
        self.assertIn("stt_meta", self.item["extra"])
        self.assertEqual(self.item["source"], "TT")

        # Picture items without sector fall back to default department (Kotimaa)
        self.assertEqual(self.item["extra"]["stt_meta"]["department_id"], 3)
        self.assertEqual(self.item["extra"]["stt_meta"]["department_name"], "Kotimaa")
        self.assertIsNone(self.item["extra"]["stt_meta"]["tt_department_code"])
        self.assertEqual(
            self.item["anpa_category"], [{"qcode": "3", "name": "Kotimaa"}]
        )

    def test_body_html_and_byline(self):
        html = self.item.get("body_html", "")
        # Picture items don't have body_html content
        self.assertEqual(html, "")
        self.assertIn("byline", self.item)
        self.assertEqual(self.item["byline"], "Fredrik Sandberg/TT")
        self.assertEqual(self.item["type"], "picture")

    def test_item_type_and_version_fields(self):
        self.assertEqual(self.item["type"], "picture")
        self.assertIn("guid", self.item)
        self.assertIn("uri", self.item)
        self.assertIn("mimetype", self.item)

    def test_external_id_and_description(self):
        # This should be the picture association's URI
        self.assertEqual(
            self.item["uri"],
            "http://tt.se/media/image/sdlr1tDM7WXjoU-crop_w2264_h1273_x522_y789",
        )

    def test_associations_removed(self):
        self.assertNotIn("associations", self.item)

    def test_versioncreated_absent_for_picture_items(self):
        """Picture items should not set versioncreated; timestamp comes from parent text item."""
        self.assertEqual(self.item.get("type"), "picture")
        self.assertNotIn("versioncreated", self.item)

    def test_versioncreated_capping_method_directly(self):
        """Test the _cap_versioncreated_to_parent method directly."""
        parser = self.parser_class()

        # Test data with text association from fixture
        ninjs_data = {
            "associations": {
                "text_item": {
                    "type": "text",
                    "versioncreated": "2024-10-03T14:32:36+02:00",  # From fixture
                    "uri": "http://tt.se/media/text/241003-finlanduleaborgkniv-9fc4edfa",
                }
            }
        }

        # Item with later versioncreated
        from dateutil.parser import isoparse

        item = {"versioncreated": isoparse("2024-10-03T16:00:00+02:00")}

        # Call the capping method
        parser._cap_versioncreated_to_parent(item, ninjs_data)

        # The versioncreated should be capped to the parent text item's timestamp
        expected_time = isoparse("2024-10-03T14:32:36+02:00")
        self.assertEqual(item["versioncreated"], expected_time)

    def test_versioncreated_no_capping_when_no_parent(self):
        """Test that versioncreated is preserved when no parent text item exists."""
        # Create a picture item without text associations
        test_data = {
            "uri": "http://tt.se/media/image/test-picture",
            "type": "picture",
            "versioncreated": "2024-10-03T16:00:00+02:00",
            "associations": {
                "other_picture": {
                    "type": "picture",  # Not a text item
                    "versioncreated": "2024-10-03T14:32:36+02:00",
                }
            },
        }

        parser = self.parser_class()
        result = parser._transform_from_ninjs(test_data)

        # The versioncreated should remain unchanged since no parent text item exists
        from dateutil.parser import isoparse

        expected_time = isoparse("2024-10-03T16:00:00+02:00")
        self.assertEqual(result["versioncreated"], expected_time)

    def test_versioncreated_capping_with_multiple_parent_candidates(self):
        """Test that versioncreated is capped to the earliest parent text item timestamp."""
        # Use fixture data as base and add multiple text associations
        test_data = dict(self.json_data)  # Copy fixture data
        test_data.update(
            {
                "type": "picture",
                "versioncreated": "2024-10-03T18:00:00+02:00",  # Latest
                "uri": "http://tt.se/media/image/test-picture",
            }
        )

        # Add another text association with earlier timestamp
        test_data["associations"]["text_item_2"] = {
            "type": "text",
            "versioncreated": "2024-10-03T13:00:00+02:00",  # Earlier than fixture
            "firstcreated": "2024-10-03T12:30:00+02:00",  # Even earlier
        }

        parser = self.parser_class()
        result = parser._transform_from_ninjs(test_data)

        # The versioncreated should be capped to the earliest parent text item's timestamp
        from dateutil.parser import isoparse

        expected_time = isoparse(
            "2024-10-03T12:30:00+02:00"
        )  # firstcreated is earliest
        self.assertEqual(result["versioncreated"], expected_time)
