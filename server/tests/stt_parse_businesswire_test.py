import logging

from tests import TestCase
from stt.stt_parse_businesswire import BusinessWireParser

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BusinessWireParserTestCase(TestCase):
    fixture = "stt_businesswire_20240606079628r1.xml"
    parser_class = BusinessWireParser

    def test_headline_and_ids(self):
        # Test that the headline contains the expected key terms
        self.assertIn("Long-Term Data from Mirum", self.item["name"])
        self.assertIn("LIVMARLI Studies", self.item["name"])
        self.assertIn("EASL Congress", self.item["name"])
        self.assertEqual(self.item["external_id"], "20240606079628")

    def test_body_html_contains_keywords(self):
        html = self.item.get("body_html", "")
        assert "LIVMARLI" in html
        assert "Mirum Pharmaceuticals" in html

    def test_metadata_keywords(self):
        extra = self.item.get("extra", {})
        assert extra["bw_keywords"]["BWRegionKeywords"] == [
            "Europe",
            "North America",
        ]
        assert extra["bw_keywords"]["BWCountryKeywords"] == [
            "United States",
            "Italy",
        ]
        assert extra["bw_keywords"]["BWStateKeywords"] == ["California"]
        assert "Pharmaceutical" in extra["bw_keywords"]["BWIndustryKeywords"]

    def test_ticker_symbol(self):
        extra = self.item.get("extra", {})
        assert extra["securities"]["Ticker Symbol"] == "MIRM"
        assert extra["securities"]["Exchange"] == "NASDAQ"

    def test_slugline_and_byline(self):
        assert self.item["slugline"] == "CA-MIRUM-PHARMACEUTICALS"
        # ByLine is empty in the test XML fixture
        assert self.item["byline"] == ""

    def test_dateline_and_subjects(self):
        assert self.item["dateline"] == "FOSTER CITY, Calif."
        # Subject is not present in the test XML fixture
        assert "subject" not in self.item or len(self.item.get("subject", [])) == 0

    def test_keywords_flattened(self):
        # Confirm flattened keywords field includes merged values from
        # bw_keywords
        keywords = self.item.get("keywords", [])
        assert "United States" in keywords
        assert "Pharmaceutical" in keywords
        assert "California" in keywords
        assert "Europe" in keywords

    def test_headline_component_role(self):
        assert self.item["headline"] == self.item["name"]
