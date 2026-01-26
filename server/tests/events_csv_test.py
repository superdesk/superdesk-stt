import os
import asyncio
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from stt.io.feed_parsers.stt_events_csv_parse import EventsCSVFeedParser
from settings import DEFAULT_TIMEZONE


# === Shared helpers for occurrence status tests ===
@contextmanager
def mock_eventoccurstatus(items):
    """Patch the vocab service to return `items` for eventoccurstatus."""
    with patch(
        "stt.io.feed_parsers.stt_events_csv_parse.get_resource_service"
    ) as get_service:
        mock = MagicMock()
        mock.get_items.return_value = items
        get_service.return_value = mock
        yield


def write(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return str(p)


def parse_file(path):
    parser = EventsCSVFeedParser()
    return asyncio.run(parser.parse(path))


def create_csv_file(tmp_path, filename, headers, rows):
    """Create a CSV file with given headers and rows."""
    content = ",".join(headers) + "\n"
    for row in rows:
        content += ",".join(str(cell) for cell in row) + "\n"
    return write(tmp_path, filename, content)


def create_parser():
    """Create a new EventsCSVFeedParser instance."""
    return EventsCSVFeedParser()


def parse_csv_content(tmp_path, headers, rows, filename="test.csv"):
    """Helper to create CSV file and parse it in one step."""
    path = create_csv_file(tmp_path, filename, headers, rows)
    return parse_file(path)


def assert_event_basic_structure(event, expected_name=None, expected_source="CSV"):
    """Assert basic event structure and properties."""
    assert event.get("original_source") == expected_source
    assert event.get("type") == "event"
    assert "dates" in event
    assert event["dates"].get("start")
    if expected_name:
        assert event.get("name") == expected_name


def assert_event_dates(event, expected_start_date=None, expected_tz=None, has_end=True):
    """Assert event date properties."""
    dates = event["dates"]
    if expected_start_date:
        assert dates["start"].isoformat().startswith(expected_start_date)
    if expected_tz:
        assert dates["tz"] == expected_tz
    if has_end:
        assert "end" in dates and dates["end"]


def assert_single_event_parsed(items, expected_name=None):
    """Assert that exactly one event was parsed."""
    assert len(items) == 1
    if expected_name:
        assert items[0]["name"] == expected_name
    return items[0]


def parse_occur_status_csv(tmp_path, occurrence_status_value, vocab_items=None):
    """Helper to test occurrence status parsing with mocked vocabulary."""
    headers = ["Start Date", "Event Name", "Occurrence Status"]
    rows = [["2024-01-01", "Test Event", occurrence_status_value]]

    if vocab_items is None:
        vocab_items = [
            {
                "is_active": True,
                "qcode": "eocstat:eos5",
                "name": "Planned, occurs certainly",
                "label": "Planned, occurs certainly",
            }
        ]

    with mock_eventoccurstatus(vocab_items):
        return parse_csv_content(tmp_path, headers, rows)


def assert_eos5(event):
    assert "occur_status" in event
    os5 = event["occur_status"]
    assert os5["qcode"] == "eocstat:eos5"
    assert os5["name"] == "Planned, occurs certainly"
    assert os5["label"] == "Planned, occurs certainly"
    assert len(os5) == 3


def assert_no_occur_status(event):
    assert "occur_status" not in event or event["occur_status"] is None


def test_parse_valid_row_builds_event_with_tz_and_end_default(tmp_path):
    headers = ["Start Date", "Start Time", "Event Name", "Timezone", "Slugline"]
    rows = [["2024-07-01", "14:30", "  Summer Fair  ", "America/New_York", "  slug  "]]

    with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
        items = parse_csv_content(tmp_path, headers, rows)
    ev = assert_single_event_parsed(items, "Summer Fair")

    assert ev["slugline"] == "slug"
    assert_event_dates(ev, "2024-07-01T14:30:00", "America/New_York")
    assert ev["dates"]["start"].isoformat().endswith("-04:00")

    assert ev["dates"].get("all_day") is True

    # Missing end time => all day event
    from datetime import timedelta

    expected_end = ev["dates"]["start"] + timedelta(days=1)
    assert ev["dates"]["end"] == expected_end


def test_can_parse_and_sniff_delimiters_csv_tsv(tmp_path):
    parser = create_parser()

    # Create files with different delimiters manually since create_csv_file uses commas
    comma_path = write(tmp_path, "comma.csv", "Start Date,Event Name\n2024-01-01,One\n")
    semi_path = write(tmp_path, "semi.csv", "Start Date;Event Name\n2024-01-02;Two\n")
    tab_path = write(
        tmp_path, "file.tsv", "Start Date\tEvent Name\n2024-01-03\tThree\n"
    )

    assert parser.can_parse(comma_path) is True
    assert parser.can_parse(tab_path) is False  # only .csv is accepted

    items1 = parse_file(comma_path)
    assert_single_event_parsed(items1, "One")

    items2 = parse_file(semi_path)
    assert_single_event_parsed(items2, "Two")

    items3 = parse_file(tab_path)
    assert_single_event_parsed(items3, "Three")


def test_builds_links_calendars_location_contact(tmp_path):
    headers = [
        "Start Date",
        "Event Name",
        "External Links",
        "External link 2",
        "Calendars",
        "Location Name",
        "Location Address",
        "Location City/Town",
        "Location State/Province/Region",
        "Location Country",
        "Contact Honorific",
        "Contact First Name",
        "Contact Last Name",
        "Contact Organisation",
        "Contact Point of Contact",
        "Contact Email",
        "Contact Phone Number",
        "Contact Phone Usage",
        "Contact Phone Public",
    ]
    rows = [
        [
            "2024-05-05",
            "Sample",
            "http://a.com",
            " http://b.com ",
            "cal1; cal2",
            "Venue",
            "123 St",
            "Metropolis",
            "State",
            "US",
            "Dr",
            "Jane",
            "Doe",
            "Org",
            "POC",
            "jane@org.com",
            "123456",
            "work",
            "y",
        ]
    ]

    items = parse_csv_content(tmp_path, headers, rows)
    ev = assert_single_event_parsed(items, "Sample")

    assert ev["links"] == [{"href": "http://a.com"}, {"href": "http://b.com"}]
    assert ev["calendars"] == [{"qcode": "cal1"}, {"qcode": "cal2"}]

    assert (
        "location" in ev
        and isinstance(ev["location"], list)
        and len(ev["location"]) == 1
    )
    loc = ev["location"][0]
    assert loc["name"] == "Venue"
    assert loc["address"] == {
        "line": ["123 St"],
        "locality": "Metropolis",
        "area": "State",
        "country": "US",
    }

    assert "event_contact_info" in ev and len(ev["event_contact_info"]) == 1
    assert (
        ev["event_contact_info"][0]
        == "Dr Jane Doe | Org | POC | jane@org.com | 123456 (work) | public"
    )


def test_skips_row_when_required_fields_missing(tmp_path):
    headers = ["Start Date", "Event Name"]
    rows = [
        ["", "HasNameButNoStart"],
        ["2024-01-01", ""],
        ["2024-01-02", "   "],
        ["2024-01-03", "Valid"],
    ]

    with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
        items = parse_csv_content(tmp_path, headers, rows)
    ev = assert_single_event_parsed(items, "Valid")
    assert_event_dates(ev, "2024-01-03")


def test_invalid_start_skips_and_invalid_end_falls_back(tmp_path):
    headers = [
        "Start Date",
        "Start Time",
        "End Date",
        "End Time",
        "Event Name",
        "Timezone",
    ]
    rows = [
        ["not a date", "10:00", "2024-01-02", "11:00", "Bad", "UTC"],
        ["2024-02-03", "10:00", "nope", "12:00", "Good", "UTC"],
    ]

    with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
        items = parse_csv_content(tmp_path, headers, rows)
    ev = assert_single_event_parsed(items, "Good")
    assert_event_dates(ev, "2024-02-03T10:00:00", "UTC")
    assert ev["dates"]["start"].isoformat().endswith("+00:00")

    # End time should be 1 hour after start time when no end time is provided
    from datetime import timedelta

    expected_end = ev["dates"]["start"] + timedelta(hours=1)
    assert ev["dates"]["end"] == expected_end


def test_default_timezone_applied_when_missing(tmp_path):
    headers = ["Start Date", "Start Time", "Event Name"]
    rows = [["2024-01-01", "12:00", "Default TZ"]]

    items = parse_csv_content(tmp_path, headers, rows)
    ev = assert_single_event_parsed(items, "Default TZ")

    assert_event_dates(ev, "2024-01-01T12:00:00", DEFAULT_TIMEZONE)
    assert ev["dates"]["start"].isoformat().endswith("+02:00")


def test_locale_dayfirst_parsing(tmp_path):
    headers = ["Start Date", "Start Time", "Event Name"]
    rows = [["01/02/2026", "10:00", "Locale Date"]]

    with patch("locale.getlocale", return_value=("fi_FI", "UTF-8")):
        items = parse_csv_content(tmp_path, headers, rows)

    ev = assert_single_event_parsed(items, "Locale Date")
    assert_event_dates(ev, "2026-02-01T10:00:00")


def test_preserves_existing_timezone_when_tz_hint_provided(tmp_path):
    headers = ["Start Date", "Event Name", "Timezone"]
    rows = [["2024-03-10 01:30 -05:00", "HasTZ", "Europe/Paris"]]

    with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
        items = parse_csv_content(tmp_path, headers, rows)
    ev = assert_single_event_parsed(items, "HasTZ")
    assert_event_dates(ev, "2024-03-10T01:30:00", "Europe/Paris")
    assert ev["dates"]["start"].isoformat().endswith("-05:00")


def test_parse_eventsheet_fixture_csv():
    """Parse the real fixture at server/tests/fixtures/csv/eventsheet.csv.

    This mirrors how other parsers' tests load fixtures (e.g. BusinessWire),
    using a stable path under tests/fixtures.
    """
    from unittest.mock import patch

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "csv", "eventsheet.csv"
    )

    # Mock get_resource_service to return None (simulating no app context)
    with patch(
        "stt.io.feed_parsers.stt_events_csv_parse.get_resource_service"
    ) as mock_service:
        mock_service.return_value = None
        items = parse_file(fixture_path)

    # Basic structure assertions
    assert isinstance(items, list)
    assert len(items) > 0

    first = items[0]
    assert_event_basic_structure(first)

    # Calendars column should map to list of qcodes when present
    # Fixture has values like "Urheilu" in the Calendars column
    if first.get("calendars"):
        assert isinstance(first["calendars"], list)
        assert all("qcode" in c for c in first["calendars"])


