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
        # The parser sets headline from the main JSON headline field
        # For picture items, it uses description_text from associations
        self.assertEqual(
            self.item["headline"],
            "I somras skedde två rasistiskt motiverade knivdåd på ett köpcentrum i Uleåborg, med bara några dagars mellanrum. Arkivbild.",
        )
        self.assertIn("source", self.item)
        self.assertIn("desk", self.item)
        self.assertIn("extra", self.item)
        self.assertIn("stt_meta", self.item["extra"])
        self.assertEqual(self.item["source"], "TT")
        self.assertEqual(self.item["desk"], "Ulkomaat")

        self.assertEqual(self.item["extra"]["stt_meta"]["department_id"], 3)
        self.assertEqual(self.item["extra"]["stt_meta"]["department_name"], "Kotimaa")
        self.assertIsNone(self.item["extra"]["stt_meta"]["tt_department_code"])
        self.assertEqual(
            self.item["anpa_category"], [{"qcode": "3", "name": "Kotimaa"}]
        )

    def test_body_html_and_byline(self):
        html = self.item.get("body_html", "")
        self.assertEqual(html, "")
        self.assertIn("byline", self.item)
        self.assertEqual(self.item["byline"], "Fredrik Sandberg/TT")
        self.assertEqual(self.item["type"], "picture")
        # versioncreated is not set by the parser for picture items

    def test_item_type_and_version_fields(self):
        self.assertEqual(self.item["type"], "picture")
        self.assertIn("guid", self.item)
        self.assertIn("uri", self.item)
        self.assertIn("mimetype", self.item)

    def test_external_id_and_description(self):
        self.assertEqual(
            self.item["uri"],
            "http://tt.se/media/image/sdlr1tDM7WXjoU-crop_w2264_h1273_x522_y789",
        )

    def test_associations_removed(self):
        self.assertNotIn("associations", self.item)
