# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dateutil import parser as dtparse
from superdesk.io.feed_parsers import FeedParser
from superdesk.io.registry import register_feed_parser

logger = logging.getLogger(__name__)


# --- Module-private helpers ---


def _normalize_dateline(value: Any) -> Optional[Dict[str, str]]:
    """Return {"text": "..."} or None, per Superdesk mapping."""
    if value is None:
        return None
    if isinstance(value, dict):
        txt = value.get("text")
        if isinstance(txt, str) and txt.strip():
            return {"text": txt.strip()}
        # try to compose from pieces
        parts = []
        for k in ("city", "state", "province", "region", "country"):
            v = value.get(k)
            if isinstance(v, dict):
                name = v.get("name") or v.get("qcode")
                if isinstance(name, str) and name.strip():
                    parts.append(name.strip())
            elif isinstance(v, str) and v.strip():
                parts.append(v.strip())
        return {"text": ", ".join(parts)} if parts else None
    if isinstance(value, (list, tuple)):
        joined = ", ".join(str(v).strip() for v in value if str(v).strip())
        return {"text": joined} if joined else None
    s = str(value).strip()
    return {"text": s} if s else None


def _to_int_or_none(v: Any) -> Optional[int]:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class ContentAPIItemParser(FeedParser):
    NAME = "content_api_json"
    label = "STT Content API"

    def __init__(self):
        super().__init__()

    # Be liberal in what we accept: dict (one item) or list[dict] (batch)
    def can_parse(self, payload: Any) -> bool:
        if isinstance(payload, list):
            return all(isinstance(i, dict) for i in payload)
        if isinstance(payload, dict):
            # Accept wrapper dicts that contain a list of items under common keys
            for k in ("_items", "items", "results", "docs"):
                v = payload.get(k)
                if isinstance(v, list):
                    return all(isinstance(i, dict) for i in v if i is not None)
            # Also accept single-item dicts
            return True
        return False

    async def parse(
        self, item: Any, provider: Optional[dict] = None
    ) -> List[Dict[str, Any]]:
        provider = provider or {}
        # Case 1: Already a list of items
        if isinstance(item, list):
            out: List[Dict[str, Any]] = []
            for it in item:
                if isinstance(it, dict):
                    parsed = self._parse_one(it, provider)
                    if parsed and isinstance(parsed, dict):
                        out.append(parsed)
                else:
                    logger.warning(
                        "Skipping non-dict entry in list: %r (type: %s)",
                        it,
                        type(it).__name__,
                    )
            return out

        # Case 2: Wrapper dict containing a list of items under a common key
        if isinstance(item, dict):
            for key in ("_items", "items", "results", "docs"):
                raw_list = item.get(key)
                if isinstance(raw_list, list):
                    wrapper_out: List[Dict[str, Any]] = []
                    for it in raw_list:
                        if isinstance(it, dict):
                            parsed = self._parse_one(it, provider)
                            if parsed and isinstance(parsed, dict):
                                wrapper_out.append(parsed)
                        else:
                            logger.warning(
                                "Skipping non-dict entry under %s: %r (type: %s)",
                                key,
                                it,
                                type(it).__name__,
                            )
                    return wrapper_out

            # Case 3: Single content item dict
            parsed_one = self._parse_one(item, provider)
            return [parsed_one] if parsed_one and isinstance(parsed_one, dict) else []
        return []

    # ------------------------ internal helpers -------------------------
    def _parse_one(
        self, src: Dict[str, Any], provider: dict
    ) -> Optional[Dict[str, Any]]:
        """Map a single JSON item from Content API to Superdesk item."""
        if not isinstance(src, dict):
            logger.warning(
                "_parse_one received non-dict input: %s (type: %s)",
                src,
                type(src).__name__,
            )
            return None

        processed: Dict[str, Any] = dict(src)

        # Apply default fields and normalize headline/body
        self._apply_defaults(processed)

        # Normalize all known timestamp fields
        for tf in ("versioncreated", "firstcreated", "_updated", "_created"):
            if processed.get(tf):
                processed[tf] = self._normalize_timestamp(processed[tf])

        # Normalize dateline: Superdesk expects an object, not a string
        if "dateline" in processed:
            nd = _normalize_dateline(processed.get("dateline"))
            if nd is not None:
                processed["dateline"] = nd
            else:
                processed.pop("dateline", None)

        # Normalize priority (cast to int) or omit when invalid
        if "priority" in processed:
            pv = _to_int_or_none(processed.get("priority"))
            if pv is not None:
                processed["priority"] = pv
            else:
                processed.pop("priority", None)
        elif "urgency" in processed:
            pv = _to_int_or_none(processed.get("urgency"))
            if pv is not None:
                processed["priority"] = pv

        # Do not carry an explicit expiry from upstream; ingest should manage it
        processed.pop("expiry", None)

        # Ensure versioncreated is tz-aware and set
        vc = processed.get("versioncreated")
        if not isinstance(vc, datetime):
            processed["versioncreated"] = datetime.now(timezone.utc)
        elif vc.tzinfo is None:
            processed["versioncreated"] = vc.replace(tzinfo=timezone.utc)

        # Filter out items without meaningful content
        headline = processed.get("headline", "").strip()
        body_html = processed.get("body_html", "").strip()

        if not headline and not body_html:
            logger.info(
                "Skipping item without meaningful content: %s",
                processed.get("uri", "unknown"),
            )
            return None

        # Final safety check: ensure we always return a dict
        if not isinstance(processed, dict):
            logger.error(
                "_parse_one produced non-dict result: %s (type: %s)",
                processed,
                type(processed).__name__,
            )
            return None
        logger.warning("Processed item: %s", processed)
        return processed

    def _apply_defaults(self, item: Dict[str, Any]) -> None:
        item.setdefault("type", "text")
        item.setdefault("pubstatus", "usable")
        item.setdefault(
            "headline",
            item.get("headline") or item.get("name") or item.get("title") or "",
        )
        item.setdefault("body_html", item.get("body_html") or "")

    def _normalize_timestamp(self, value: Any) -> Optional[datetime]:
        """Normalize timestamps to tz-aware datetime (UTC)."""
        if not value:
            return None
        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        try:
            dt = dtparse.parse(str(value))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception as ex:
            logger.warning("Failed to parse timestamp %r: %s", value, ex)
            return datetime.now(timezone.utc)


# Register like BusinessWire example: parse() returns List[Dict]
register_feed_parser(ContentAPIItemParser.NAME, ContentAPIItemParser())
