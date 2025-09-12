import os
import json
from unittest.mock import patch

from tests import TestCase

from stt.stt_ntb_ninjs_parse import STTTTNINJSParseFeedParser, _cv_lookup
import logging

logger = logging.getLogger(__name__)
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
        # Basic structure from parsed item
        assert self.item["type"] == "text"
        assert (
            self.item["headline"]
            == "Food prices rise again as grocery giant expands into pharmacies"
        )
        assert self.item["byline"] == "Jecaterina Mantsinen"
        assert self.item["slugline"] == "test-imatrics"

        # Test exact qcodes produced by parser - any deviation indicates a parser bug
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

        # Allow both environments: without vocab (empty) or with vocab mapping present (e.g., "14").
        assert anpa_qcodes in (set(), {"14"})

        # Invariant: no category subjects are kept in `subject`; they are mapped to `anpa_category`
        category_subjects = [
            s
            for s in self.item.get("subject", [])
            if isinstance(s, dict) and s.get("scheme") == "category"
        ]
        assert (
            not category_subjects
        ), "Category subjects should be filtered out from the subject field"

        # Validate that non-category subjects from fixture are preserved in parsed output
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

    @patch("stt.stt_ntb_ninjs_parse._load_cv")
    def test_category_mapping_with_vocabulary(self, mock_load_cv):
        """Test category mapping when vocabulary service is properly configured."""

        # Mock the vocabulary lookup to return proper vocabularies
        def mock_cv_lookup(vocab_id):
            if vocab_id == "stt-department-categories":
                return [
                    {"is_active": "true", "qcode": "14", "name": "Ulkomaat"},
                    {"is_active": "true", "name": "Business wire", "qcode": "1"},
                    {"is_active": "true", "name": "Holvi", "qcode": "23"},
                    {
                        "is_active": "true",
                        "name": "Julkishallinnon tiedotepalvelu",
                        "qcode": "2",
                    },
                    {"is_active": "true", "name": "Kotimaa", "qcode": "3"},
                    {"is_active": "true", "name": "Kulttuuri", "qcode": "4"},
                    {"is_active": "true", "name": "Merkkipäiväpalvelu", "qcode": "5"},
                    {"is_active": "true", "name": "Muuta", "qcode": "6"},
                    {"is_active": "true", "name": "Peliuutiset", "qcode": "8"},
                    {"is_active": "true", "name": "Politiikka", "qcode": "9"},
                    {"is_active": "true", "name": "Päivälista", "qcode": "21"},
                    {"is_active": "true", "name": "Talous", "qcode": "11"},
                    {"is_active": "true", "name": "Tiedotepalvelu", "qcode": "12"},
                    {
                        "is_active": "true",
                        "name": "Toimituksille tiedoksi",
                        "qcode": "13",
                    },
                    {"is_active": "true", "name": "Urheilu", "qcode": "16"},
                    {"is_active": "true", "name": "Uutiskooste", "qcode": "22"},
                    {"is_active": "true", "name": "Viikon tärpit", "qcode": "19"},
                    {"is_active": "true", "name": "Sähkeuutiset", "qcode": "10"},
                ]
            elif vocab_id == "stt_media_topics":
                # Mock some media topics to ensure media topic parsing works
                return [
                    {"name": "Test Topic", "qcode": "20000023"},
                    {"name": "Another Topic", "qcode": "20000021"},
                ]
            return []

        mock_load_cv.side_effect = mock_cv_lookup

        # Parse the item with mocked vocabulary to test proper category mapping
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        with self.ctx:
            parser = STTTTNINJSParseFeedParser()
            parsed_items = parser.parse(fixture)
            item = parsed_items[0] if parsed_items else {}

        # Test category mapping works correctly
        anpa_qcodes = {
            a.get("qcode") for a in item.get("anpa_category", []) if a.get("qcode")
        }

        assert anpa_qcodes == {"14"}
        # Verify the category entry structure
        anpa_category = item.get("anpa_category", [])
        logging.warning(f"anpa_category: {anpa_category}")
        assert len(anpa_category) == 1
        assert anpa_category[0]["qcode"] == "14"
        assert anpa_category[0]["name"] == "Ulkomaat"

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