def test_build_occur_status_with_valid_qcode(tmp_path):
    """Test _build_occur_status with a valid qcode that matches vocabulary."""
    vocab_items = [
        {
            "is_active": True,
            "qcode": "eocstat:eos5",
            "name": "Planned, occurs certainly",
            "label": "Planned, occurs certainly",
        },
        {
            "is_active": True,
            "qcode": "eocstat:eos3",
            "name": "Planned, may not occur",
            "label": "Planned, may not occur",
        },
    ]

    items = parse_occur_status_csv(tmp_path, "eocstat:eos5", vocab_items)
    ev = assert_single_event_parsed(items, "Test Event")
    assert_eos5(ev)


def test_build_occur_status_with_label_match(tmp_path):
    """Test _build_occur_status matching by exact label/name instead of qcode."""
    items = parse_occur_status_csv(tmp_path, '"Planned, occurs certainly"')
    ev = assert_single_event_parsed(items, "Test Event")
    assert_eos5(ev)


def test_build_occur_status_with_no_exact_match_fallback(tmp_path):
    """Test _build_occur_status fallback when no exact match exists."""
    items = parse_occur_status_csv(tmp_path, "Planned")
    ev = assert_single_event_parsed(items, "Test Event")
    assert_no_occur_status(ev)


def test_build_occur_status_fallback_when_no_vocabulary_match(tmp_path):
    """Test _build_occur_status fallback when vocabulary lookup fails."""
    items = parse_occur_status_csv(tmp_path, "unknown_status", vocab_items=[])
    ev = assert_single_event_parsed(items, "Test Event")
    assert_no_occur_status(ev)


