###############################################################################
# Copyright (C) 2023-2024 Id Solution / Superdesk / contributors
#
# Licensed under the terms of the GNU Affero General Public License version 3.
# See LICENSE or <https://www.gnu.org/licenses/agpl-3.0.html> for details.
#
# Generic, maintainable CSV → Superdesk Events parser (STT flavor).
# - Order-independent headers (case/space-insensitive), with aliases.
# - Required columns: Start date, Event name. Rows missing either are skipped.
# - Separate date/time columns merged; end defaults to start if missing.
# - Timezone applied if present; otherwise timestamps remain naive.
# - Supports multi-value fields via comma/semicolon lists.
# - Builds minimal, schema-friendly event dict without over-coupling.
# This module is intentionally small & readable. Helpers are pure functions
# and unit-test friendly. Lines and branching are kept shallow for flake8.
###############################################################################

from __future__ import annotations


import csv
import io
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from dateutil import parser as dtparse, tz

from superdesk.io.feed_parsers import FeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.metadata.utils import generate_tag_from_url
from superdesk import get_resource_service
from bson import ObjectId
import logging


logger = logging.getLogger(__name__)

# ---- Constants & regex -----------------------------------------------------

TRUEY = {"1", "y", "yes", "true", "t", "x"}
EXTERNAL_LINK_COL_RE = re.compile(r"^external\s*links?", re.I)

# ---- Small utilities -------------------------------------------------------



def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", value)
    return value.strip("_").lower()


def _str2bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    return s in TRUEY


def _norm(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_dt(
    date_str: Optional[str], time_str: Optional[str], tz_name: Optional[str]
) -> Optional[datetime]:
    """Parse flexible date/time strings. If tz_name provided and parsed value is
    naive, apply that timezone. Returns datetime object or None on failure.
    """
    date_str = _norm(date_str)
    time_str = _norm(time_str)
    if not date_str:
        return None

    candidate = date_str if not time_str else f"{date_str} {time_str}"
    try:
        tzinfo = tz.gettz(tz_name) if tz_name else None
        dt = dtparse.parse(candidate, dayfirst=False, yearfirst=False)
        if dt.tzinfo is None and tzinfo is not None:
            dt = dt.replace(tzinfo=tzinfo)
        return dt
    except Exception:
        return None


def _split_csv_list(val: Optional[str]) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in re.split(r"[;,]", val) if x.strip()]


# ---- Column aliases (case/space-insensitive) -------------------------------

ALIASES = {
    # required
    "start date": "start_date",
    "start time": "start_time",
    "event name": "name",
    # optional date bits
    "end date": "end_date",
    "end time": "end_time",
    "all day": "all_day",
    "timezone": "timezone",
    # copy & metadata
    "slugline": "slugline",
    "description": "description_short",
    "long description": "description_long",
    "ed note": "ednote",
    "internal note": "internal_note",  # accepted but dropped later
    # occurrence status (support common misspelling)
    "occurrence status": "occur_status",
    "occurence status": "occur_status",
    # calendars (qcodes, comma/semicolon separated)
    "calendars": "calendars",
    # location
    "location name": "loc_name",
    "location address": "loc_address",
    "location city/town": "loc_city",
    "location state/province/region": "loc_area",
    "location country": "loc_country",
    # contact (flattened into a single display string)
    "contact honorific": "c_honorific",
    "contact first name": "c_first",
    "contact last name": "c_last",
    "contact organisation": "c_org",
    "contact point of contact": "c_poc",
    "contact email": "c_email",
    "contact phone number": "c_phone",
    "contact phone usage": "c_phone_usage",
    "contact phone public": "c_phone_public",
}


def _canon(col: str) -> str:
    key = _norm(col).lower()
    return ALIASES.get(key, key)


# ---- Builders (each does one small thing) ----------------------------------


