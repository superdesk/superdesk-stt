import datetime
import inspect
import json
import os
import logging
import requests
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

from superdesk.errors import IngestApiError
from superdesk.io.feed_parsers.ninjs import NINJSFeedParser
from superdesk.io.feeding_services.http_service import HTTPFeedingService
from superdesk.io.registry import (
    register_feed_parser,
    register_feeding_service,
    register_feeding_service_parser,
)

logger = logging.getLogger(__name__)


def strip_text(value: Optional[str]) -> str:
    """Whitespace-trimmed helper that tolerates ``None`` inputs."""
    return (value or "").strip()


class STTSinceNINJSFeedParser(NINJSFeedParser):
    """Custom NinJS parser that enriches results with STT-specific metadata."""

    NAME = "stt_since_ninjs"
    label = "STT Since NinJS Feed Parser"

    def _transform_from_ninjs(self, ninjs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise the incoming NinJS payload and attach STT vocab mappings."""
        item = super()._transform_from_ninjs(ninjs)
        anpa_category = ninjs.get("anpa_category")
        if isinstance(anpa_category, dict):
            item["anpa_category"] = [anpa_category]
        subject: List[Dict[str, Any]] = []
        # Raw data "topics" should be valid as is
        topics = ninjs.get("topics")
        if topics:
            subject.extend(topics)
        # Raw data "sttsource" should be valid as is
        stt_sources = ninjs.get("sttsource")
        if stt_sources:
            subject.extend(stt_sources)
        # When subject is added with topics and sttsource => archive item will get that metadata from ingest
        if subject:
            item["subject"] = subject
        return item

    def datetime(self, value: Any):
        """Parse ISO-8601 datetimes with optional colon offsets into UTC."""

        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.timezone.utc)
            return value.astimezone(datetime.timezone.utc)

        text = strip_text(value)
        if not text:
            return super().datetime(value)

        try:
            candidate = text.replace("Z", "+00:00")
            parsed = datetime.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed.astimezone(datetime.timezone.utc)
        except Exception:
            return super().datetime(value)


class STTWithSinceHTTPFeedingService(HTTPFeedingService):
    """
    STT results ingest over HTTP with since-cursor semantics.

    Parser: This feeding service always uses the NINJS Feed Parser (id: "ninjs")
    regardless of the Source configuration.
    """

    NAME = "stt_since_http"
    label = "STT Sport Results API"
    fields = [
        {
            "id": "url",
            "type": "text",
            "label": "Feed URL",
            "placeholder": "Feed URL",
            "required": True,
        },
        {
            "id": "auth_token",
            "type": "password",
            "label": "Auth Token",
            "placeholder": "Auth token",
            "required": True,
        },
    ]
    ERRORS = [
        IngestApiError.apiTimeoutError().get_error_description(),
        IngestApiError.apiRedirectError().get_error_description(),
        IngestApiError.apiRequestError().get_error_description(),
        IngestApiError.apiUnicodeError().get_error_description(),
        IngestApiError.apiParseError().get_error_description(),
        IngestApiError.apiGeneralError().get_error_description(),
    ]

    session = None
    auth_token = None

    # Parser is bound via registry to NinJS (see registration at bottom of file)

    async def _update(self, provider, update):
        """Fetch and parse a provider update, yielding a single batch of NinJS items.

        This generator:
        - Validates that self.auth_token contains an auth token.
        - Initializes an HTTP session and fetches update data for the given provider.
        - Obtains a feed parser and incrementally parses the response content via the NinJS parser.
        - Yields exactly once: a list of parsed items. If parsing returns a single item, it is wrapped in a list.

        Parameters:
            provider: A dict-like provider descriptor. Must contain a "config" mapping with an "auth_token".
            update: Provider-specific cursor/marker (e.g., "since" token, timestamp, or offset) used by the fetch call.

        Yields:
            list: A single list containing the parsed NinJS items.

        Raises:
            IngestApiError: If the provider configuration lacks an auth token.
            Exception: Any error propagated from fetching or parsing (e.g., network errors, parsing failures).

        Side Effects:
            Assigns an initialized requests.Session to self.session for HTTP operations.
        """

        # Pick up the auth token from the provider configuration for this run
        self.auth_token = provider.get("config", {}).get("auth_token")
        if not self.auth_token:
            raise IngestApiError(
                "MISSING_AUTH_TOKEN",
                "Auth token is required but not set in provider configuration.",
            )
        parser = await self.get_feed_parser(provider)
        items = []
        self.session = requests.Session()
        response = self.fetch(provider, update)

        # Parse by feeding one item at a time to the NinJS parser
        content = response.content or b""
        items = await self._parse_items_via_ninjs(parser, content, provider)

        if isinstance(items, list):
            yield items
        else:
            yield [items]

    def _build_url(self, provider):
        """
        Build a request URL by appending a since query parameter based on the provider's last_updated timestamp.

        The since value is taken from provider["last_updated"]. If it is missing or None, the current UTC time
        is used. The timestamp is formatted as ISO 8601 and normalized to use the 'Z' suffix for UTC
        (e.g., 2024-01-02T03:04:05Z). If the base URL already contains query parameters, '&' is used; otherwise, '?'.

        Parameters:
        - provider (dict): Mapping with:
            - "config": {"url": str} — Base endpoint URL.
            - "last_updated" (datetime.datetime | None, optional) — Last updated timestamp (timezone-aware preferred).

        Returns:
        - str: The URL with the appended since=<ISO-8601-Z> query parameter.

        Side effects:
        - Emits warnings to the logger about the last_updated value and when defaulting to the current time.

        Raises:
        - TypeError or AttributeError if required keys are missing or have unexpected types
            (e.g., non-string URL or non-datetime last_updated).
        """
        base = provider.get("config", {}).get("url")
        since = provider.get("last_updated")
        logger.info("Last updated: {}".format(since))
        if since is None:
            # if since is not set, set it to now
            logger.warning("No last updated, using now as since")
            since = datetime.datetime.now(datetime.timezone.utc)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}since={since.isoformat().replace('+00:00','Z')}"

    def fetch(self, provider, update):
        """
        Fetch data from the provider endpoint using an authenticated GET request.

        Builds the request URL from the provided provider configuration, attaches a Bearer
        token from self.auth_token, and issues the request using self.session. Logs the
        target URL at WARNING level. The response status is validated via raise_for_status(),
        and the full requests.Response object is returned so callers can access .content,
        .json(), headers, etc.

        Args:
            provider (Mapping[str, Any]): Provider configuration. If 'timeout' (seconds)
                is provided, it overrides the request timeout (default: 30).
            update (Any): Unused placeholder to conform to the feeder interface.

        Returns:
            requests.Response: The HTTP response object from the provider.

        Raises:
            requests.exceptions.HTTPError: If the HTTP response indicates an error status.
            requests.exceptions.RequestException: For network-related errors, including
                timeouts and connection issues.
        """
        url = self._build_url(provider)
        logger.info("Fetching URL: {}".format(url))
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        resp = self.session.get(
            url, headers=headers, timeout=provider.get("timeout", 30)
        )
        resp.raise_for_status()
        # return the full Response so callers can access .content as needed
        return resp

    async def _parse_items_via_ninjs(self, parser, content: bytes, provider):
        """Pass a single item at a time to the NinJS parser.

        Supports the following top-level shapes:
        - dict with a single NinJS object
        - dict with {"items": [ ... ]}
        - list of NinJS objects
        Falls back to writing the raw content to a temp file if JSON decoding fails.
        """
        try:
            data = json.loads(content)
        except Exception:
            with NamedTemporaryFile("wb", delete=True, suffix=".json") as f:
                logger.warning(
                    "Falling back to raw file parsing due to JSON decode error"
                )
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
                parsed = await self._call_parser(parser, f.name, provider)
            if isinstance(parsed, list):
                return parsed
            if parsed is None:
                return []
            return [parsed]

        if isinstance(data, dict):
            items_list = data.get("items")
            if isinstance(items_list, list):
                iterable = items_list
            else:
                iterable = [data]
        elif isinstance(data, list):
            iterable = data
        else:
            iterable = []

        results: List[Dict[str, Any]] = []
        for obj in iterable:
            if not isinstance(obj, dict):
                continue
            with NamedTemporaryFile("w", delete=True, suffix=".json") as f:
                json.dump(obj, f)
                f.flush()
                os.fsync(f.fileno())
                parsed = await self._call_parser(parser, f.name, provider)
            if isinstance(parsed, list):
                results.extend(parsed)
            elif parsed is not None:
                results.append(parsed)

        return results

    async def _call_parser(self, parser, file_path, provider):
        """Call parser.parse with a compatible signature."""
        try:
            result = parser.parse(file_path, provider)
        except TypeError:
            result = parser.parse(file_path)

        if inspect.isawaitable(result):
            result = await result
        return result

    async def get_feed_parser(self, provider):  # type: ignore[override]
        """Always return a fresh STT-specific NinJS parser instance."""

        return STTSinceNINJSFeedParser()


# Bind the custom parser to the HTTP feeding service.
register_feed_parser(STTSinceNINJSFeedParser.NAME, STTSinceNINJSFeedParser())
register_feeding_service(STTWithSinceHTTPFeedingService)
register_feeding_service_parser(
    STTWithSinceHTTPFeedingService.NAME, STTSinceNINJSFeedParser.NAME
)
