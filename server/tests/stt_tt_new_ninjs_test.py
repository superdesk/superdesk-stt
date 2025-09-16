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
        # This is a text item from the fixture
        self.assertEqual(
            self.item["headline"],
            "Knivattack i köpcentrum hade rasistmotiv",
        )
        self.assertIn("source", self.item)
        self.assertIn("extra", self.item)
        self.assertIn("stt_meta", self.item["extra"])
        self.assertEqual(self.item["source"], "TT")

        # Text item has sector "UTR" which maps to Ulkomaat (14)
        self.assertEqual(self.item["extra"]["stt_meta"]["department_id"], 14)
        self.assertEqual(self.item["extra"]["stt_meta"]["department_name"], "Ulkomaat")
        self.assertEqual(self.item["extra"]["stt_meta"]["tt_department_code"], "UTR")
        self.assertEqual(
            self.item["anpa_category"], [{"qcode": "14", "name": "Ulkomaat"}]
        )

    def test_body_html_and_byline(self):
        html = self.item.get("body_html", "")
        # Text items have body_html content
        self.assertNotEqual(html, "")
        self.assertIn("Knivattack i köpcentrum hade rasistmotiv", html)
        # Text items may not have byline in this fixture
        self.assertEqual(self.item["type"], "text")

    def test_item_type_and_version_fields(self):
        self.assertEqual(self.item["type"], "text")
        # For text items, check the main item URI and mimetype
        self.assertEqual(
            self.item["uri"],
            "http://tt.se/media/text/241003-finlanduleaborgkniv-9fc4edfa",
        )
        self.assertEqual(self.item["mimetype"], "text/html")

    def test_external_id_and_description(self):
        # This should be the text item's URI
        self.assertEqual(
            self.item["uri"],
            "http://tt.se/media/text/241003-finlanduleaborgkniv-9fc4edfa",
        )

    def test_associations_removed(self):
        self.assertNotIn("associations", self.item)

    def test_versioncreated_present_for_text_items(self):
        """Text items should have versioncreated timestamp."""
        self.assertEqual(self.item.get("type"), "text")
        self.assertIn("versioncreated", self.item)

    def test_versioncreated_capping_method_directly(self):
        """Test the _cap_versioncreated_to_parent method directly using fixture data."""
        parser = self.parser_class()

        # Create a picture processing context where the picture associations include
        # the parent text item data. This simulates how the capping would work.
        ninjs_data = {
            "associations": {
                "parent_text": {
                    "type": "text",
                    "versioncreated": "2024-10-03T14:32:36+02:00",  # From fixture
                    "uri": "http://tt.se/media/text/241003-finlanduleaborgkniv-9fc4edfa",
                }
            }
        }

        # Picture item with later versioncreated (simulating a picture item being processed)
        from dateutil.parser import isoparse

        item = {"versioncreated": isoparse("2024-10-03T16:00:00+02:00")}

        # Call the capping method - it should find the text item in associations and cap to its timestamp
        parser._cap_versioncreated_to_parent(item, ninjs_data)

        # The versioncreated should be capped to the parent text item's timestamp
        expected_time = isoparse("2024-10-03T14:32:36+02:00")  # From fixture
        self.assertEqual(item["versioncreated"], expected_time)

    def test_versioncreated_no_capping_when_no_parent(self):
        """Test that versioncreated is preserved when no parent text item exists using fixture data."""
        # Create test data based on fixture picture association but without any text items
        # This simulates a standalone picture item (which is rare but possible)
        picture_from_fixture = self.json_data["associations"]["a001"]
        test_data = dict(picture_from_fixture)  # Copy actual picture data from fixture
        test_data["versioncreated"] = "2024-10-03T16:00:00+02:00"
        test_data["associations"] = {
            "other_picture": {
                "type": "picture",  # Only picture associations, no text items
                "uri": "http://tt.se/media/image/another-picture",
                "versioncreated": "2024-10-03T14:32:36+02:00",
            }
        }

        parser = self.parser_class()
        result = parser._transform_from_ninjs(test_data)

        # The versioncreated should remain unchanged since no parent text item exists
        from dateutil.parser import isoparse

        expected_time = isoparse("2024-10-03T16:00:00+02:00")
        self.assertEqual(result["versioncreated"], expected_time)

    def test_versioncreated_capping_with_multiple_timestamp_fields(self):
        """Test that versioncreated is capped to the earliest available timestamp in parent text item using fixture data."""
        parser = self.parser_class()

        # Create associations with a text item that has multiple timestamp fields
        # This tests that the earliest timestamp is used for capping
        ninjs_data = {
            "associations": {
                "parent_text": {
                    "type": "text",
                    "uri": "http://tt.se/media/text/241003-finlanduleaborgkniv-9fc4edfa",  # From fixture
                    "versioncreated": "2024-10-03T14:32:36+02:00",  # From fixture
                    "firstcreated": "2024-10-03T12:30:00+02:00",  # Earlier than versioncreated
                    "pubdate": "2024-10-03T13:15:00+02:00",  # Between the two
                }
            }
        }

        # Picture item with later versioncreated
        from dateutil.parser import isoparse

        item = {"versioncreated": isoparse("2024-10-03T18:00:00+02:00")}

        # Call the capping method
        parser._cap_versioncreated_to_parent(item, ninjs_data)

        # Should be capped to the earliest timestamp (firstcreated)
        expected_time = isoparse("2024-10-03T12:30:00+02:00")
        self.assertEqual(item["versioncreated"], expected_time)
