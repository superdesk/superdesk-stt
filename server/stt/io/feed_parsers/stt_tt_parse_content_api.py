# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import inspect

from superdesk.io.registry import register_feed_parser
from .stt_parse_content_api import ContentAPIItemParser

logger = logging.getLogger(__name__)


class ContentAPITTItemParser(ContentAPIItemParser):
    NAME = "stt_tt_parse_content_api"
    label = "STT TT Content API"

    async def parse(
        self, item: Any, provider: Optional[dict] = None
    ) -> List[Dict[str, Any]]:
        """
        TT-specific parse method for single item or list processing by the
        feeding service. This MUST return a List[Dict] to comply with Superdesk
        ingest expectations. Async to match the base class contract.
        """
        provider = provider or {}

        # Helper to handle sync/async _parse_one uniformly
        async def _parse_one_maybe_async(
            elem: Dict[str, Any],
        ) -> Optional[Dict[str, Any]]:
            result = self._parse_one(elem, provider)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, dict) and result:
                return result
            return None

        # Case 1: payload is a dict - parse one and return a single-item list
        if isinstance(item, dict):
            parsed = await _parse_one_maybe_async(item)
            return [parsed] if parsed else []

        # Case 2: payload is a list - parse each dict item, ignore non-dicts
        if isinstance(item, list):
            results: List[Dict[str, Any]] = []
            for idx, elem in enumerate(item):
                if not isinstance(elem, dict):
                    continue
                parsed = await _parse_one_maybe_async(elem)
                if parsed is not None:
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
        # Guarantee downstream consumers always receive a GUID
        return processed


# Register like BusinessWire example: parse() returns List[Dict[str, Any]]
register_feed_parser(ContentAPITTItemParser.NAME, ContentAPITTItemParser())
