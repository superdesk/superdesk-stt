import json
import os
import unittest

import stt.stt_tt_new_parse_ninjs as stt_module
from stt.stt_tt_new_parse_ninjs import STTTTNEWNINJSFeedParser


class STTTTNEWNINJSFeedParserTest(unittest.TestCase):
    fixture = "json/stt_new_ninjs.json"

    def setUp(self):
        super().setUp()
        # Load JSON fixture following the same pattern as other test cases
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture_path = os.path.join(dirname, "fixtures", self.fixture)
        with open(fixture_path, "r", encoding="utf-8") as f:
            self.json_data = json.load(f)
        self.parser = STTTTNEWNINJSFeedParser()

    def test_transform_maps_metadata_and_cleans_associations(self):
        # Patch the base transform to return a predictable base item
        def fake_base_transform(self, ninjs):
            return {
                "headline": "Base Headline",
                "name": "Base Name",
                "associations": {"a001": {"type": "picture"}},
            }

        import unittest.mock

        with unittest.mock.patch.object(
            stt_module.NINJSFeedParser, "_transform_from_ninjs", fake_base_transform
        ):
            parser = self.parser
            ninjs = {
                "type": "text",
                "sector": "SPT",
                "department": "UTR",
                "urgency": "5",
                "headline": "My Headline",
                "originaltransmissionreference": "ext-123",
                "filename": "file.txt",
                "body_html5": "<figure><div class='byline'>Byline</div><span>Intro</span></figure>",
                "associations": {"a001": {"type": "picture"}},
            }

            item = parser._transform_from_ninjs(ninjs)

            self.assertTrue(parser.is_sport_item)
            self.assertEqual(item["source"], "TT")
            self.assertEqual(item["desk"], "Ulkomaat")
            self.assertEqual(item["extra"]["stt_meta"]["department_id"], 14)
            self.assertEqual(item["extra"]["stt_meta"]["department_name"], "Ulkomaat")
            self.assertEqual(item["extra"]["stt_meta"]["tt_department_code"], "UTR")
            # anpa_category should be populated from CV mapping (fallback name to map)
            self.assertIn("anpa_category", item)
            self.assertEqual(
                item["anpa_category"], [{"qcode": "ulkomaat", "name": "Ulkomaat"}]
            )
            self.assertEqual(item["priority"], 5)
            self.assertEqual(item["name"], "My Headline")
            self.assertEqual(item["external_id"], "ext-123")
            self.assertEqual(item["description_text"], "file.txt")
            self.assertNotIn("associations", item)
            self.assertNotIn("<html", item["body_html"])
            self.assertNotIn("<body", item["body_html"])
            self.assertIn('<p class="byline">Byline</p>', item["body_html"])
            self.assertIn("<p>Intro</p>", item["body_html"])

    def test_sanitise_html_normalizes_and_strips_containers(self):
        parser = self.parser
        html = "<figure><div class='byline'>By</div><span>Text</span></figure>"

        sanitized = parser.sanitise_stt_tt_html(html)

        self.assertEqual(sanitized, '<p class="byline">By</p><p>Text</p>')
        self.assertNotIn("<figure", sanitized)
        self.assertNotIn("<div", sanitized)
        self.assertNotIn("<span", sanitized)

    def test_datetime_converts_naive_and_aware_to_utc_iso(self):
        parser = self.parser

        # Naive datetime treated as Europe/Helsinki (UTC+3 in June)
        naive_input = "2024-06-01T10:00:00"
        naive_converted = parser.datetime(naive_input)
        self.assertEqual(naive_converted, "2024-06-01T07:00:00+00:00")

        # Aware datetime with +02:00 should normalize via Helsinki then to UTC
        aware_input = "2024-10-03T14:32:36+02:00"
        aware_converted = parser.datetime(aware_input)
        self.assertEqual(aware_converted, "2024-10-03T12:32:36+00:00")

    def test_can_parse_rejects_image_type(self):
        # Create a copy of the fixture data with image type
        data = self.json_data.copy()
        data["type"] = "image"

        # Write to a temporary file
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            json.dump(data, tmp_file)
            tmp_file.flush()

            self.assertFalse(self.parser.can_parse(tmp_file.name))

        # Clean up
        import os

        os.unlink(tmp_file.name)

    def test_department_defaults_on_unknown_or_missing(self):
        parser = self.parser

        # Missing
        dept_id, dept_name = parser._map_department(None)
        self.assertEqual((dept_id, dept_name), (3, "Kotimaa"))

        # Unknown
        dept_id, dept_name = parser._map_department("XYZ")
        self.assertEqual((dept_id, dept_name), (3, "Kotimaa"))

        # Known, case-insensitive
        dept_id, dept_name = parser._map_department("utr")
        self.assertEqual((dept_id, dept_name), (14, "Ulkomaat"))

    def test_sanitise_html_returns_stripped_when_inner_parse_fails(self):
        parser = self.parser
        html = "<html><head><title>x</title></head></html>"

        sanitized = parser.sanitise_stt_tt_html(html)

        self.assertEqual(sanitized, "")
