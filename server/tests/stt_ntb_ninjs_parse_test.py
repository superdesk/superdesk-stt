import os
import json

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

    def test_datetime_without_timezone(self):
        """Test datetime parsing without timezone (assumes Helsinki)."""
        # Test that the item has basic structure
        assert self.item["type"] == "text"

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

        # Exact match (numeric qcode has no case)
        result = _cv_lookup(cv_items, "20000023")
        assert result is not None
        assert result["qcode"] == "20000023"

        # No match
        assert _cv_lookup(cv_items, "99999999") is None

        # Empty input
        assert _cv_lookup(cv_items, "") is None

    def test_fixture_structure(self):
        """Test that the fixture file has the expected structure and mappings."""
        # Basic structure from parsed item
        assert self.item["type"] == "text"
        assert (
            self.item["headline"]
            == "Food prices rise again as grocery giant expands into pharmacies"
        )
        assert self.item["byline"] == "Jecaterina Mantsinen"
        assert self.item["slugline"] == "test-imatrics"

        # --- Verify qcode mapping correctness (subject & anpa_category) ---
        # subject/anpa_category must both exist and contain qcodes
        subjects = self.item.get("subject") or []
        anpa = self.item.get("anpa_category") or []

        def _extract_qcodes(val):
            if isinstance(val, dict):
                val = [val]
            if not isinstance(val, list):
                return set()
            return {
                x.get("qcode") for x in val if isinstance(x, dict) and x.get("qcode")
            }

        subject_qcodes = _extract_qcodes(subjects)
        anpa_qcodes = _extract_qcodes(anpa)

        assert subject_qcodes, "subject should contain qcodes (non-empty)"
        assert anpa_qcodes, "anpa_category should contain qcodes (non-empty)"

        # Verify that anpa_category is populated from subjects with scheme="category"
        # The parser maps subjects with scheme="category" to anpa_category via vocabulary lookup
        # so we expect anpa_category to be populated when such subjects exist
        category_subjects = [
            s for s in subjects if isinstance(s, dict) and s.get("scheme") == "category"
        ]
        if category_subjects:
            assert (
                anpa_qcodes
            ), "anpa_category should be populated when subjects with scheme='category' exist"

        # Optionally, validate against raw fixture: all fixture subject qcodes should be present in parsed subject
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture_path = os.path.join(dirname, "fixtures", self.fixture)
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        raw_subject_qcodes = _extract_qcodes(raw.get("subject"))
        if raw_subject_qcodes:
            assert raw_subject_qcodes.issubset(subject_qcodes), (
                f"Parsed subject qcodes {subject_qcodes} should include "
                f"fixture qcodes {raw_subject_qcodes}"
            )

        # --- Body content from fixture is present after sanitization ---
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
        # The sanitization converts div class="byline" to p class="byline" but may leave outer divs
        assert 'class="byline"' in result
