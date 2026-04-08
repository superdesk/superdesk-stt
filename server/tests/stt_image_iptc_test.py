# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import io
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from superdesk.media.iim_codes import TAG

from stt.io.feed_parsers.stt_image_iptc import SttImageIPTCFeedParser


class SttImageIPTCFeedParserTest(unittest.TestCase):
    def setUp(self):
        self.parser = SttImageIPTCFeedParser()

    # ------------------------------------------------------------------
    # Registration / metadata
    # ------------------------------------------------------------------

    def test_parser_name(self):
        self.assertEqual(self.parser.NAME, "stt_image_iptc")

    def test_parser_label(self):
        self.assertEqual(self.parser.label, "STT Image (IPTC metadata)")

    # ------------------------------------------------------------------
    # can_parse
    # ------------------------------------------------------------------

    def test_can_parse_jpeg(self):
        self.assertTrue(self.parser.can_parse("/path/to/photo.jpg"))
        self.assertTrue(self.parser.can_parse("/path/to/photo.jpeg"))

    def test_cannot_parse_non_jpeg(self):
        self.assertFalse(self.parser.can_parse("/path/to/photo.png"))
        self.assertFalse(self.parser.can_parse("/path/to/photo.gif"))
        self.assertFalse(self.parser.can_parse("/path/to/photo.tiff"))
        self.assertFalse(self.parser.can_parse("/path/to/document.xml"))

    def test_cannot_parse_non_string(self):
        self.assertFalse(self.parser.can_parse(None))
        self.assertFalse(self.parser.can_parse(42))
        self.assertFalse(self.parser.can_parse(b"/path/to/photo.jpg"))

    # ------------------------------------------------------------------
    # parse_date_time
    # ------------------------------------------------------------------

    def test_parse_date_time_valid(self):
        result = self.parser.parse_date_time("20230515", "120000+0000")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2023)
        self.assertEqual(result.month, 5)
        self.assertEqual(result.day, 15)
        self.assertEqual(result.hour, 12)

    def test_parse_date_time_missing_date(self):
        self.assertIsNone(self.parser.parse_date_time(None, "120000+0000"))

    def test_parse_date_time_missing_time(self):
        self.assertIsNone(self.parser.parse_date_time("20230515", None))

    def test_parse_date_time_both_missing(self):
        self.assertIsNone(self.parser.parse_date_time(None, None))

    def test_parse_date_time_invalid_returns_none(self):
        self.assertIsNone(self.parser.parse_date_time("not-a-date", "not-a-time"))

    # ------------------------------------------------------------------
    # parse_meta — field mapping
    # ------------------------------------------------------------------

    def test_parse_meta_maps_all_iptc_fields(self):
        item = {}
        metadata = {
            TAG.HEADLINE: "Test Headline",
            TAG.BY_LINE: "Jane Doe",
            TAG.OBJECT_NAME: "test-slug",
            TAG.CAPTION_ABSTRACT: "A test caption",
            TAG.KEYWORDS: ["kw1", "kw2"],
            TAG.SPECIAL_INSTRUCTIONS: "Handle with care",
            TAG.COPYRIGHT_NOTICE: "© 2025 STT",
        }
        self.parser.parse_meta(item, metadata)
        self.assertEqual(item["headline"], "Test Headline")
        self.assertEqual(item["byline"], "Jane Doe")
        self.assertEqual(item["slugline"], "test-slug")
        self.assertEqual(item["description_text"], "A test caption")
        self.assertEqual(item["keywords"], ["kw1", "kw2"])
        self.assertEqual(item["ednote"], "Handle with care")
        self.assertEqual(item["copyrightnotice"], "© 2025 STT")

    def test_parse_meta_keywords_string_wrapped_in_list(self):
        """A single keyword string must be normalised to a one-element list."""
        item = {}
        self.parser.parse_meta(item, {TAG.KEYWORDS: "single-keyword"})
        self.assertEqual(item["keywords"], ["single-keyword"])

    def test_parse_meta_missing_keys_are_skipped(self):
        """Absent IPTC tags must not create keys in the item dict."""
        item = {}
        self.parser.parse_meta(item, {})
        for field in ("headline", "byline", "slugline", "description_text", "keywords", "ednote", "copyrightnotice"):
            self.assertNotIn(field, item)

    def test_parse_meta_sets_firstcreated_from_date_and_time_tags(self):
        item = {}
        self.parser.parse_meta(item, {TAG.DATE_CREATED: "20230515", TAG.TIME_CREATED: "120000+0000"})
        self.assertIn("firstcreated", item)
        self.assertEqual(item["firstcreated"].year, 2023)
        self.assertEqual(item["firstcreated"].month, 5)
        self.assertEqual(item["firstcreated"].day, 15)

    def test_parse_meta_no_firstcreated_when_date_missing(self):
        item = {}
        self.parser.parse_meta(item, {TAG.TIME_CREATED: "120000+0000"})
        self.assertNotIn("firstcreated", item)

    # ------------------------------------------------------------------
    # STT-specific: assignment_id must NOT be mapped
    # ------------------------------------------------------------------

    def test_assignment_id_not_mapped(self):
        """TAG.ORIGINAL_TRANSMISSION_REFERENCE is commented out in the STT parser
        and must never populate assignment_id on the item."""
        item = {}
        self.parser.parse_meta(item, {TAG.ORIGINAL_TRANSMISSION_REFERENCE: "REF-12345"})
        self.assertNotIn("assignment_id", item)

    def test_parse_meta_returns_item(self):
        item = {}
        result = self.parser.parse_meta(item, {TAG.HEADLINE: "Returned"})
        self.assertIs(result, item)

    def test_parse_meta_partial_fields(self):
        """Only the provided tags must be set; others must remain absent."""
        item = {}
        self.parser.parse_meta(item, {TAG.HEADLINE: "Only Headline"})
        self.assertEqual(item["headline"], "Only Headline")
        self.assertNotIn("byline", item)
        self.assertNotIn("slugline", item)

    def test_parse_meta_keywords_list_unchanged(self):
        """A keywords list must not be double-wrapped."""
        item = {}
        self.parser.parse_meta(item, {TAG.KEYWORDS: ["a", "b", "c"]})
        self.assertEqual(item["keywords"], ["a", "b", "c"])

    # ------------------------------------------------------------------
    # parse_date_time — edge cases
    # ------------------------------------------------------------------

    def test_parse_date_time_empty_string_date_returns_none(self):
        self.assertIsNone(self.parser.parse_date_time("", "120000+0000"))

    def test_parse_date_time_empty_string_time_returns_none(self):
        self.assertIsNone(self.parser.parse_date_time("20230515", ""))

    def test_parse_date_time_arrow_fallback_returns_none(self):
        """When strptime fails the arrow branch is tried; if it also fails, None is returned."""
        self.assertIsNone(self.parser.parse_date_time("totally", "invalid"))

    def test_parse_date_time_preserves_timezone(self):
        result = self.parser.parse_date_time("20230515", "120000+0300")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)

    # ------------------------------------------------------------------
    # can_parse — edge cases
    # ------------------------------------------------------------------

    def test_cannot_parse_no_extension(self):
        self.assertFalse(self.parser.can_parse("/path/to/imagefile"))

    def test_cannot_parse_empty_string(self):
        self.assertFalse(self.parser.can_parse(""))

    # ------------------------------------------------------------------
    # ALLOWED_EXT
    # ------------------------------------------------------------------

    def test_allowed_ext_includes_jpeg_extensions(self):
        for ext in (".jpg", ".jpeg"):
            self.assertIn(ext, self.parser.ALLOWED_EXT)


