# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from superdesk.io.registry import register_feed_parser
from .stt_parse_content_api import ContentAPIItemParser

logger = logging.getLogger(__name__)


class ContentAPITTItemParser(ContentAPIItemParser):
    NAME = "stt_tt_parse_content_api"
    label = "STT TT Content API"

    def can_parse(self, payload: Any) -> bool:
        return isinstance(payload, dict) or (
            isinstance(payload, list) and all(isinstance(i, dict) for i in payload)
        )

    def parse(self, item: Any, provider: Optional[dict] = None) -> List[Dict[str, Any]]:
        """
        TT-specific parse method for single item or list processing by the
        feeding service. This MUST return a List[Dict] to comply with Superdesk
        ingest expectations.
        """
        provider = provider or {}

        # Case 1: payload is a dict - parse one and return a single-item list
        # (or empty if invalid)
        if isinstance(item, dict):
            parsed = self._parse_one(item, provider)
            if isinstance(parsed, dict) and parsed:
                return [parsed]
            return []

        # Case 2: payload is a list - parse each dict item,
        # ignore non-dicts
        if isinstance(item, list):
            results: List[Dict[str, Any]] = []
            for idx, elem in enumerate(item):
                if not isinstance(elem, dict):
                    continue
                parsed = self._parse_one(elem, provider)
                if isinstance(parsed, dict) and parsed:
                    results.append(parsed)
            return results
        return []

    # ------------------------ TT-specific overrides -------------------------
    def _parse_one(self, src: Dict[str, Any], provider: dict) -> Dict[str, Any]:
        """
        TT-specific parsing that extends base class functionality.
        Adds TT-specific preprocessing and uses custom GUID generation.
        """
        if not isinstance(src, dict):
            logger.error("TT Parser received non-dict source: %s", type(src))
            return {}

        # TT-specific: Remove MongoDB incompatible keys first
        cleaned_src = {k: v for k, v in src.items() if not k.startswith("$")}

        # Use base class parsing for most functionality
        processed = super()._parse_one(cleaned_src, provider)

        # Validate base class returned proper dict
        if not processed:
            return {}

        if not isinstance(processed, dict):
            logger.error(
                "Base class _parse_one returned non-dict: type=%s, value=%s",
                type(processed),
                processed,
            )
            return {}

        # TT-specific: Additional body_html fallbacks
        if not processed.get("body_html"):
            processed["body_html"] = (
                processed.get("body_html5") or processed.get("body_richhtml5") or ""
            )

        body_html = processed.get("body_html")
        if not isinstance(body_html, str):
            processed["body_html"] = ""
        else:
            processed["body_html"] = body_html or ""
        return processed

    def _ensure_guid(self, item: Dict[str, Any]) -> str:
        """Ensure GUIDs use the TT-specific namespace when auto-generated."""
        base_guid = super()._ensure_guid(item)
        if not isinstance(base_guid, str):
            return base_guid

        tt_prefix = "urn:newsml:stt.fi:stt_tt_content_api:"
        default_prefix = "urn:newsml:stt.fi:contentapi:"

        if base_guid.startswith(tt_prefix):
            return base_guid
        if base_guid.startswith(default_prefix):
            return tt_prefix + base_guid[len(default_prefix) :]
        if base_guid.startswith("urn:"):
            return base_guid
        return tt_prefix + base_guid


# Register like BusinessWire example: parse() returns List[Dict[str, Any]]
register_feed_parser(ContentAPITTItemParser.NAME, ContentAPITTItemParser())
