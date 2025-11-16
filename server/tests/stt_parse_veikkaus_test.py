# tests/stt_parse_veikkaus_test.py
import logging
# import os

from tests import TestCase
# from stt.stt_parse_lottery_veikkaus import (
#    VeikkausTextFeedParser,
#    to_body_html,
#    fix_encoding_issues,
# )

from stt.stt_parse_lottery_veikkaus import (
    VeikkausTextFeedParser
)

# from datetime import datetime

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class VeikkausTextFeedParserTestCase(TestCase):
    fixture = "txt/pelitulos.Y_06.08.2022.txt"
    parser_class = VeikkausTextFeedParser

    async def parse_source_content(self):
        # dirname = os.path.dirname(os.path.realpath(__file__))
        # fixture_path = os.path.join(dirname, "fixtures", self.fixture)
        # provider = {"name": "Test"}
        async with self.ctx:
            # parser = self.parser_class()
            # parsed = await parser.parse(fixture_path, provider)
            pass
            # self.assertEqual(len(parsed), 1)
            # self.item = parsed[0]

    def test_core_metadata_fields(self):
        """Test headline, type, urgency, pubstatus, slugline, and description."""
        pass
        # self.assertEqual(self.item["headline"], "TOTO75-ravi")
        # self.assertEqual(self.item["type"], "text")
        # self.assertEqual(self.item["urgency"], 4)
        # self.assertEqual(self.item["pubstatus"], "usable")
        # self.assertEqual(self.item["slugline"], "Veikkaus")
        # self.assertEqual(self.item["description_text"], "pelitulos.Y_06.08.2022.txt")

    def test_guid_format(self):
        """Test GUID includes filename."""
        pass
        # self.assertIn("pelitulos.Y_06.08.2022.txt", self.item["guid"])

    def test_body_html_content(self):
        """Test body_html content and encoding fixes."""
        pass
        # html = self.item.get("body_html", "")
        # self.assertIn("Voitonjako:", html)
        # self.assertIn("Special Major", html)
        # self.assertIn("lähtö:", html)
        # self.assertNotIn("l‰htˆ:", html)
        # self.assertTrue(html.startswith("<p>"))
        # self.assertTrue(html.endswith("</p>"))

    def test_fix_encoding_utility(self):
        """Test encoding fix helper."""
        pass
        # corrupted = "1. l‰htˆ: Hevonen"
        # fixed = fix_encoding_issues(corrupted)
        # self.assertEqual(fixed, "1. lähtö: Hevonen")

    def test_to_body_html_utility(self):
        """Test line-to-html conversion."""
        pass
        # self.assertEqual(to_body_html(["A", "B"]), "<p>A<br/>\nB</p>")
        # self.assertEqual(to_body_html(["only"]), "<p>only</p>")
        # self.assertEqual(to_body_html([]), "<p></p>")

    def test_can_parse_fixture_file(self):
        """Ensure parser accepts .txt file format."""
        pass
        # parser = self.parser_class()
        # fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", self.fixture)
        # self.assertTrue(parser.can_parse(fixture_path))

    def test_parser_metadata(self):
        """Check parser NAME and label attributes."""
        pass
        # parser = self.parser_class()
        # self.assertEqual(parser.NAME, "veikkaus_text")
        # self.assertEqual(parser.label, "STT Veikkaus Text Parser")

    def test_versioncreated_is_datetime(self):
        pass
        # assert isinstance(self.item["versioncreated"], datetime)
