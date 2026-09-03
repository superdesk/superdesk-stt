from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple
import email.utils
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp

from superdesk.errors import IngestApiError, ParserError
from superdesk.io.registry import register_feeding_service
from superdesk.io.feeding_services.http_base_service import HTTPFeedingServiceBase


logger = logging.getLogger(__name__)

utcfromtimestamp = datetime.utcfromtimestamp

# Maximum number of retries for transient errors (429/5xx). This is retries, not attempts.
MAX_RETRIES = 3
# Base seconds for exponential backoff (1, 2, 4, ...)
BACKOFF_BASE = 1.0
RETRY_STATUSES = {429, *range(500, 600)}
RETRY_METHODS = {"HEAD", "GET", "OPTIONS"}


def _get_retry_delay(attempt: int, header_value: str | None) -> float:
    if not header_value:
        return BACKOFF_BASE * (2**attempt)

    # Retry-After can be either seconds or an HTTP date
    try:
        return max(0.0, float(header_value))
    except ValueError:
        pass

    try:
        retry_at = email.utils.parsedate_to_datetime(header_value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return BACKOFF_BASE * (2**attempt)


class STTContentAPIService(HTTPFeedingServiceBase):
    """
    Feeding Service for Superdesk-compatible Content API (/contentapi/items).
    Simple, Bearer-authorized fetch with incremental since filtering.
    """

    NAME = "stt_content_api"
    # Ensure the correct parser is used even if provider.feed_parser is unset
    FEED_PARSER = "content_api_json"
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

    def _get_config(self, provider) -> Tuple[str, str]:
        """Validate and return (url, api_key) from provider config.

        Raises ParserError on misconfiguration to make issues visible in ingest UI.
        """
        config = (provider or {}).get("config") or {}
        url = config.get("url")
        api_key = config.get("api_key")
        if not url or not api_key:
            raise ParserError.parseMessageError(
                "Missing url or api_key in provider.config",
                provider,
                data={"url": url, "has_api_key": bool(api_key)},
            )
        return url, api_key

    def _build_params(self, since_iso: str, page: int) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "page": page,
        }
        return params

    # ------------------------------ HTTP helpers ------------------------------

    @asynccontextmanager
    async def _get_with_retry(
        self,
        provider: dict,
        url: str | None = None,
        *,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        base_url, api_key = self._get_config(provider)
        headers = self._headers(api_key)
        url = url or base_url

        session = await self.http_session()
        last_exc: BaseException | None = None

        http_timeout: aiohttp.ClientTimeout
        if timeout is not None:
            http_timeout = aiohttp.ClientTimeout(timeout)
        else:
            http_timeout = self.http_timeout

        # urllib3 Retry.total is "number of retries", so attempts = retries + 1
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with session.get(
                    url, headers=headers, params=params, timeout=http_timeout
                ) as response:
                    if response.status not in RETRY_STATUSES:
                        # This is a valid response status, return to the caller so they can
                        # use the response
                        yield response
                        return
                    elif attempt >= MAX_RETRIES:
                        # Do not retry after final attempt. Yield it so the caller can call
                        # raise_for_status() and handle the final HTTP error normally.
                        yield response
                        return

                    delay = _get_retry_delay(
                        attempt, response.headers.get("Retry-After")
                    )
                    logger.warning(
                        "GET %s returned retryable status %s; retrying in %.2fs (attempt %d/%d)",
                        url,
                        response.status,
                        delay,
                        attempt + 1,
                        MAX_RETRIES,
                    )

                # Important: sleep after exiting `async with session.get(...)`,
                # so the retryable response is already released before waiting.
                await asyncio.sleep(delay)

            except (
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientPayloadError,
                asyncio.TimeoutError,
            ) as exc:
                last_exc = exc

                if attempt >= MAX_RETRIES:
                    raise

                delay = BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "GET %s failed with %s; retrying in %.2fs (attempt %d/%d)",
                    url,
                    type(exc).__name__,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)

        if last_exc:
            raise last_exc

        raise RuntimeError("Unexpected retry loop exit")

    # ------------------------------ lifecycle ------------------------------

    async def _test(self, provider: dict) -> None:
        """
        Make a tiny request to validate URL + Authorization.
        """
        # Use the provider passed by the runner; avoid accessing self.config here
        # because self.provider may not be set yet by the framework
        # Small request to validate; reuses retry helper for robustness
        async with self._get_with_retry(provider) as response:
            response.raise_for_status()

    async def _update(self, provider, update) -> Iterable[Iterable[Dict]]:
        """
        Fetch pages from the Content API, parse items with the configured parser,
        and return a flat list of parsed dicts.
        """
        logger.info(
            "Updating Content API provider %s ...", provider.get("name", "<unnamed>")
        )
        last_update_dt = provider.get("last_updated") or utcfromtimestamp(0)
        if isinstance(last_update_dt, datetime):
            since_iso = last_update_dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            since_iso = ""

        json_items = await self._fetch_data(provider, since_iso)
        parsed_items = []

        for item in json_items:
            try:
                # Get the configured parser for this provider and parse the item
                parser = await self.get_feed_parser(provider)
                if not isinstance(item, dict):
                    logger.warning(
                        "Skipping non-dict JSON item before parse: %r (type: %s)",
                        item,
                        type(item).__name__,
                    )
                    continue

                parsed_result = await parser.parse(item, provider)
                # Only return dict items to the ingest pipeline
                if isinstance(parsed_result, list):
                    parsed_items.extend(
                        [x for x in parsed_result if isinstance(x, dict)]
                    )
                elif isinstance(parsed_result, dict):
                    parsed_items.append(parsed_result)
                else:
                    logger.warning(
                        "Dropping non-dict parsed item (type=%s)",
                        type(parsed_result).__name__,
                    )
            except Exception as ex:
                logger.error("Error processing item: %s", str(ex))
                raise ParserError.parseMessageError(ex, provider, data=item)

        # Final guard: ensure only dicts are returned (avoids filter_expired_items crash)
        parsed_items = [it for it in parsed_items if isinstance(it, dict)]
        return [parsed_items]

    async def _fetch_data(self, provider: dict, since_iso: str) -> list[dict]:
        logger.debug("Fetching data from Content API ...")
        url, _ = self._get_config(provider)

        logger.info(
            "Starting Content API fetch from %s (since: %s)",
            url,
            since_iso or "beginning",
        )

        all_items = []
        page = 1
        while True:
            try:
                params = self._build_params(since_iso, page)
                # Optionally include a since parameter if configured on provider
                cfg = (provider or {}).get("config") or {}
                since_param = cfg.get("since_param")
                if since_param and since_iso:
                    params[since_param] = since_iso

                async with self._get_with_retry(provider, params=params) as response:
                    response.raise_for_status()
                    data = await self._safe_json(response, provider)

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

    async def _safe_json(
        self, response: aiohttp.ClientResponse, provider: dict
    ) -> Any:
        try:
            data = await response.json()
            return data if data is not None else {}
        except Exception as ex:
            logger.error(
                "Failed to parse JSON from Content API (status: %d, content-type: %s)",
                response.status,
                response.headers.get("content-type", "unknown"),
            )
            parse_error = Exception(f"JSON parse error: {ex}")
            raise IngestApiError.apiGeneralError(parse_error, provider)

    def _extract_batch(self, data: Any) -> List[Dict]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            raw = (
                data.get("_items")
                or data.get("items")
                or data.get("results")
                or data.get("docs")
                or data
            )
            if isinstance(raw, dict):
                return [v for v in raw.values() if isinstance(v, dict)]
            if isinstance(raw, list):
                return [v for v in raw if isinstance(v, dict)]
        return []

    def _has_next_page(self, data: Any) -> bool:
        links = data.get("_links") if isinstance(data, dict) else None
        return isinstance(links, dict) and "next" in links


register_feeding_service(STTContentAPIService)
