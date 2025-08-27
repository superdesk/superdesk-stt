# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013,
# 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from dateutil import tz
from dateutil.parser import isoparse
from lxml import etree
from lxml import html as lxml_html
from superdesk import get_resource_service
from superdesk.io.feed_parsers.ninjs import NINJSFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.text_utils import sanitize_html
from superdesk.utc import local_to_utc

TIMEZONE = "Europe/Helsinki"

# Controlled Vocabulary id used in Superdesk for STT departments
STT_DEPT_VOCAB_ID = "stt_department_categories"

# TT department code -> STT CV qcode
_DEPARTMENT_QCODE_MAP: Dict[str, str] = {
    "INR": "kotimaa",
    "UTR": "ulkomaat",
    "SPO": "urheilu",
    "HBT": "muuta",
    "RED": "toimituksille_tiedoksi",
    "TTL": "urheilu",
    "PRM": "tiedotepalvelu",
    "DOM": "talous",
    "FOR": "talous",
    "SPR": "urheilu",
    "TBL": "urheilu",
}

# TT department code -> (STT integer value, STT string value)
_DEPARTMENT_MAP: Dict[str, Tuple[int, str]] = {
    "INR": (3, "Kotimaa"),
    "UTR": (14, "Ulkomaat"),
    "SPO": (16, "Urheilu"),
    "HBT": (6, "Muuta"),
    "RED": (13, "Toimituksille tiedoksi"),
    "TTL": (16, "Urheilu"),
    "PRM": (12, "Tiedotepalvelu"),
    "DOM": (11, "Talous"),
    "FOR": (11, "Talous"),
    "SPR": (16, "Urheilu"),
    "TBL": (16, "Urheilu"),
}
_DEFAULT_DEPT: Tuple[int, str] = (3, "Kotimaa")


class STTTTNEWNINJSFeedParser(NINJSFeedParser):
    """Feed Parser for STT TT NINJS format."""

    NAME = "stt_tt_new_ninjs"
    label = "STT TT New NINJS Feed Parser"

    def __init__(self) -> None:
        super().__init__()
        self.is_sport_item = False

    # --------- Core overrides ---------

    def can_parse(self, file_path: str) -> bool:
        """Only parse non-image ninjs JSON files; resilient to malformed input."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                ninjs = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        content_type = ninjs.get("type")
        if content_type == "image":
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
        self.is_sport_item = ninjs.get("sector") == "SPT"

        ninjs_local = dict(ninjs)  # avoid mutating caller
        raw_html = (
            ninjs_local.get("body_html5")
            or ninjs_local.get("body_html")
            or ninjs_local.get("body")
        )

        # First, let parent build a standard Superdesk item (ids, qcodes, dates...)
        item = super()._transform_from_ninjs(ninjs_local)

        # --- HTML sanitize/normalize
        item["body_html"] = self.sanitise_stt_tt_html(raw_html)

        # --- Metadata mapping TT -> STT (derivative of Neo import rules)

        # Source: fixed "TT"
        item["source"] = "TT"

        # Desk: fixed "Ulkomaat" (per spec)
        # If your schema uses another field name (e.g. "task.desk"), adjust here.
        item["desk"] = "Ulkomaat"

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
        key_for_map = str(tt_dept_code).strip().upper() if tt_dept_code else ""
        mapped_qcode = _DEPARTMENT_QCODE_MAP.get(key_for_map)
        if not mapped_qcode:
            # default to Kotimaa when unknown
            mapped_qcode = "kotimaa"

        cv_item = self._get_cv_item_by_qcode(STT_DEPT_VOCAB_ID, mapped_qcode)
        anpa_name = (cv_item or {}).get("name") or _DEPARTMENT_MAP.get(
            str(tt_dept_code).strip().upper() if tt_dept_code else "", _DEFAULT_DEPT
        )[1]

        # Superdesk expects anpa_category as a list of {qcode, name}
        item["anpa_category"] = [{"qcode": mapped_qcode, "name": anpa_name}]

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

        # After mapping, you can remove associations to reduce payload size
        item.pop("associations", None)

        return item

    # --------- Helpers ---------

    def _get_cv_item_by_qcode(
        self, vocab_id: str, qcode: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Fetch a vocabulary item by qcode from Superdesk CV. Safe on failure.

        Returns the full CV item dict or None if not found.
        """
        if not qcode:
            return None
        try:
            svc = get_resource_service("vocabularies")
            vocab = svc.find_one(req=None, _id=vocab_id)
            if not vocab:
                return None
            for it in vocab.get("items", []):
                if it.get("qcode") == qcode:
                    return it
        except Exception:
            # Service may be unavailable during certain unit tests
            return None
        return None

    def _map_department(self, tt_code: Optional[str]) -> Tuple[int, str]:
        """Map TT department string → (STT integer id, STT string)."""
        if not tt_code:
            return _DEFAULT_DEPT
        code = str(tt_code).strip().upper()
        return _DEPARTMENT_MAP.get(code, _DEFAULT_DEPT)

    def datetime(self, value: Optional[str]) -> Optional[str]:
        """
        Convert incoming datetime to UTC ISO:
        - If value has tz -> keep then convert
        - If naive -> treat as Europe/Helsinki, then convert
        Return ISO string in UTC or None.
        """
        if not value:
            return None

        dt = isoparse(value)
        local_tz = tz.gettz(TIMEZONE)
        if dt.tzinfo is None:
            if not local_tz:
                return value  # fallback, parent might handle
            dt = dt.replace(tzinfo=local_tz)
        else:
            # normalize through TIMEZONE for local_to_utc helper
            if local_tz and dt.tzinfo != local_tz:
                dt = dt.astimezone(local_tz)

        dt_utc = local_to_utc(TIMEZONE, dt)
        return dt_utc.isoformat()

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
