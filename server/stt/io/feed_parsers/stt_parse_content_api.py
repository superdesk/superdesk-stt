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


class ContentAPIItemParser(FeedParser):
    NAME = "content_api_json"
    label = "STT Content API"

    def __init__(self):
        super().__init__()

    # Be liberal in what we accept: dict (one item) or list[dict] (batch)
    def can_parse(self, payload: Any) -> bool:
        return isinstance(payload, dict) or (
            isinstance(payload, list) and all(isinstance(i, dict) for i in payload)
        )

    def parse(self, item: Any, provider: Optional[dict] = None) -> List[Dict[str, Any]]:
        provider = provider or {}

        if isinstance(item, list):
            out: List[Dict[str, Any]] = []
            for it in item:
                if isinstance(it, dict):
                    parsed = self._parse_one(it, provider)
                    if parsed:
                        out.append(parsed)
            return out

        if isinstance(item, dict):
            parsed_one = self._parse_one(item, provider)
            return [parsed_one] if parsed_one else []
        return []

    # ------------------------ internal helpers -------------------------
    def _parse_one(self, src: Dict[str, Any], provider: dict) -> Dict[str, Any]:
        """Map a single JSON item from Content API to Superdesk item.
        Returns a dict suitable for ingest (type/pubstatus/guid/timestamps set).
        """
        processed: Dict[str, Any] = dict(src)

        # 1) Optional field mapping from provider.config.field_mapping
        field_mapping = (provider.get("config") or {}).get("field_mapping") or {}
        if isinstance(field_mapping, dict) and field_mapping:
            try:
                mapped = self._apply_field_mapping(src, field_mapping)
                processed.update(mapped)
            except Exception as ex:
                logger.warning("Field mapping failed: %s", ex)

        # 2) Required defaults
        processed.setdefault("type", "text")
        processed.setdefault("pubstatus", "usable")
        processed.setdefault(
            "headline", processed.get("headline") or processed.get("name") or ""
        )
        processed.setdefault("body_html", processed.get("body_html") or "")

        # 3) GUID (stable when URI/_id present, else random UUID)
        if not processed.get("guid"):
            guid = self._ensure_guid(processed)
            processed["guid"] = guid

        # 4) Normalize timestamps to timezone-aware datetimes
        for tf in ("versioncreated", "firstcreated", "_updated", "_created"):
            if processed.get(tf):
                processed[tf] = self._normalize_timestamp(processed[tf])

        # Ensure versioncreated exists and is aware
        vc = processed.get("versioncreated")
        if not isinstance(vc, datetime):
            processed["versioncreated"] = datetime.now(timezone.utc)
        elif vc.tzinfo is None:
            processed["versioncreated"] = vc.replace(tzinfo=timezone.utc)

        # 5) Expiry based on provider config (hours)
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
            return f"urn:newsml:stt.fi:contentapi:{hashlib.sha1(s.encode('utf-8')).hexdigest()}"
        try:
            blob = json.dumps(item, ensure_ascii=False, sort_keys=True)
            h = hashlib.sha1(blob.encode("utf-8")).hexdigest()
            return f"urn:newsml:stt.fi:contentapi:{h}"
        except Exception:
            return f"urn:newsml:stt.fi:contentapi:{uuid.uuid4()}"

    def _apply_field_mapping(
        self, src: Dict[str, Any], mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Apply field mapping from source to target format (dot-path aware)."""

        def _get_by_path(obj: Any, path: str) -> Any:
            cur: Any = obj
            for part in path.split("."):
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    return None
            return cur

        def _set_by_path(dst: Dict[str, Any], path: str, value: Any) -> None:
            parts = path.split(".")
            node = dst
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = value

        out: Dict[str, Any] = {}
        for target, source in (mapping or {}).items():
            if not isinstance(target, str) or not isinstance(source, str):
                continue
            val = _get_by_path(src, source)
            if val is not None:
                _set_by_path(out, target, val)
        return out

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
register_feed_parser(ContentAPIItemParser.NAME, ContentAPIItemParser())
