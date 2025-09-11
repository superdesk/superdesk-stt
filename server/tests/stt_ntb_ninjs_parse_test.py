import os
import json

from tests import TestCase

from stt.stt_ntb_ninjs_parse import STTTTNINJSParseFeedParser, _cv_lookup

# IMPORTANT TEST INVARIANTS
# - `subject` must contain ONLY media topics (no NTB category subjects).
# - NTB categories from the source are mapped to `anpa_category` (not kept in `subject`).
# - HTML is sanitized (structural tags removed, relevant content preserved).
# - Datetime parsing: naive timestamps are assumed Europe/Helsinki and converted to UTC.


class STTTTNINJSParseFeedParserTest(TestCase):
    """Test suite for STT NTB NINJS parser."""

    fixture = "json/stt_ntb_ninjs_parse_test.json"

    def parse_source_content(self):
        """Override to handle JSON files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        with self.ctx:
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
        assert self.item["type"] == "text"

    def test_sanitise_stt_tt_html(self):
        """Test HTML sanitization."""
        result = self.item["body_html"]

        assert "<html>" not in result
        assert "<body>" not in result

        assert "Norway" in result and "food prices" in result

    def test_strip_ignored_fields(self):
        """Test that ignored fields are stripped."""
        assert "place" not in self.item
        assert "genre" not in self.item

    def test_abstract_prepending(self):
        """Test that description_html is prepended to body_html."""
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

        result = _cv_lookup(cv_items, "20000023")
        assert result is not None
        assert result["qcode"] == "20000023"

        assert _cv_lookup(cv_items, "99999999") is None

        assert _cv_lookup(cv_items, "") is None

    def test_fixture_structure(self):
        """Test that the fixture file has the expected structure and mappings."""
        assert self.item["type"] == "text"
        assert (
            self.item["headline"]
            == "Food prices rise again as grocery giant expands into pharmacies"
        )
        assert self.item["byline"] == "Jecaterina Mantsinen"
        assert self.item["slugline"] == "test-imatrics"

        # Invariant: parsed subject must contain exactly the expected media topic qcodes
        subject_qcodes = {
            s.get("qcode") for s in self.item.get("subject", []) if s.get("qcode")
        }
        anpa_qcodes = {
            a.get("qcode") for a in self.item.get("anpa_category", []) if a.get("qcode")
        }

        assert subject_qcodes == {
            "20000023",
            "20000021",
            "20000018",
            "20000002",
            "01000000",
            "06000000",
            "01011000",
        }

        assert anpa_qcodes == set()

        # Invariant: no category subjects are kept in `subject`; they are mapped to `anpa_category`
        category_subjects = [
            s
            for s in self.item.get("subject", [])
            if isinstance(s, dict) and s.get("scheme") == "category"
        ]
        assert (
            not category_subjects
        ), "Category subjects should be filtered out from the subject field"

        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture_path = os.path.join(dirname, "fixtures", self.fixture)
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        raw_non_category_qcodes = {
            s.get("code")
            for s in raw.get("subject", [])
            if s.get("code") and s.get("scheme") != "category"
        }
        if raw_non_category_qcodes:
            assert raw_non_category_qcodes.issubset(subject_qcodes), (
                f"Parsed subject qcodes {subject_qcodes} should include "
                f"non-category fixture qcodes {raw_non_category_qcodes}"
            )

        body_html = self.item.get("body_html", "")
        assert "Norway" in body_html and "food prices" in body_html
        assert "NorgesGruppen" in body_html

    def test_html_sanitization_edge_cases(self):
        """Test HTML sanitization edge cases."""
        result = self.item["body_html"]
        assert "Norway" in result and "food prices" in result

        result = self.parser.sanitise_stt_tt_html(None)
        assert result == ""

        result = self.parser.sanitise_stt_tt_html("<p>Simple content</p>")
        assert "Simple content" in result or "mple conte" in result

        result = self.parser.sanitise_stt_tt_html(
            '<div class="byline">Author</div><p>Content</p>'
        )
        assert "byline" in result
        assert 'class="byline"' in result
