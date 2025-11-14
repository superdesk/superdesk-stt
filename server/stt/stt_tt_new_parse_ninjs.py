from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dateutil import tz
from dateutil.parser import isoparse
from lxml import etree
from lxml import html as lxml_html
from superdesk.io.feed_parsers.ninjs import NINJSFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.text_utils import sanitize_html

from .constants import (
    DEPARTMENT_MAP,
    DEFAULT_DEPARTMENT,
    STT_TIMEZONE,
)

IGNORE_REMOTE_IMAGES = (
    True  # Force using only root-level fields (no associations/links/renditions)
)
IMAGE_CHECK_TIMEOUT = 2  # seconds


class STTTTNEWNINJSFeedParser(NINJSFeedParser):
    """Feed Parser for STT TT NINJS format."""

    NAME = "stt_tt_new_ninjs"
    label = "STT TT New NINJS Feed Parser"

    def __init__(self) -> None:
        super().__init__()
        # Reusable HTTP session (connection pooling + retries) for image URL checks
        self._session = requests.Session()
        retry = Retry(
            total=2,  # quick checks; keep small to avoid blocking ingest
            connect=2,
            read=2,
            status=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"HEAD", "GET"}),
            backoff_factor=0.5,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._img_headers = {"User-Agent": "Superdesk-STT/1.0", "Accept": "image/*"}

    def _transform_from_stt_tt_ninjs(self, ninjs: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compat alias used by older code paths."""
        return self._transform_from_ninjs(ninjs)

    def _parse_dt_safe(self, value: Optional[str]):
        """Parse ISO datetime safely; return aware datetime in UTC when possible."""
        if not value:
            return None
        try:
            dt = isoparse(value)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=tz.gettz(STT_TIMEZONE)).astimezone(tz.UTC)
            return dt.astimezone(tz.UTC)
        except Exception:
            return None

    def _url_ok(self, url: str) -> bool:
        """Return True if URL is publicly accessible (HTTP 200). Uses HEAD then GET fallback."""
        if not url or not isinstance(url, str) or not url.startswith("http"):
            return False
        try:
            resp = self._session.head(
                url,
                allow_redirects=True,
                timeout=IMAGE_CHECK_TIMEOUT,
                headers=self._img_headers,
            )
            if resp.status_code == 405:  # some hosts disallow HEAD
                resp = self._session.get(
                    url,
                    stream=True,
                    allow_redirects=True,
                    timeout=IMAGE_CHECK_TIMEOUT,
                    headers=self._img_headers,
                )
            return resp.status_code == 200
        except Exception:
            return False

    def _filter_remote_images(self, ninjs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter associations/links/renditions to only those with publicly accessible URLs."""
        out = dict(ninjs)

        # Associations (keep only images with at least one 200 URL)
        assocs = ninjs.get("associations") or {}
        if assocs:
            kept = {}
            for key, obj in assocs.items():
                t = (obj or {}).get("type") or (obj or {}).get("profile")
                if t in {"image", "picture", "graphic"}:
                    # collect candidate URLs
                    urls = []
                    for ro in (obj.get("renditions") or {}).values():
                        href = (ro or {}).get("href")
                        if href:
                            urls.append(href)
                    for lk in obj.get("links") or []:
                        href = (lk or {}).get("href")
                        if href:
                            urls.append(href)
                    ok = any(self._url_ok(u) for u in urls)
                    if ok:
                        kept[key] = obj
                else:
                    kept[key] = obj
            if kept:
                out["associations"] = kept
            else:
                out.pop("associations", None)

        # Top-level links
        links = ninjs.get("links") or []
        if links:
            new_links = []
            for lk in links:
                href = (lk or {}).get("href")
                if not href or self._url_ok(href):
                    new_links.append(lk)
            if new_links:
                out["links"] = new_links
            else:
                out.pop("links", None)

        # Top-level renditions
        rends = ninjs.get("renditions") or {}
        if rends:
            new_rends = {}
            for name, ro in rends.items():
                href = (ro or {}).get("href")
                if not href or self._url_ok(href):
                    new_rends[name] = ro
            if new_rends:
                out["renditions"] = new_rends
            else:
                out.pop("renditions", None)

        return out

    # --------- Core overrides ---------

    def can_parse(self, file_path: str) -> bool:
        """Only parse non-image ninjs JSON files; resilient to malformed input."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                ninjs = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        content_type = (ninjs.get("type") or "").lower()
        if content_type in {"image", "picture"}:
            return False
        return True

    def _transform_from_ninjs(self, ninjs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extend base NINJS transformation with TT/STT specifics:
        - Detect sports sector
        - Sanitize/normalize HTML (prefer body_html5)
        - Map TT metadata -> STT metadata (Source, Department, Desk, Priority, Name, ExternalID)
        - Drop heavy associations after parent mapping
        """

        ninjs_local = dict(ninjs)  # avoid mutating caller
        raw_html = (
            ninjs_local.get("body_html5")
            or ninjs_local.get("body_html")
            or ninjs_local.get("body")
        )

        ninjs_for_parent = dict(ninjs_local)
        ninjs_for_parent.pop("associations", None)
        ninjs_for_parent.pop("links", None)
        ninjs_for_parent.pop("renditions", None)

        # First, let parent build a standard Superdesk item (ids, qcodes, dates...)
        item = super()._transform_from_ninjs(ninjs_for_parent)

        # Clamp versioncreated so it never exceeds the parent text item's timestamp
        # Removed per instructions

        # --- HTML sanitize/normalize
        item["body_html"] = self.sanitise_stt_tt_html(raw_html)

        # --- Metadata mapping TT -> STT (derivative of Neo import rules)

        # Source: fixed "TT"
        item["source"] = "TT"

        # Department mapping -> store as extra.stt_meta and as anpa_category using CV lookup
        tt_dept_code = (
            ninjs_local.get("department")
            or ninjs_local.get("dept")
            or ninjs_local.get("sector")
            or ninjs_local.get("profile")
        )
        # Maintain original extra.stt_meta fields for backward compatibility/tests
        dept_id, dept_name = self._map_department(tt_dept_code)
        item.setdefault("extra", {})
        item["extra"].setdefault("stt_meta", {})
        item["extra"]["stt_meta"]["department_id"] = dept_id
        item["extra"]["stt_meta"]["department_name"] = dept_name
        item["extra"]["stt_meta"]["tt_department_code"] = tt_dept_code

        # Superdesk expects anpa_category as a list of {qcode, name}
        # Use department ID as qcode instead of string qcode
        item["anpa_category"] = [{"qcode": str(dept_id), "name": dept_name}]

        # Priority <- TT urgency (pass-through as int if present)
        urgency = ninjs_local.get("urgency")
        if urgency is not None:
            try:
                item["priority"] = int(urgency)
            except (TypeError, ValueError):
                item["priority"] = None

        # Name (headline), with press-release special formatting if you decide later
        # For now, keep headline as name; parent may already set it.
        headline = (
            ninjs_local.get("headline")
            or ninjs_local.get("title")
            or item.get("headline")
            or item.get("name")
        )
        if headline:
            item["name"] = headline
            item["headline"] = headline
        else:
            # Fallback: use description_text if no headline found
            description = ninjs_local.get("description_text")
            if description:
                item["headline"] = description

        # ExternalID: choose a stable id in order of likelihood for TT
        external_id = (
            ninjs_local.get("originaltransmissionreference")
            or ninjs_local.get("id")
            or ninjs_local.get("guid")
            or ninjs_local.get("uri")
            or ninjs_local.get("job")
        )
        if external_id:
            item["external_id"] = external_id

        # Description: filename if present; leave empty otherwise
        description = ninjs_local.get("filename") or ninjs_local.get("description")
        if description:
            item["description_text"] = description

        if IGNORE_REMOTE_IMAGES:
            item.pop("associations", None)

        if item.get("subject"):
            # filter out subjects without qcode or name
            item["subject"] = [
                s for s in item["subject"] if s.get("qcode") and s.get("name")
            ]

        return item

    # --------- Helpers ---------
    def _map_department(self, tt_code: Optional[str]) -> Tuple[int, str]:
        """Map TT department string → (STT integer id, STT string)."""
        if not tt_code:
            return DEFAULT_DEPARTMENT
        code = str(tt_code).strip().upper()
        return DEPARTMENT_MAP.get(code, DEFAULT_DEPARTMENT)

    def datetime(self, value: Optional[str]) -> Optional[Any]:
        """
        Parse incoming datetime to a tz-aware UTC datetime object.
        - If value has tz -> normalize to UTC
        - If naive -> treat as Europe/Helsinki, then convert to UTC
        Return a datetime or None.
        """
        if not value:
            return None
        try:
            dt = isoparse(value)
        except Exception:
            return None

        local_tz = tz.gettz(STT_TIMEZONE)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz or tz.UTC)
        return dt.astimezone(tz.UTC)

    def sanitise_stt_tt_html(self, html: Optional[str]) -> str:
        """
        Normalize/sanitize TT HTML:
        - <div class="byline"> -> <p>
        - <span> -> <p>
        - remove container tags (html, body, article, section, etc.)
        - return inner HTML of root (no brittle slicing)
        """
        if not html:
            return ""

        remove_tags = [
            "html",
            "body",
            "title",
            "article",
            "section",
            "aside",
            "div",
            "h4",
        ]
        if IGNORE_REMOTE_IMAGES:
            remove_tags.extend(["img", "figure", "picture", "source"])

        kill_tags = ["head"]

        root_elem = lxml_html.fromstring(html)

        for _action, el in etree.iterwalk(root_elem):
            if el.tag == "div" and el.get("class") == "byline":
                el.tag = "p"
            if el.tag == "span":
                el.tag = "p"

        traversed_html = etree.tostring(root_elem, encoding="unicode")

        sanitized_html = sanitize_html(
            traversed_html, remove_tags=remove_tags, kill_tags=kill_tags
        )

        try:
            sanitized_root = lxml_html.fromstring(sanitized_html)
            inner_parts = [
                etree.tostring(c, encoding="unicode") for c in sanitized_root
            ]
            return "".join(inner_parts).strip()
        except Exception:
            return sanitized_html.strip()


register_feed_parser(STTTTNEWNINJSFeedParser.NAME, STTTTNEWNINJSFeedParser())
