# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013-2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from __future__ import annotations


import logging
from datetime import datetime
from typing import Dict, Iterable, List, Any
import requests

from superdesk.errors import IngestApiError, ParserError
from superdesk.io.registry import register_feeding_service
from superdesk.io.feeding_services.http_base_service import HTTPFeedingServiceBase

# Processing items directly in feeding service to avoid parser discovery issues

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
        {
            "id": "max_results",
            "type": "number",
            "label": "Page size",
            "placeholder": "25",
        },
        {
            "id": "timeout",
            "type": "number",
            "label": "HTTP timeout (sec)",
            "placeholder": "20",
        },
        {
            "id": "field_mapping",
            "type": "json",
            "label": "Field Mapping (JSON)",
            "placeholder": '{"headline": "headline", "body_html": "body_html"}',
            "required": False,
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

    def _build_params(
        self, since_iso: str, page: int, max_results: int
    ) -> Dict[str, Any]:
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
        # Avoid logging sensitive details; only log target URL
        logger.warning("Testing Content API connectivity to %s", url)
        headers = self._headers(api_key)
        params = {"page": 1, "max_results": 1}
        self.get_url(url, params=params, headers=headers)

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
        """
        Reads pages of items using ?where[versioncreated]>last_update ordering by versioncreated.
        Accepts both array and {_items:[...]} response shapes.
        """
        logger.warning("fetching data ...")
        config = provider.get("config", {})
        url: str = config["url"]
        api_key: str = config["api_key"]
        max_results: int = int(config.get("max_results", 25))
        timeout: int = int(config.get("timeout", 20))

        logger.info(
            "Starting Content API fetch from %s (since: %s, page_size: %d, timeout: %ds)",
            url,
            since_iso or "beginning",
            max_results,
            timeout,
        )

        headers = self._headers(api_key)

        items: List[Dict] = []
        page = 1

        while True:
            params = self._build_params(since_iso, page, max_results)
            logger.debug(
                "Requesting page %d with params: %s",
                page,
                {k: v for k, v in params.items() if k != "where"},
            )

            try:
                response = requests.get(
                    url, params=params, headers=headers, timeout=timeout
                )
                status = response.status_code
                if status >= 400:
                    logger.warning(
                        "Content API HTTP %s on page %d. Body: %s",
                        status,
                        page,
                        response.text[:1000],
                    )
                    raise IngestApiError.apiGeneralError(
                        Exception(f"HTTP {status} from Content API"), provider
                    )
                logger.info(
                    "Successfully fetched page %d with %d max_results from Content API (status: %d)",
                    page,
                    max_results,
                    status,
                )
            except IngestApiError:
                # Already wrapped with provider context
                raise
            except Exception as ex:
                logger.error(
                    "Failed to fetch page %d from Content API: %s", page, str(ex)
                )
                raise IngestApiError.apiGeneralError(ex, provider)

            try:
                data = response.json() or {}
            except Exception as json_ex:
                # Surface raw text on JSON parse failure with better error context
                logger.error(
                    "Failed to parse JSON response from Content API (status: %d, content-type: %s)",
                    response.status_code,
                    response.headers.get("content-type", "unknown"),
                )
                logger.debug("Response text (first 500 chars): %s", response.text[:500])
                raise IngestApiError.apiGeneralError(
                    Exception(f"JSON parse error: {str(json_ex)}"), provider
                )

            batch = (
                data
                if isinstance(data, list)
                else data.get("_items") or data.get("items") or []
            )

            if isinstance(batch, dict):
                # dict-of-id -> item
                batch_list = [v for v in batch.values() if isinstance(v, dict)]
            elif isinstance(batch, list):
                batch_list = [v for v in batch if isinstance(v, dict)]
            else:
                batch_list = []

            # Ensure batch_list contains only dicts (already filtered above)
            batch_list = [item for item in batch_list if isinstance(item, dict)]

            if not batch_list:
                break

            items.extend(batch_list)

            # Stop if there is no next link and we've filled a single page
            has_next = False
            links = data.get("_links") if isinstance(data, dict) else None
            if isinstance(links, dict):
                has_next = "next" in links

            meta = data.get("_meta") if isinstance(data, dict) else None
            total = meta.get("total") if isinstance(meta, dict) else None

            if (not has_next) and (total is None or page * max_results >= int(total)):
                break

            page += 1
            if page == 2:
                break

        logger.info(
            "Content API fetch completed: %d items retrieved from %d pages",
            len(items),
            page - 1,
        )
        return items


register_feeding_service(STTContentAPIService)
