"""
Register custom Jinja filters – fi_current_date, fi_date, fi_time and fi_ddmm – so they are
available in every template rendered by Superdesk.
"""

from dateutil import parser
from datetime import datetime
import pytz  # type: ignore
import logging

logger = logging.getLogger(__name__)

_HELSINKI = pytz.timezone("Europe/Helsinki")
_WEEKDAY_FI = [
    "maanantai",
    "tiistai",
    "keskiviikko",
    "torstai",
    "perjantai",
    "lauantai",
    "sunnuntai",
]


def _to_helsinki(value):
    """Parse ISO string and force Europe/Helsinki tz."""
    try:
        # if already a datetime, just convert timezone
        if isinstance(value, datetime):
            dt = value.astimezone(_HELSINKI)
        else:
            dt = parser.isoparse(value).astimezone(_HELSINKI)
        return dt
    except Exception:
        return None  # graceful fallback


def fi_date(value: str) -> str:
    dt = _to_helsinki(value)
    if not dt:
        return value or ""
    return f"{_WEEKDAY_FI[dt.weekday()]} {dt.day}.{dt.month}."


def fi_current_date() -> str:
    dt = datetime.now(_HELSINKI)
    capitalized_weekday = _WEEKDAY_FI[dt.weekday()].capitalize()
    return f"{capitalized_weekday} {dt.day}.{dt.month}."


def fi_time(value: str) -> str:
    dt = _to_helsinki(value)
    if not dt:
        return value or ""
    return dt.strftime("%H:%M")


def fi_ddmm(value: str) -> str:
    dt = _to_helsinki(value)
    if not dt:
        return ""
    return f"{dt.day:02d}.{dt.month:02d}."


def fi_which_weekday(value: str) -> str:
    # "2025-10-14T00:00:00+0000" => "tiistaina 14.10."
    dt = _to_helsinki(value)
    if not dt:
        return ""
    return f"{_WEEKDAY_FI[dt.weekday()]}na {dt.day}.{dt.month}."


def init_app(app):
    app.jinja_env.filters["fi_date"] = fi_date
    app.jinja_env.filters["fi_time"] = fi_time
    app.jinja_env.filters["fi_ddmm"] = fi_ddmm
    app.jinja_env.globals["fi_current_date"] = fi_current_date
    app.jinja_env.filters["fi_which_weekday"] = fi_which_weekday