def test_build_occur_status_with_empty_or_missing_status(tmp_path):
    """Test _build_occur_status when occur_status is empty or missing."""
    headers = ["Start Date", "Event Name", "Occurrence Status"]
    rows = [["2024-01-01", "Test Event", ""], ["2024-01-02", "Test Event 2", "   "]]

    items = parse_csv_content(tmp_path, headers, rows)
    assert len(items) == 2

    # Both events should not have occur_status when it's empty/whitespace
    for event in items:
        assert_no_occur_status(event)


def test_build_occur_status_case_insensitive_matching(tmp_path):
    """Test _build_occur_status performs case-insensitive matching."""
    headers = ["Start Date", "Event Name", "Occurrence Status"]
    rows = [
        ["2024-01-01", "Test Event", "EOCSTAT:EOS5"],
        ["2024-01-02", "Test Event 2", '"PLANNED, OCCURS CERTAINLY"'],
    ]

    with mock_eventoccurstatus(
        [
            {
                "is_active": True,
                "qcode": "eocstat:eos5",
                "name": "Planned, occurs certainly",
                "label": "Planned, occurs certainly",
            }
        ]
    ):
        items = parse_csv_content(tmp_path, headers, rows)
        assert len(items) == 2
        assert_eos5(items[0])
        assert_eos5(items[1])


def test_build_occur_status_ignores_inactive_items(tmp_path):
    vocab_items = [
        {
            "is_active": False,
            "qcode": "eocstat:eos5",
            "name": "Planned, occurs certainly",
            "label": "Planned, occurs certainly",
        }
    ]

    items = parse_occur_status_csv(tmp_path, "eocstat:eos5", vocab_items)
    ev = assert_single_event_parsed(items, "Test Event")
    assert_no_occur_status(ev)
