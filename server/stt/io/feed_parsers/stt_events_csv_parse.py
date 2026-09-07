from __future__ import annotations


import csv
import io
import os
import re
import locale
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
from settings import DEFAULT_TIMEZONE

from ...common import upsert_location


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


def _infer_dayfirst() -> bool:
    """
    Determine whether dates should be parsed with day-first ordering based on locale.

    This checks the current LC_TIME locale (falling back to the default locale) and
    returns True for non-``en_US`` locales, and False for ``en_US`` or when the locale
    cannot be determined.
    """
    try:
        loc = locale.getlocale(locale.LC_TIME)[0]
    except Exception:
        loc = None

    if not loc:
        env_loc = os.environ.get("LC_TIME") or os.environ.get("LANG")
        if env_loc:
            loc = env_loc.split(".", 1)[0].split("@", 1)[0]

    if not loc:
        return False

    loc = loc.lower()
    return not loc.startswith("en_us")


def _parse_dt(
    date_str: Optional[str],
    time_str: Optional[str],
    tz_name: Optional[str],
    default_tz_name: Optional[str] = None,
    dayfirst: Optional[bool] = None,
) -> tuple[Optional[datetime], bool]:
    """Parse flexible date/time strings. If tz_name provided and parsed value is
    naive, apply that timezone. Returns (datetime, used_default_tz) or (None, False)
    on failure.
    """
    date_str = _norm(date_str)
    time_str = _norm(time_str)
    if not date_str:
        return None, False

    candidate = date_str if not time_str else f"{date_str} {time_str}"
    try:
        used_default_tz = False
        tzinfo = (
            tz.gettz(tz_name)
            if tz_name
            else (tz.gettz(default_tz_name) if default_tz_name else None)
        )
        parsed_dayfirst = _infer_dayfirst() if dayfirst is None else dayfirst
        dt = dtparse.parse(candidate, dayfirst=parsed_dayfirst, yearfirst=False)
        if dt.tzinfo is None and tzinfo is not None:
            dt = dt.replace(tzinfo=tzinfo)
            if not tz_name and default_tz_name:
                used_default_tz = True
        return dt, used_default_tz
    except Exception:
        return None, False


def _split_csv_list(val: Optional[str]) -> List[str]:
    if not val:
        return []
    return [x.strip() for x in re.split(r"[;,]", val) if x.strip()]


def _parse_dayfirst_hint(value: Optional[str]) -> Optional[bool]:
    """Detect explicit date ordering hints from template/header rows.

    Supports common placeholders like "DD/MM/YYYY" and "MM/DD/YYYY".
    """
    token = _norm(value).lower().replace(" ", "")
    if not token:
        return None
    if token in {"dd/mm/yyyy", "d/m/yyyy", "dd/mm/yy", "d/m/yy"}:
        return True
    if token in {"mm/dd/yyyy", "m/d/yyyy", "mm/dd/yy", "m/d/yy"}:
        return False
    return None


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


