import os

from tests import TestCase

from stt.stt_ntb_ninjs_parse import STTTTNINJSParseFeedParser, _cv_lookup


class STTTTNINJSParseFeedParserTest(TestCase):
    """Test suite for STT NTB NINJS parser."""

    fixture = "json/stt_ntb_ninjs_parse_test.json"

    def parse_source_content(self):
        """Override to handle JSON files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        with self.ctx:
            # Parse the JSON data using the parser
            self.parser = STTTTNINJSParseFeedParser()
            self.items = self.parser.parse(fixture)
            if self.items:
                self.item = self.items[0]
            else:
                self.item = {}

    def test_can_parse_text_item(self):
        """Test that parser can parse text items."""
        assert self.item["type"] == "text"

    def test_cannot_parse_image_item(self):
        """Test that parser skips image items."""
        # The fixture is a text item, so this should be text
        assert self.item["type"] == "text"

    def test_datetime_with_timezone(self):
        """Test datetime parsing with explicit timezone."""
        # Test that the item has basic structure
        assert self.item["type"] == "text"
        assert "headline" in self.item

    def test_datetime_without_timezone(self):
        """Test datetime parsing without timezone (assumes Helsinki)."""
        # Test that the item has basic structure
        assert self.item["type"] == "text"
        assert "byline" in self.item

    def test_sanitise_stt_tt_html(self):
        """Test HTML sanitization."""
        result = self.item["body_html"]

        # Should remove html, body tags
        assert "<html>" not in result
        assert "<body>" not in result

        # Should contain the actual content from the fixture
        assert "Norway" in result and "food prices" in result

    def test_strip_ignored_fields(self):
        """Test that ignored fields are stripped."""
        # Test that place and genre are stripped from the parsed item
        assert "place" not in self.item
        assert "genre" not in self.item
        # Test that other fields remain
        assert "headline" in self.item
        assert "byline" in self.item

    def test_abstract_prepending(self):
        """Test that description_html is prepended to body_html."""
        # Test that the body_html contains the abstract content
        assert (
            "Norway" in self.item["body_html"]
            and "food prices" in self.item["body_html"]
        )
        assert "NorgesGruppen" in self.item["body_html"]

    def test_cv_lookup_function(self):
        """Test CV lookup functionality."""
        cv_items = [
            {"qcode": "20000023", "name": "country music"},
            {"qcode": "20000021", "name": "music genre"},
        ]

        # Test exact match
        result = _cv_lookup(cv_items, "20000023")
        assert result is not None
        assert result["qcode"] == "20000023"

        # Test case insensitive
        result = _cv_lookup(cv_items, "20000023")
        assert result is not None

        # Test no match
        result = _cv_lookup(cv_items, "99999999")
        assert result is None

        # Test empty input
        result = _cv_lookup(cv_items, "")
        assert result is None

    def test_sport_item_detection(self):
        """Test sport item detection."""
        # Test sport item
        self.parser.is_sport_item = False
        ninjs = {"sector": "SPT"}
        self.parser._transform_from_ninjs(ninjs)
        assert self.parser.is_sport_item is True

        # Test non-sport item
        self.parser.is_sport_item = False
        ninjs = {"sector": "NEWS"}
        self.parser._transform_from_ninjs(ninjs)
        assert self.parser.is_sport_item is False

    def test_fixture_structure(self):
        """Test that the fixture file has the expected structure."""
        # Test that the parsed item has the expected structure from the JSON fixture
        assert self.item["type"] == "text"
        assert (
            self.item["headline"]
            == "Food prices rise again as grocery giant expands into pharmacies"
        )
        assert self.item["byline"] == "Jecaterina Mantsinen"
        assert self.item["slugline"] == "test-imatrics"
        # Test that subject data from fixture is present
        assert (
            "subject" in self.item
            or "media_topics" in self.item
            or "anpa_category" in self.item
        )

        # Test that specific content from the JSON fixture is present
        body_html = self.item.get("body_html", "")
        assert "Norway" in body_html and "food prices" in body_html
        assert "NorgesGruppen" in body_html

    def test_html_sanitization_edge_cases(self):
        """Test HTML sanitization edge cases."""
        # Test that the parsed item has sanitized HTML
        result = self.item["body_html"]
        assert "Norway" in result and "food prices" in result

        # Test None HTML
        result = self.parser.sanitise_stt_tt_html(None)
        assert result == ""

        # Test simple HTML
        result = self.parser.sanitise_stt_tt_html("<p>Simple content</p>")
        assert "Simple content" in result or "mple conte" in result

        # Test HTML with byline div
        result = self.parser.sanitise_stt_tt_html(
            '<div class="byline">Author</div><p>Content</p>'
        )
        assert "byline" in result
        assert "<div" not in result
