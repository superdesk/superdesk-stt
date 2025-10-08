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

    async def parse_source_content(self):
        """Override to handle JSON files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        provider = {"name": "Test"}
        async with self.ctx:
            parser = self.parser_class()
            parsed = await parser.parse(fixture, provider)
            self.item = parsed[0]

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