def _build_location(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    has_loc = any(
        r.get(k)
        for k in ("loc_name", "loc_address", "loc_city", "loc_area", "loc_country")
    )
    if not has_loc:
        return None

    addr_line = [r["loc_address"]] if r.get("loc_address") else []
    addr: Dict[str, Any] = {
        "line": addr_line or None,
        "locality": r.get("loc_city") or None,
        "area": r.get("loc_area") or None,
        "country": r.get("loc_country") or None,
    }
    # prune empty values
    addr = {k: v for k, v in addr.items() if v}

    loc: Dict[str, Any] = {"name": r.get("loc_name") or None}
    if addr:
        loc["address"] = addr
    return loc


def _build_calendars(r: Dict[str, Any]) -> List[Dict[str, str]]:
    codes = _split_csv_list(r.get("calendars")) if r.get("calendars") else []
    return [{"qcode": q} for q in codes]


def _build_occur_status(r: Dict[str, Any]) -> Optional[Dict[str, str]]:
    code = _norm(r.get("occur_status")) if r.get("occur_status") else ""
    return {"qcode": code} if code else None


def _collect_external_links(raw_row: Dict[str, Any]) -> List[Dict[str, str]]:
    urls: List[str] = []
    for hdr, val in raw_row.items():
        if hdr and EXTERNAL_LINK_COL_RE.match(hdr) and val and _norm(val):
            urls.append(_norm(val))
    return [{"href": u} for u in urls] if urls else []


def _build_contact(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build contact info as a contact object for database storage."""
    needed = ("c_first", "c_last", "c_org", "c_email", "c_phone")
    if not any(r.get(k) for k in needed):
        return None

    contact: Dict[str, Any] = {
        "is_active": True,
        "public": True,
    }

    # Build name
    name_bits = []
    if r.get("c_honorific"):
        name_bits.append(r["c_honorific"])
    if r.get("c_first"):
        name_bits.append(r["c_first"])
        contact["first_name"] = r["c_first"]
    if r.get("c_last"):
        name_bits.append(r["c_last"])
        contact["last_name"] = r["c_last"]

    if name_bits:
        contact["name"] = " ".join(name_bits)

    if r.get("c_org"):
        contact["organisation"] = r["c_org"]
    if r.get("c_poc"):
        contact["job_title"] = r["c_poc"]
    if r.get("c_email"):
        contact["contact_email"] = [r["c_email"].lower()]
    if r.get("c_phone"):
        contact["contact_phone"] = [
            {"number": r["c_phone"], "public": _str2bool(r.get("c_phone_public", True))}
        ]

    return contact if contact.get("name") or contact.get("contact_email") else None


def _contact_text(r: Dict[str, Any]) -> Optional[str]:
    needed = ("c_first", "c_last", "c_org", "c_email", "c_phone")
    if not any(r.get(k) for k in needed):
        return None
    name_bits = " ".join(
        x for x in (r.get("c_honorific"), r.get("c_first"), r.get("c_last")) if x
    )
    phone_bits = (
        f"{r.get('c_phone')} ({r.get('c_phone_usage')})" if r.get("c_phone") else None
    )
    public_tag = "public" if _str2bool(r.get("c_phone_public")) else None
    parts = [
        name_bits or None,
        r.get("c_org"),
        r.get("c_poc"),
        r.get("c_email"),
        phone_bits,
        public_tag,
    ]
    joined = " | ".join([p for p in parts if p])
    return joined or None


def _prune(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _gen_guid(file_path: str, row_index: int) -> str:
    """Stable URN based on filename and CSV row index (header=1, first row=2)."""
    return generate_tag_from_url(f"{os.path.basename(file_path)}:{row_index}", "urn")


# ---- Parser ----------------------------------------------------------------


class EventsCSVFeedParser(FeedParser):
    NAME = "stt_events_csv"
    label = "STT Events CSV Parser"

    def can_parse(self, file_path: str) -> bool:  # noqa: D401
        """Return True for .csv files."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext == ".csv"

    def _open_reader(self, file_path: str) -> csv.DictReader:
        """Open CSV as UTF-8 (BOM-safe), sniff delimiter, return DictReader."""
        with open(file_path, "rb") as fh:
            raw = fh.read()
        # Remove BOM if present
        text = raw.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except Exception:
            dialect = csv.excel
        return csv.DictReader(io.StringIO(text), dialect=dialect)

    def parse(
        self, file_path: str, provider: Optional[dict] = None
    ) -> List[Dict[str, Any]]:  # noqa: D401
        """Parse CSV and return a list of event items."""
        del provider
        reader = self._open_reader(file_path)

        items: List[Dict[str, Any]] = []
        row_index = 1  # header line is 1; first data row will be 2

        for raw_row in reader:
            row_index += 1

            # Normalize headers and values
            r: Dict[str, Any] = {}
            for k, v in raw_row.items():
                if k is None:
                    continue
                r[_canon(k)] = v.strip() if isinstance(v, str) else v

            # Required fields present?
            if not _norm(r.get("start_date", "")) or not _norm(r.get("name", "")):
                continue

            # Datetimes
            tz_name = r.get("timezone") or None
            start_dt = _parse_dt(r.get("start_date"), r.get("start_time"), tz_name)
            # Only compute explicit end if any end-* columns exist, else default to start
            end_dt = None
            if r.get("end_date") or r.get("end_time"):
                end_dt = _parse_dt(
                    r.get("end_date") or r.get("start_date"), r.get("end_time"), tz_name
                )
            if not start_dt:
                # Guard: parsing failed despite required columns
                continue

            all_day = bool(_str2bool(r.get("all_day")))

            # Build dates ensuring END > START (required by planning.events validator)
            if end_dt and end_dt > start_dt:
                base_end = end_dt
            else:
                # If all-day, make it a one-day span; else default duration = 60 minutes
                base_end = (
                    (start_dt + timedelta(days=1))
                    if all_day
                    else (start_dt + timedelta(minutes=60))
                )

            dates: Dict[str, Any] = {
                "start": start_dt,
                "end": base_end,
            }
            if all_day:
                dates["all_day"] = True
            if tz_name:
                dates["tz"] = tz_name
            occur_status = _build_occur_status(r)
            if occur_status:
                dates["occur_status"] = occur_status

            event: Dict[str, Any] = {
                "guid": _gen_guid(file_path, row_index),
                "type": "event",
                "name": _norm(r.get("name")),
                "slugline": _norm(r.get("slugline")) or None,
                "description_short": r.get("description_short") or None,
                "description_long": r.get("description_long") or None,
                "ednote": r.get("ednote") or None,
                "dates": dates,
                "links": _collect_external_links(raw_row) or None,
                "original_source": "CSV",
                "pubstatus": "usable",
                "extra": {
                    "stt_source": "csv",
                    "csv_row": row_index,
                },
            }

            calendars = _build_calendars(r)
            if calendars:
                event["calendars"] = calendars

            # Handle location - save to database if it has a unique identifier
            location = _build_location(r)
            if location:
                try:
                    locations_service = get_resource_service("locations")
                    if locations_service is not None:
                        # Create a unique identifier for the location
                        location_parts = []
                        if location.get("name"):
                            location_parts.append(location["name"])
                        if location.get("address", {}).get("locality"):
                            location_parts.append(location["address"]["locality"])
                        if location_parts:
                            location_id = _slugify("_".join(location_parts))
                            custom_guid = f"urn:stt:location:csv:{location_id}"
                            location["qcode"] = custom_guid

                            existing_location = locations_service.find_one(
                                req=None, guid=custom_guid
                            )

                            if existing_location:
                                updated_location = {**existing_location, **location}
                                location_id = existing_location["_id"]
                                locations_service.update(
                                    location_id, updated_location, existing_location
                                )
                                saved_location = locations_service.find_one(
                                    req=None, _id=location_id
                                )
                                saved_location["qcode"] = custom_guid
                            else:
                                location["guid"] = custom_guid
                                location_ids = locations_service.post([location])
                                saved_location = locations_service.find_one(
                                    req=None, _id=location_ids[0]
                                )
                                if saved_location:
                                    saved_location["qcode"] = custom_guid

                            event["location"] = [saved_location]
                        else:
                            event["location"] = [location]
                except Exception as e:
                    logger.warning(
                        f"Failed to save location for event {event.get('name')}: {e}"
                    )
                    event["location"] = [location]

            # Handle contact info - save to database and use ObjectIds
            contact = _build_contact(r)
            if contact:
                try:
                    contacts_service = get_resource_service("contacts")
                    # Check if contact already exists
                    existing_contact = None
                    if contact.get("contact_email"):
                        cursor = contacts_service.search(
                            {
                                "query": {
                                    "term": {
                                        "contact_email.keyword": contact["contact_email"][0]
                                    }
                                }
                            }
                        )
                        if cursor.count():
                            existing_contact = list(cursor)[0]

                    if existing_contact:
                        event["event_contact_info"] = [
                            ObjectId(existing_contact["_id"])
                        ]
                    else:
                        new_contact_id = contacts_service.post([contact])[0]
                        event["event_contact_info"] = [new_contact_id]
                except Exception as e:
                    logger.warning(
                        f"Failed to save contact for event {event.get('name')}: {e}"
                    )
                    # Fallback to text contact info
                    contact_text = _contact_text(r)
                    if contact_text:
                        event["event_contact_info"] = [contact_text]

            # Set expiry_offset for expiry calculation using base_end
            event["expiry_offset"] = base_end

            # Prune empty values
            event["dates"] = _prune(event["dates"])
            event = _prune(event)
            items.append(event)

        return items


register_feed_parser(EventsCSVFeedParser.NAME, EventsCSVFeedParser())
