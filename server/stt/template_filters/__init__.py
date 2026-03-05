"""
Register custom Jinja filters – fi_current_date, fi_date, fi_time and fi_ddmm – so they are
available in every template rendered by Superdesk.
"""

import logging
import re
from datetime import datetime
from html import unescape
from typing import Any

import pytz  # type: ignore
from dateutil import parser
from markupsafe import Markup

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


def fi_date(value: str, capitalized: bool = False) -> str:
    dt = _to_helsinki(value)
    if not dt:
        return value or ""
    weekday = _WEEKDAY_FI[dt.weekday()]
    if capitalized:
        weekday = weekday.capitalize()
    return f"{weekday} {dt.day}.{dt.month}."


def fi_current_date() -> str:
    dt = datetime.now(_HELSINKI)
    capitalized_weekday = _WEEKDAY_FI[dt.weekday()].capitalize()
    return f"{capitalized_weekday} {dt.day}.{dt.month}."


def fi_time(value: str) -> str:
    dt = _to_helsinki(value)
    if not dt:
        return value or ""
    hour = dt.hour
    minute = dt.minute
    # return time like "9.05" or "14.30"
    return f"{hour}.{minute:02d}"


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


def stt_priority_to_text(priority: int) -> str:
    # 1 = pääaihe
    # 2 = perusjuttu
    # 3 = perusjuttu
    # 4 = lyhyt juttu
    # 5 = tulokset
    priority_map = {
        1: "pääaihe",
        2: "perusjuttu",
        3: "perusjuttu",
        4: "lyhyt juttu",
        5: "tulokset",
    }
    return priority_map.get(priority, "")


def html_unescape(value: Any) -> Markup:
    if value is None:
        return Markup("")
    if isinstance(value, Markup):
        return value
    try:
        return Markup(unescape(str(value)))
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("html_unescape failed: %s", exc)
        return Markup(str(value))


def count_body_html_characters(value: Any) -> int:
    if value is None:
        return 0
    try:
        text = str(value).strip()

        # equivalent to client-side cleanHtml
        text = re.sub(r"<!-- EMBED START [\s\S]+?<!-- EMBED END .*?-->", "", text)
        text = re.sub(r"(?i)<br[^>]*>", "&nbsp;", text)
        text = re.sub(r"</?[^>]+></?[^>]+>", " ", text)
        text = re.sub(r"</?[^>]+>", "", text)
        text = text.strip().replace("&nbsp;", " ")

        # additional JS equivalent `input = input.replace(/\r?\n|\r/g, '');`
        text = re.sub(r"\r?\n|\r", "", text)

        # unescape HTML entities before counting, as the visible text shouldn't count HTML entities verbatim
        text = unescape(text)

        return len(text)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("count_body_html_characters failed: %s", exc)
        return 0


def init_app(app):
    app.jinja_env.filters["fi_date"] = fi_date
    app.jinja_env.filters["fi_time"] = fi_time
    app.jinja_env.filters["fi_ddmm"] = fi_ddmm
    app.jinja_env.globals["fi_current_date"] = fi_current_date
    app.jinja_env.filters["fi_which_weekday"] = fi_which_weekday
    app.jinja_env.filters["stt_priority_to_text"] = stt_priority_to_text
    app.jinja_env.filters["html_unescape"] = html_unescape
    app.jinja_env.filters["count_body_html_characters"] = count_body_html_characters
