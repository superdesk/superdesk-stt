import json
import os
from tests import TestCase
from stt.stt_json_event_formatter import STTJsonEventFormatter


class STTJsonEventFormatterTest(TestCase):
    add_stt_cvs = True
    parse_source = False
    fixture = "json/stt_json_event_item.json"

    def get_sample_item(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", self.fixture)
        with open(fixture_path, "r") as f:
            return json.load(f)

    async def test_map_calendar_output_with_categories(self):
        async with self.app.app_context():
            formatter = STTJsonEventFormatter()
            item = self.get_sample_item()

            formatter.map_calendar_output(item)

            calendars = item["calendars"]
            self.assertGreater(len(calendars), 0)

            # Should have Muut kuin urheilu for non-sport category
            has_non_sport_category = any(
                calendar["name"] == "Muut kuin urheilu" for calendar in calendars
            )
            self.assertTrue(has_non_sport_category)

    async def test_map_calendar_output_no_categories(self):
        async with self.app.app_context():
            formatter = STTJsonEventFormatter()
            item = self.get_sample_item()
            item["anpa_category"] = []

            formatter.map_calendar_output(item)
            self.assertEqual(item["calendars"], [])

    async def test_map_calendar_output_sport_only(self):
        async with self.app.app_context():
            formatter = STTJsonEventFormatter()
            item = self.get_sample_item()
            item["anpa_category"] = [{"name": "Urheilu", "qcode": "16", "scheme": None}]

            formatter.map_calendar_output(item)

            has_non_sport_category = any(
                calendar["name"] == "Muut kuin urheilu"
                for calendar in item["calendars"]
            )
            self.assertFalse(has_non_sport_category)
