from __future__ import annotations


import logging
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Dict, Iterable, List
from superdesk.io.registry import register_feeding_service
from .stt_content_api import STTContentAPIService as BaseSTTContentAPIService
from superdesk.errors import ParserError

logger = logging.getLogger(__name__)


class STTTTContentAPIService(BaseSTTContentAPIService):
    """
    TT-specific Content API Service that uses ApiKey authentication and
    handles 'hits' response format. Inherits most functionality from the base
    STTContentAPIService but overrides specific methods.
    """

    NAME = "stt_tt_content_api"
    # Ensure the TT parser is used even if provider.feed_parser is unset
    FEED_PARSER = "stt_tt_parse_content_api"
    label = "STT TT Content API"

    def _headers(self, api_key: str) -> Dict[str, str]:
        """Generate headers for TT Content API requests using ApiKey
        instead of Bearer."""
        auth_header = api_key if api_key.startswith("ApiKey ") else f"ApiKey {api_key}"
        return {
            "Accept": "application/json",
            "Authorization": auth_header,
        }

    fields = [
        {
            "id": "url",
            "type": "text",
            "label": "Items URL",
            "placeholder": "https://<host>/contentapi/items",
            "required": True,
        },
        {
            "id": "api_key",
            "type": "text",
            "label": "API Key (ApiKey or raw token)",
            "placeholder": "ApiKey <token> OR raw <token>",
            "required": True,
        },
        {
            "id": "page_size",
            "type": "text",
            "label": "Page size (s)",
            "placeholder": "50",
            "required": False,
            "default": "50",
            "description": (
                "Number of items to request per page from TT Content API "
                "(query param s). Range: 1-1000."
            ),
        },
        {
            "id": "max_pages",
            "type": "text",
            "label": "Max pages",
            "placeholder": "200",
            "required": False,
            "default": "200",
            "description": (
                "Safety cap for the number of pages to fetch when "
                "paginating. Range: 1-10000."
            ),
        },
        {
            "id": "timeout",
            "type": "text",
            "label": "Request timeout (seconds)",
            "placeholder": "300",
            "required": False,
            "default": "300",
            "description": (
                "HTTP request timeout per page when calling TT Content API."
            ),
        },
    ]

    def _update(self, provider, update) -> Iterable[Dict]:
        """
        TT-specific update that fetches all pages and yields parsed dict items.
        """
        json_items = self._fetch_tt_data(provider)
        if not isinstance(json_items, list):
            json_items = [json_items]

        parsed_items: List[Dict] = []

        # Resolve parser once
        parser = self.get_feed_parser(provider)

        for item in json_items:
            try:
                if not isinstance(item, dict):
                    continue

                parsed_result = parser.parse(item, provider)
                # Only return dict items to the ingest pipeline
                if isinstance(parsed_result, list):
                    parsed_items.extend(
                        [x for x in parsed_result if isinstance(x, dict)]
                    )
                elif isinstance(parsed_result, dict):
                    parsed_items.append(parsed_result)
                else:
                    pass
            except Exception as ex:
                logger.error("Error processing item: %s", str(ex))
                raise ParserError.parseMessageError(ex, provider, data=item)

        # Final guard: ensure only dicts are returned
        # (avoids filter_expired_items crash)
        parsed_items = [it for it in parsed_items if isinstance(it, dict)]
        return parsed_items

    def _fetch_tt_data(self, provider) -> List[Dict]:
        """
        Fetch all items from TT Content API with pagination.
        Uses `s` (page size) and `fr` (offset) according to docs, and the
        `total` field when available to determine how many pages to request.

        Provider optional settings:
          - page_size: int (default 50)
          - max_pages: int safety cap (default 200)
          - timeout: int per-request timeout (default 300)
        """
        url, api_key = self._get_config(provider)
        headers = self._headers(api_key)

        config = provider.get("config", {})
        page_size = int(config.get("page_size", 50))
        max_pages = int(config.get("max_pages", 200))
        # safety cap to avoid runaway loops
        timeout = int(config.get("timeout", 300))

        # Prepare base URL components and preserve existing query params
        parsed = urlparse(url)
        base_qs = dict(parse_qsl(parsed.query, keep_blank_values=True))

        items: List[Dict] = []
        offset = 0
        total = None

        for page in range(max_pages):
            # Merge/override pagination params each loop
            qs = {**base_qs, "s": str(page_size), "fr": str(offset)}
            page_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

            # Use base class HTTP retry infrastructure
            response = self._get_with_retry(page_url, headers=headers, timeout=timeout)
            response.raise_for_status()

            # Use base class JSON parsing with error handling
            data = self._safe_json(response, provider)

            if total is None and isinstance(data, dict):
                # `total` may not always be present; handle gracefully
                total = data.get("total")

            batch = self._extract_tt_items_from_response(data)

            # Normalize and collect dict items only
            if isinstance(batch, list) and batch:
                items.extend([it for it in batch if isinstance(it, dict)])
            else:
                # No more results
                break

            offset += page_size

            # Stop if we've fetched all known results
            if isinstance(total, int) and offset >= total:
                break

        # Final guard: return only dicts
        return [it for it in items if isinstance(it, dict)]

    def _extract_tt_items_from_response(self, data) -> List:
        """
        Extract items from TT API response, specifically handling 'hits'
        property. This is the main difference from the base class - TT API
        returns data in 'hits'.
        """
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            hits = data.get("hits", [])
            if isinstance(hits, dict):
                return list(hits.values())
            return hits
        else:
            return []


register_feeding_service(STTTTContentAPIService)