class SttImageIPTCGetMetadataTest(unittest.TestCase):
    """Tests for _get_iptc_metadata — charset-aware IPTC decoding."""

    # IIM record/tag codes used in assertions
    _HEADLINE = (2, 105)
    _CAPTION = (2, 120)
    _BYLINE = (2, 80)
    _KEYWORDS = (2, 25)
    _CHARSET = (1, 90)

    def setUp(self):
        self.parser = SttImageIPTCFeedParser()
        self.stream = io.BytesIO(b"fake-jpeg-bytes")

    def _run_with_iptc(self, iptc_dict):
        """Call _get_iptc_metadata with a mocked IPTC payload."""
        with patch("stt.io.feed_parsers.stt_image_iptc.Image") as mock_image, \
             patch("stt.io.feed_parsers.stt_image_iptc.IptcImagePlugin") as mock_plugin:
            mock_plugin.getiptcinfo.return_value = iptc_dict
            return self.parser._get_iptc_metadata(self.stream)

    # ------------------------------------------------------------------
    # Empty / missing IPTC block
    # ------------------------------------------------------------------

    def test_returns_empty_dict_when_no_iptc(self):
        """getiptcinfo returning None must yield an empty metadata dict."""
        self.assertEqual(self._run_with_iptc(None), {})

    def test_returns_empty_dict_when_iptc_empty(self):
        """An empty IPTC block must yield an empty metadata dict."""
        self.assertEqual(self._run_with_iptc({}), {})

    # ------------------------------------------------------------------
    # Default encoding: CP1252
    # ------------------------------------------------------------------

    def test_nordic_characters_decoded_without_charset_tag(self):
        """ä ö å Ä Ö Å must decode correctly when no charset tag is present."""
        iptc = {self._HEADLINE: "Pääministeri".encode("cp1252")}
        result = self._run_with_iptc(iptc)
        self.assertEqual(result[TAG.HEADLINE], "Pääministeri")

    def test_cp1252_typographic_characters_not_dropped(self):
        """En-dash (0x96) and curly quotes (0x93/0x94) must survive decoding.

        These bytes are printable in CP1252 but invisible C1 control codes in
        Latin-1, which was the regression: they were silently dropped.
        """
        # mirrors the real caption: – "Hyvä matsi saatiin"
        raw = " \x96 \x93Hyv\xe4 matsi saatiin\x94".encode("cp1252")
        result = self._run_with_iptc({self._CAPTION: raw})
        caption = result[TAG.CAPTION_ABSTRACT]
        self.assertIn("–", caption)   # en-dash  0x96
        self.assertIn("\u201c", caption)  # left curly quote  0x93
        self.assertIn("\u201d", caption)  # right curly quote 0x94
        self.assertIn("Hyvä", caption)

    def test_full_range_of_nordic_letters(self):
        """All six Nordic letters must round-trip through the default CP1252 path."""
        nordic = "äöåÄÖÅ"
        iptc = {self._BYLINE: nordic.encode("cp1252")}
        result = self._run_with_iptc(iptc)
        self.assertEqual(result[TAG.BY_LINE], nordic)

    # ------------------------------------------------------------------
    # Explicit UTF-8 charset tag
    # ------------------------------------------------------------------

    def test_utf8_used_when_charset_tag_declares_utf8(self):
        """Record 1 Tag 90 containing ESC % G must switch decoding to UTF-8."""
        iptc = {
            self._CHARSET: b"\x1b%G",
            self._HEADLINE: "Pääministeri".encode("utf-8"),
        }
        result = self._run_with_iptc(iptc)
        self.assertEqual(result[TAG.HEADLINE], "Pääministeri")

    def test_utf8_marker_detected_when_embedded_in_longer_value(self):
        """ESC % G must be recognised even when surrounded by other bytes."""
        iptc = {
            self._CHARSET: b"\x1b\x28\x42\x1b%G",  # extra escape before marker
            self._HEADLINE: "Pääministeri".encode("utf-8"),
        }
        result = self._run_with_iptc(iptc)
        self.assertEqual(result[TAG.HEADLINE], "Pääministeri")

    def test_cp1252_used_when_charset_tag_absent(self):
        """Absence of the charset tag must result in CP1252 decoding, not UTF-8."""
        # 0xe4 0xe4 is valid CP1252 (ää) but invalid UTF-8
        iptc = {self._HEADLINE: b"P\xe4\xe4ministeri"}
        result = self._run_with_iptc(iptc)
        self.assertEqual(result[TAG.HEADLINE], "Pääministeri")

    # ------------------------------------------------------------------
    # Tag filtering
    # ------------------------------------------------------------------

    def test_unknown_tag_codes_are_skipped(self):
        """Codes absent from iim_codes must be silently ignored."""
        iptc = {
            (9, 99): b"should be ignored",
            self._HEADLINE: b"Known",
        }
        result = self._run_with_iptc(iptc)
        self.assertEqual(list(result.keys()), [TAG.HEADLINE])

    def test_charset_tag_not_present_in_returned_metadata(self):
        """Record 1 Tag 90 is a control field and must not appear in the output."""
        iptc = {
            self._CHARSET: b"\x1b%G",
            self._HEADLINE: "Otsikko".encode("utf-8"),
        }
        result = self._run_with_iptc(iptc)
        # The charset tag name would be absent from iim_codes; verify it didn't
        # sneak in under any key
        self.assertNotIn((1, 90), result)
        self.assertEqual(len(result), 1)

    # ------------------------------------------------------------------
    # Multi-value fields (e.g. Keywords)
    # ------------------------------------------------------------------

    def test_list_values_each_element_decoded(self):
        """Multi-value IPTC fields must have every byte element decoded."""
        iptc = {self._KEYWORDS: [b"ravit", "talvi\xe4".encode("cp1252")]}
        result = self._run_with_iptc(iptc)
        self.assertEqual(result[TAG.KEYWORDS], ["ravit", "talviä"])

    def test_list_values_non_bytes_elements_passed_through(self):
        """Non-bytes items inside a list field must be kept as-is."""
        iptc = {self._KEYWORDS: [b"bytes-kw", "already-str"]}
        result = self._run_with_iptc(iptc)
        self.assertIn("bytes-kw", result[TAG.KEYWORDS])
        self.assertIn("already-str", result[TAG.KEYWORDS])
