# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license
#

import unittest
from datetime import datetime

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
        for field in (
            "headline",
            "byline",
            "slugline",
            "description_text",
            "keywords",
            "ednote",
            "copyrightnotice",
        ):
            self.assertNotIn(field, item)

    def test_parse_meta_sets_firstcreated_from_date_and_time_tags(self):
        item = {}
        self.parser.parse_meta(
            item, {TAG.DATE_CREATED: "20230515", TAG.TIME_CREATED: "120000+0000"}
        )
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
