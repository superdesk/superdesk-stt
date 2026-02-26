import logging
import os
import tempfile
import asyncio
from datetime import datetime
from unittest.mock import patch

from tests import TestCase
from stt.io.feed_parsers.stt_events_csv_parse import EventsCSVFeedParser, _parse_dt

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class EventsCSVFeedParserTestCase(TestCase):
    fixture = "csv/eventsheet.csv"
    parser_class = EventsCSVFeedParser

    async def parse_source_content(self):
        """Override to handle CSV files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        provider = {"name": "Test"}
        async with self.ctx:
            parser = self.parser_class()
            items = await parser.parse(fixture, provider)
            self.item = items[0]

    def test_headline_and_metadata(self):
        """Test that headline and metadata are extracted correctly."""
        self.assertIn("name", self.item)
        self.assertEqual(self.item["type"], "event")
        self.assertEqual(self.item["original_source"], "CSV")
        self.assertEqual(self.item["pubstatus"], "usable")

    def test_dates_structure(self):
        """Test that dates are properly structured."""
        dates = self.item.get("dates", {})
        self.assertIn("start", dates)
        self.assertIn("end", dates)
        self.assertIsInstance(dates["start"], datetime)
        self.assertIsInstance(dates["end"], datetime)

    def test_extra_fields(self):
        """Test extra fields are properly set."""
        extra = self.item.get("extra", {})
        self.assertEqual(extra["stt_source"], "csv")
        self.assertIn("csv_row", extra)


class TestNoEndTimeFlag(TestCase):
    """Test the no_end_time configuration option."""

    # Set required attributes to avoid fixture parsing
    fixture = None
    parse_source = False
    parser_class = EventsCSVFeedParser

    def test_parse_dt_with_date_only(self):
        """Test what _parse_dt does with just a date string."""
        # Test parsing just a date
        result, _ = _parse_dt("2024-01-15", None, None)

        # Should be 00:00
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)

    def test_default_behavior_uses_end_time(self):
        """Test that default behavior uses end_time when available."""
        # Create a temporary CSV file
        csv_content = """start_date,start_time,end_date,end_time,name
2024-01-15,14:30,2024-01-15,16:45,Test Event"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            parser = self.parser_class()
            items = asyncio.run(parser.parse(temp_file, {"name": "Test"}))
            end = items[0]["dates"]["end"]
            self.assertEqual(end.hour, 16)
            self.assertEqual(end.minute, 45)
        finally:
            os.unlink(temp_file)


class TestEventsheet2Fixture(TestCase):
    """Regression tests for eventsheet-2 fixture parsing."""

    fixture = None
    parse_source = False
    parser_class = EventsCSVFeedParser

    def test_parse_eventsheet_2_all_rows_and_timestamps(self):
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", "csv", "eventsheet-2.csv")

        parser = self.parser_class()
        # Patch service lookup so this test validates CSV parsing behavior without
        # requiring app resource services (locations/contacts/vocabularies).
        with patch(
            "stt.io.feed_parsers.stt_events_csv_parse.get_resource_service"
        ) as mock_service:
            mock_service.return_value = None
            items = asyncio.run(parser.parse(fixture, {"name": "Test"}))

        # All data rows (excluding the format helper row) should be parsed.
        self.assertEqual(len(items), 24)

        by_name = {item["name"]: item for item in items}

        # Missing end_time should produce an all-day event.
        first = by_name["NHL: Detroit Red Wings - Winnipeg Jets"]
        self.assertEqual(first["dates"]["start"].hour, 1)
        self.assertEqual(first["dates"]["start"].minute, 30)
        self.assertTrue(first["dates"].get("all_day", False))
        self.assertEqual(
            int((first["dates"]["end"] - first["dates"]["start"]).total_seconds()),
            86400,
        )

        # DD/MM/YYYY should be parsed day-first for this fixture.
        feb_event = by_name["NHL: St. Louis Blues - Vegas Golden Knights"]
        self.assertEqual(feb_event["dates"]["start"].year, 2026)
        self.assertEqual(feb_event["dates"]["start"].month, 2)
        self.assertEqual(feb_event["dates"]["start"].day, 1)

    def test_flag_true_ignores_end_time_and_infers_from_start(self):
        """Test that no_end_time flag ignores time in end date."""
        # Create a temporary CSV file
        csv_content = """start_date,start_time,end_date,end_time,name
2024-01-15,14:30,2024-01-15,16:45,Test Event"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            parser = self.parser_class()
            items = asyncio.run(
                parser.parse(
                    temp_file, {"name": "Test", "config": {"no_end_time": True}}
                )
            )
            end = items[0]["dates"]["end"]
            # Expect 15:30 (start at 14:30 + 1h fallback)
            self.assertEqual(end.hour, 15)
            self.assertEqual(end.minute, 30)
        finally:
            os.unlink(temp_file)

    def test_flag_true_with_end_date_only(self):
        """Test no_end_time with only end_date (no end_time column)."""
        # Create a temporary CSV file
        csv_content = """start_date,start_time,end_date,name
2024-01-15,14:30,2024-01-16,Test Event"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            parser = self.parser_class()
            items = asyncio.run(
                parser.parse(
                    temp_file, {"name": "Test", "config": {"no_end_time": True}}
                )
            )
            end = items[0]["dates"]["end"]
            self.assertEqual(end.day, 16)  # January 16th
            self.assertEqual(end.hour, 0)
            self.assertEqual(end.minute, 0)
        finally:
            os.unlink(temp_file)

    def test_flag_defaults_to_false(self):
        """Test that no_end_time defaults to False when not specified."""
        # Create a temporary CSV file
        csv_content = """start_date,start_time,end_date,end_time,name
2024-01-15,14:30,2024-01-15,16:45,Test Event"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            parser = self.parser_class()

            # Test without config
            items1 = asyncio.run(parser.parse(temp_file, {"name": "Test"}))
            # Test with empty config
            items2 = asyncio.run(
                parser.parse(temp_file, {"name": "Test", "config": {}})
            )

            # Both should behave the same (include time)
            self.assertEqual(items1[0]["dates"]["end"].hour, 16)
            self.assertEqual(items2[0]["dates"]["end"].hour, 16)
        finally:
            os.unlink(temp_file)
