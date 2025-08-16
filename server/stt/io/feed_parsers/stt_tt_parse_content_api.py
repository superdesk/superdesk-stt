# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dateutil import parser as dtparse
from superdesk.io.feed_parsers import FeedParser
from superdesk.io.registry import register_feed_parser

from datetime import datetime, timezone, timedelta
import hashlib
import json
import uuid

logger = logging.getLogger(__name__)


class ContentAPITTItemParser(FeedParser):
    NAME = "stt_tt_parse_content_api"
    label = "STT TT Content API"

    def __init__(self):
        super().__init__()

    def can_parse(self, payload: Any) -> bool:
        return isinstance(payload, dict) or (
            isinstance(payload, list) and all(isinstance(i, dict) for i in payload)
        )

    def parse(self, item: Any, provider: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Parse a single dict or a list of dicts and always return a flat List[Dict]."""
        provider = provider or {}
        logger.warning("type of item: %s", type(item))
        parsed = self._parse_one(item, provider)
        if parsed:
            return parsed
        return {}

    # ------------------------ internal helpers -------------------------
    def _parse_one(self, src: Dict[str, Any], provider: dict) -> Dict[str, Any]:
        """Map a single JSON item from Content API to Superdesk item.
        Returns a dict suitable for ingest (type/pubstatus/guid/timestamps set).
        """
        if not isinstance(src, dict):
            logger.error("Parser received non-dict source: %s", type(src))
            return {}

        processed: Dict[str, Any] = dict(src)

        # Remove any keys that start with '$' as MongoDB doesn't allow them
        processed = {k: v for k, v in processed.items() if not k.startswith("$")}

        # 1) Required defaults
        processed.setdefault("type", "text")
        processed.setdefault("pubstatus", "usable")
        processed.setdefault(
            "headline", processed.get("headline") or processed.get("name") or ""
        )
        processed.setdefault(
            "body_html",
            processed.get("body_html")
            or processed.get("body_html5")
            or processed.get("body_richhtml5")
            or "",
        )

        # 2) GUID (stable when URI/_id present, else random UUID)
        if not processed.get("guid"):
            guid = self._ensure_guid(processed)
            processed["guid"] = guid

        # 3) Normalize timestamps to timezone-aware datetimes
        for tf in ("versioncreated", "firstcreated", "_updated", "_created"):
            if processed.get(tf):
                processed[tf] = self._normalize_timestamp(processed[tf])

        # Ensure versioncreated exists and is aware
        vc = processed.get("versioncreated")
        if not isinstance(vc, datetime):
            processed["versioncreated"] = datetime.now(timezone.utc)
        elif vc.tzinfo is None:
            processed["versioncreated"] = vc.replace(tzinfo=timezone.utc)

        # 4) Expiry based on provider config (hours)
        content_expiry_hours = (provider.get("config") or {}).get("content_expiry", 0)
        if content_expiry_hours:
            try:
                processed["expiry"] = processed["versioncreated"] + timedelta(
                    hours=int(content_expiry_hours)
                )
            except Exception:
                processed["expiry"] = datetime.now(timezone.utc) + timedelta(
                    hours=int(content_expiry_hours)
                )
        else:
            processed["expiry"] = None

        # Final validation: ensure we return a valid dict
        if not isinstance(processed, dict):
            logger.error("Parser produced non-dict result: %s", type(processed))
            return {}

        return processed

    def _ensure_guid(self, item: Dict[str, Any]) -> str:
        uri = (
            item.get("uri")
            or item.get("guid")
            or item.get("original_id")
            or item.get("_id")
        )
        if isinstance(uri, (str, int)):
            s = str(uri)
            return f"urn:newsml:stt.fi:stt_tt_content_api:{hashlib.sha1(s.encode('utf-8')).hexdigest()}"
        try:
            blob = json.dumps(item, ensure_ascii=False, sort_keys=True)
            h = hashlib.sha1(blob.encode("utf-8")).hexdigest()
            return f"urn:newsml:stt.fi:stt_tt_content_api:{h}"
        except Exception:
            return f"urn:newsml:stt.fi:stt_tt_content_api:{uuid.uuid4()}"

    def _normalize_timestamp(self, value: Any) -> Optional[datetime]:
        """Normalize timestamps to tz-aware datetime (UTC when naive)."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            dt = dtparse.parse(str(value))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception as ex:
            logger.warning("Failed to parse timestamp %r: %s", value, ex)
            return datetime.now(timezone.utc)


# Register like BusinessWire example: parse() returns List[Dict]
register_feed_parser(ContentAPITTItemParser.NAME, ContentAPITTItemParser())
