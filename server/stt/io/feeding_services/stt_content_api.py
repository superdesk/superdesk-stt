from __future__ import annotations


import logging
from datetime import datetime
from typing import Dict, Iterable, List, Any
import requests

from superdesk.errors import IngestApiError, ParserError
from superdesk.io.registry import register_feeding_service
from superdesk.io.feeding_services.http_base_service import HTTPFeedingServiceBase


logger = logging.getLogger(__name__)

utcfromtimestamp = datetime.utcfromtimestamp


class STTContentAPIService(HTTPFeedingServiceBase):
    """
    Feeding Service for Superdesk-compatible Content API (/contentapi/items).
    Simple, Bearer-authorized fetch with incremental since filtering.
    """

    NAME = "stt_content_api"
    ERRORS = [ParserError.parseMessageError().get_error_description()]

    label = "STT Content API"
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

    # ------------------------------ helpers ------------------------------

    def _bearer(self, api_key: str) -> str:
        if api_key.startswith("Bearer "):
            return api_key
        return f"Bearer {api_key}"

    def _headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": self._bearer(api_key),
        }

    def _build_params(self, since_iso: str, page: int) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "page": page,
        }
        return params

    # ------------------------------ lifecycle ------------------------------

    def _test(self, provider):
        """
        Make a tiny request to validate URL + Authorization.
        """
        config = (provider or {}).get("config") or self.config or {}
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
        logger.warning("Updating content API ...")
        last_update_dt = provider.get("last_updated") or utcfromtimestamp(0)
        if isinstance(last_update_dt, datetime):
            since_iso = last_update_dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            since_iso = ""

        json_items = self._fetch_data(provider, since_iso)
        parsed_items = []

        for item in json_items:
            try:
                # Process items directly to avoid parser discovery issues
                parsed_result = self.get_feed_parser(provider, item).parse(
                    item, provider
                )
                # Parser returns a list, so extend instead of append
                if isinstance(parsed_result, list):
                    parsed_items.extend(parsed_result)
                else:
                    parsed_items.append(parsed_result)
            except Exception as ex:
                logger.error("Error processing item: %s", str(ex))
                raise ParserError.parseMessageError(ex, provider, data=item)

        return parsed_items

    def _fetch_data(self, provider, since_iso: str) -> List[Dict]:
        logger.warning("fetching data ...")
        config = provider.get("config", {})
        url = config["url"]
        api_key = config["api_key"]
        headers = self._headers(api_key)

        logger.info(
            "Starting Content API fetch from %s (since: %s)",
            url,
            since_iso or "beginning",
        )

        all_items = []
        page = 1
        while True:
            try:
                response = requests.get(
                    url,
                    params=self._build_params(since_iso, page),
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                data = self._safe_json(response, provider)
                batch = self._extract_batch(data)
                if not batch:
                    break
                all_items.extend(batch)
                if not self._has_next_page(data):
                    break
                page += 1
            except IngestApiError:
                raise
            except Exception as ex:
                logger.error(
                    "Failed to fetch page %d from Content API: %s", page, str(ex)
                )
                raise IngestApiError.apiGeneralError(ex, provider)
        return all_items

    def _safe_json(self, response, provider) -> Any:
        try:
            return response.json() or {}
        except Exception as ex:
            logger.error(
                "Failed to parse JSON from Content API (status: %d, content-type: %s)",
                response.status_code,
                response.headers.get("content-type", "unknown"),
            )
            raise IngestApiError.apiGeneralError(
                Exception(f"JSON parse error: {ex}"), provider
            )

    def _extract_batch(self, data: Any) -> List[Dict]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            raw = data.get("_items") or data.get("items") or data
            if isinstance(raw, dict):
                return [v for v in raw.values() if isinstance(v, dict)]
            if isinstance(raw, list):
                return [v for v in raw if isinstance(v, dict)]
        return []

    def _has_next_page(self, data: Any) -> bool:
        links = data.get("_links") if isinstance(data, dict) else None
        return isinstance(links, dict) and "next" in links


register_feeding_service(STTContentAPIService)
