from __future__ import annotations


import logging
from datetime import datetime
from typing import Dict, Iterable, List
import requests

from superdesk.errors import IngestApiError, ParserError
from superdesk.io.registry import register_feeding_service
from superdesk.io.feeding_services.http_base_service import HTTPFeedingServiceBase
from stt.io.feed_parsers.stt_tt_parse_content_api import ContentAPITTItemParser


logger = logging.getLogger(__name__)

utcfromtimestamp = datetime.utcfromtimestamp


class STTContentAPIService(HTTPFeedingServiceBase):
    """
    Feeding Service for Superdesk-compatible Content API (/tt/contentapi/items).
    Simple, Bearer-authorized fetch with incremental since filtering.
    """

    NAME = "stt_tt_content_api"
    ERRORS = [ParserError.parseMessageError().get_error_description()]

    label = "STT TT Content API"
    HTTP_AUTH = False

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
            "label": "API Key (Bearer or raw token)",
            "placeholder": "Bearer <token> OR raw <token>",
            "required": True,
        },
    ]

    def __init__(self):
        super().__init__()

    def _headers(self, api_key: str) -> Dict[str, str]:
        """Generate headers for TT Content API requests."""
        auth_header = api_key if api_key.startswith("ApiKey ") else f"ApiKey {api_key}"
        return {
            "Accept": "application/json",
            "Authorization": auth_header,
        }

    def _test(self, provider):
        """Validate URL and API key by making a test request."""
        config = (provider or {}).get("config", {})
        url = config.get("url")
        api_key = config.get("api_key")

        if not url or not api_key:
            raise ParserError.parseMessageError(
                Exception("Missing url or api_key in provider.config"),
                provider,
                data={"url": url, "has_api_key": bool(api_key)},
            )

        headers = self._headers(api_key)
        self.get_url(url, headers=headers)

    def _update(self, provider, update) -> Iterable[Dict]:
        """
        Fetch pages from the Content API, parse items with the configured parser,
        and return a flat list of parsed dicts.
        """
        json_items = self._fetch_data(provider)
        parser = ContentAPITTItemParser()
        parsed_items = []

        for item in json_items:
            try:
                # Use our dedicated parser directly to avoid discovery issues
                parsed_result = parser.parse(item, provider)

                if isinstance(parsed_result, dict):
                    parsed_items.append(parsed_result)
                else:
                    logger.error(
                        "Parser returned unexpected type (should be list): %s",
                        type(parsed_result),
                    )
            except Exception as ex:
                logger.error("Error processing item: %s", str(ex))
                raise ParserError.parseMessageError(ex, provider, data=item)

        if isinstance(parsed_items, list):
            yield parsed_items
        else:
            yield [parsed_items]

    def _fetch_data(self, provider) -> List[Dict]:
        """Fetch items from the TT Content API endpoint."""
        config = provider.get("config", {})
        url = config["url"]
        api_key = config["api_key"]
        headers = self._headers(api_key)

        response = requests.get(url, headers=headers, timeout=300)
        if response.status_code >= 400:
            raise IngestApiError.apiGeneralError(
                Exception(f"HTTP {response.status_code} from TT Content API"), provider
            )

        try:
            data = response.json() or {}
        except Exception as json_ex:
            raise IngestApiError.apiGeneralError(
                Exception(f"JSON parse error: {str(json_ex)}"), provider
            )
        # logger.warning("Data: %s", data.get("hits"))
        logger.warning("type: %s", type(data))
        # Extract items from response (handles both direct list and {hits: []} formats)
        items = self._extract_items_from_response(data)
        return [item for item in items if isinstance(item, dict)]

    def _extract_items_from_response(self, data) -> List:
        """Extract items from API response, handling different response formats."""
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            hits = data.get("hits", [])
            if isinstance(hits, dict):
                return list(hits.values())
            return hits
        else:
            return []


register_feeding_service(STTContentAPIService)