def _build_occur_status(row: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Resolve event occurrence status from CSV against IPTC vocabulary.

    Accepts either qcode (e.g. 'eocstat:eos5') or label (e.g. 'Planned, occurs certainly').
    Returns a dict with {'qcode', 'name', 'label'} or None if nothing can be resolved.

    This function must not fabricate raw/free-text values or apply arbitrary defaults.
    """
    raw = _norm(row.get("occur_status")) if row.get("occur_status") else ""
    if not raw:
        return None

    items: List[Dict[str, Any]] = []
    try:
        svc = get_resource_service("vocabularies")
    except Exception:
        svc = None

    if svc:
        get_items = getattr(svc, "get_items", None)
        if callable(get_items):
            items = get_items("eventoccurstatus") or []
        else:
            find_one = getattr(svc, "find_one", None)
            if callable(find_one):
                vocab = find_one(req=None, _id="eventoccurstatus") or {}
                items = vocab.get("items") or []

    if not items:
        # No vocabulary available: do not fabricate anything
        return None

    # Filter only active items
    items = [it for it in items if bool(it.get("is_active", True))]
    if not items:
        return None

    lower = raw.lower()

    # 1) Exact qcode match (case-insensitive)
    for it in items:
        q = (it.get("qcode") or "").strip()
        if q and q.lower() == lower:
            name = _norm(it.get("name") or it.get("label") or q)
            label = _norm(it.get("label") or name)
            return {"qcode": q, "name": name, "label": label}

    # 2) Exact label/name match (case-insensitive)
    for it in items:
        name = _norm(it.get("name"))
        label = _norm(it.get("label"))
        if lower in {name.lower(), label.lower()}:
            q = _norm(it.get("qcode") or "")
            return {"qcode": q, "name": name or label or q, "label": label or name or q}

    # No match found -> do not return fabricated values
    return None


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
    """CSV Events Parser with STT-compatible configuration.

    Config options in provider["config"]:
    - no_end_time (bool): If True, ignores 'end_time' column. Uses only 'end_date' or defaults to 'start_date'.
    """

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

    async def parse(
        self, file_path: str, provider: Optional[dict] = None
    ) -> List[Dict[str, Any]]:  # noqa: D401
        """Parse CSV and return a list of Superdesk event items."""
        config = provider.get("config") if provider else {}
        no_end_time = config.get("no_end_time", False) is True if config else False
        reader = self._open_reader(file_path)

        items: List[Dict[str, Any]] = []
        row_index = 1  # header line is 1; first data row will be 2
        dayfirst_hint: Optional[bool] = None

        for raw_row in reader:
            row_index += 1

            # Normalize headers and values
            r: Dict[str, Any] = {}
            for k, v in raw_row.items():
                if k is None:
                    continue
                r[_canon(k)] = v.strip() if isinstance(v, str) else v

            if dayfirst_hint is None:
                dayfirst_hint = _parse_dayfirst_hint(r.get("start_date"))

            # Required fields present?
            if not _norm(r.get("start_date", "")) or not _norm(r.get("name", "")):
                continue

            # Datetimes
            tz_name = _norm(r.get("timezone")) or None
            start_time_missing = not _norm(r.get("start_time"))
            end_time_missing = not _norm(r.get("end_time"))

            start_dt, start_used_default_tz = _parse_dt(
                r.get("start_date"),
                r.get("start_time"),
                tz_name,
                DEFAULT_TIMEZONE,
                dayfirst=dayfirst_hint,
            )
            if not start_dt:
                # Guard: parsing failed despite required columns
                continue

            # Determine end date/time logic
            end_date = r.get("end_date") or r.get("start_date")
            end_time = None if (no_end_time or end_time_missing) else r.get("end_time")
            if r.get("end_date") or r.get("end_time"):
                end_dt, end_used_default_tz = _parse_dt(
                    end_date,
                    end_time,
                    tz_name,
                    DEFAULT_TIMEZONE,
                    dayfirst=dayfirst_hint,
                )
            else:
                end_dt, end_used_default_tz = None, False

            all_day = bool(_str2bool(r.get("all_day")))
            # Missing start or end time implies all-day.
            if start_time_missing or end_time_missing:
                all_day = True

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
            elif start_used_default_tz or end_used_default_tz:
                dates["tz"] = DEFAULT_TIMEZONE

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
            occur_status = _build_occur_status(r)
            if occur_status:
                event["occur_status"] = occur_status

            calendars = _build_calendars(r)
            if calendars:
                event["calendars"] = calendars

            # Handle location - save to database if it has a unique identifier
            location = _build_location(r)
            if location:
                try:
                    # Create a unique identifier for the location
                    location_parts = []
                    if location.get("name"):
                        location_parts.append(location["name"])
                    if location.get("address", {}).get("locality"):
                        location_parts.append(location["address"]["locality"])
                    if location_parts:
                        location_slug = _slugify("_".join(location_parts))
                        custom_guid = f"urn:stt:location:csv:{location_slug}"
                        saved_location = await upsert_location(location, custom_guid)
                        event["location"] = (
                            [saved_location] if saved_location else [location]
                        )
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
                                        "contact_email.keyword": contact[
                                            "contact_email"
                                        ][0]
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
