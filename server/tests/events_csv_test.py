import os

from stt.io.feed_parsers.stt_events_csv_parse import EventsCSVFeedParser


def test_parse_valid_row_builds_event_with_tz_and_end_default(tmp_path):
    parser = EventsCSVFeedParser()
    p = tmp_path / "events.csv"
    p.write_text(
        "Start Date,Start Time,Event Name,Timezone,Slugline\n"
        "2024-07-01,14:30,  Summer Fair  ,America/New_York,  slug  \n",
        encoding="utf-8",
    )

    items = parser.parse(str(p))
    assert len(items) == 1
    ev = items[0]

    assert ev["name"] == "Summer Fair"
    assert ev["slugline"] == "slug"
    assert ev["dates"]["tz"] == "America/New_York"
    assert ev["dates"]["start"].isoformat().startswith("2024-07-01T14:30:00")
    assert ev["dates"]["start"].isoformat().endswith("-04:00")
    # End time should be 1 hour after start time when no end time is provided
    from datetime import timedelta

    expected_end = ev["dates"]["start"] + timedelta(hours=1)
    assert ev["dates"]["end"] == expected_end


def test_can_parse_and_sniff_delimiters_csv_tsv(tmp_path):
    parser = EventsCSVFeedParser()

    comma = tmp_path / "comma.csv"
    comma.write_text(
        "Start Date,Event Name\n" "2024-01-01,One\n",
        encoding="utf-8",
    )

    semicolon = tmp_path / "semi.csv"
    semicolon.write_text(
        "Start Date;Event Name\n" "2024-01-02;Two\n",
        encoding="utf-8",
    )

    tabbed = tmp_path / "file.tsv"
    tabbed.write_text(
        "Start Date\tEvent Name\n" "2024-01-03\tThree\n",
        encoding="utf-8",
    )

    assert parser.can_parse(str(comma)) is True
    assert parser.can_parse(str(tabbed)) is False  # only .csv is accepted

    items1 = parser.parse(str(comma))
    assert len(items1) == 1 and items1[0]["name"] == "One"

    items2 = parser.parse(str(semicolon))
    assert len(items2) == 1 and items2[0]["name"] == "Two"

    items3 = parser.parse(str(tabbed))
    assert len(items3) == 1 and items3[0]["name"] == "Three"


def test_builds_links_calendars_location_contact(tmp_path):
    parser = EventsCSVFeedParser()
    p = tmp_path / "rich.csv"
    p.write_text(
        "Start Date,Event Name,External Links,External link 2,Calendars,"
        "Location Name,Location Address,Location City/Town,Location State/Province/Region,Location Country,"
        "Contact Honorific,Contact First Name,Contact Last Name,Contact Organisation,Contact Point of Contact,"
        "Contact Email,Contact Phone Number,Contact Phone Usage,Contact Phone Public\n"
        "2024-05-05,Sample,http://a.com, http://b.com ,cal1; cal2,"
        "Venue,123 St,Metropolis,State,US,"
        "Dr,Jane,Doe,Org,POC,jane@org.com,123456,work,y\n",
        encoding="utf-8",
    )

    items = parser.parse(str(p))
    assert len(items) == 1
    ev = items[0]

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
    parser = EventsCSVFeedParser()
    p = tmp_path / "missing.csv"
    p.write_text(
        "Start Date,Event Name\n"
        ",HasNameButNoStart\n"
        "2024-01-01,\n"
        "2024-01-02,   \n"
        "2024-01-03,Valid\n",
        encoding="utf-8",
    )

    items = parser.parse(str(p))
    assert len(items) == 1
    assert items[0]["name"] == "Valid"
    assert items[0]["dates"]["start"].isoformat().startswith("2024-01-03")


def test_invalid_start_skips_and_invalid_end_falls_back(tmp_path):
    parser = EventsCSVFeedParser()
    p = tmp_path / "invalid_dates.csv"
    p.write_text(
        "Start Date,Start Time,End Date,End Time,Event Name,Timezone\n"
        "not a date,10:00,2024-01-02,11:00,Bad,UTC\n"
        "2024-02-03,10:00,nope,12:00,Good,UTC\n",
        encoding="utf-8",
    )

    items = parser.parse(str(p))
    assert len(items) == 1
    ev = items[0]
    assert ev["name"] == "Good"
    assert ev["dates"]["start"].isoformat().startswith("2024-02-03T10:00:00")
    assert ev["dates"]["start"].isoformat().endswith("+00:00")
    # End time should be 1 hour after start time when no end time is provided
    from datetime import timedelta

    expected_end = ev["dates"]["start"] + timedelta(hours=1)
    assert ev["dates"]["end"] == expected_end


def test_preserves_existing_timezone_when_tz_hint_provided(tmp_path):
    parser = EventsCSVFeedParser()
    p = tmp_path / "tz.csv"
    # Embed -05:00 in the start value while providing a tz hint that should not override it
    p.write_text(
        "Start Date,Event Name,Timezone\n"
        "2024-03-10 01:30 -05:00,HasTZ,Europe/Paris\n",
        encoding="utf-8",
    )

    items = parser.parse(str(p))
    assert len(items) == 1
    ev = items[0]
    assert ev["dates"]["tz"] == "Europe/Paris"
    assert ev["dates"]["start"].isoformat().startswith("2024-03-10T01:30:00")
    assert ev["dates"]["start"].isoformat().endswith("-05:00")


def test_parse_eventsheet_fixture_csv():
    """Parse the real fixture at server/tests/fixtures/csv/eventsheet.csv.

    This mirrors how other parsers' tests load fixtures (e.g. BusinessWire),
    using a stable path under tests/fixtures.
    """
    parser = EventsCSVFeedParser()
    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "csv", "eventsheet.csv"
    )

    items = parser.parse(fixture_path)

    # Basic structure assertions
    assert isinstance(items, list)
    assert len(items) > 0

    first = items[0]
    assert first.get("original_source") == "CSV"
    assert first.get("type") == "event"
    assert first.get("name")  # non-empty
    assert "dates" in first and first["dates"].get("start")

    # Calendars column should map to list of qcodes when present
    # Fixture has values like "Urheilu" in the Calendars column
    if first.get("calendars"):
        assert isinstance(first["calendars"], list)
        assert all("qcode" in c for c in first["calendars"])
