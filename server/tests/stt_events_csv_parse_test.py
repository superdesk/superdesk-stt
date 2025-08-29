import logging
import os
import tempfile
from datetime import datetime

from tests import TestCase
from stt.io.feed_parsers.stt_events_csv_parse import EventsCSVFeedParser, _parse_dt

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class EventsCSVFeedParserTestCase(TestCase):
    fixture = "csv/eventsheet.csv"
    parser_class = EventsCSVFeedParser

    def parse_source_content(self):
        """Override to handle CSV files instead of XML."""
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        provider = {"name": "Test"}
        with self.ctx:
            parser = self.parser_class()
            self.item = parser.parse(fixture, provider)[0]

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
        result = _parse_dt("2024-01-15", None, None)

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
            items = parser.parse(temp_file, {"name": "Test"})
            end = items[0]["dates"]["end"]
            self.assertEqual(end.hour, 16)
            self.assertEqual(end.minute, 45)
        finally:
            os.unlink(temp_file)

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
            items = parser.parse(
                temp_file, {"name": "Test", "config": {"no_end_time": True}}
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
            items = parser.parse(
                temp_file, {"name": "Test", "config": {"no_end_time": True}}
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
            items1 = parser.parse(temp_file, {"name": "Test"})
            # Test with empty config
            items2 = parser.parse(temp_file, {"name": "Test", "config": {}})

            # Both should behave the same (include time)
            self.assertEqual(items1[0]["dates"]["end"].hour, 16)
            self.assertEqual(items2[0]["dates"]["end"].hour, 16)
        finally:
            os.unlink(temp_file)
