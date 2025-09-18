import datetime
import json
import os
import logging
import requests
from tempfile import NamedTemporaryFile
from superdesk.errors import IngestApiError
from superdesk.io.feeding_services.http_service import HTTPFeedingService
from superdesk.io.registry import (
    register_feeding_service,
    register_feeding_service_parser,
)

logger = logging.getLogger(__name__)


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

    def _update(self, provider, update):
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
        parser = self.get_feed_parser(provider)
        items = []
        self.session = requests.Session()
        response = self.fetch(provider, update)

        # Parse by feeding one item at a time to the NinJS parser
        content = response.content or b""
        items = self._parse_items_via_ninjs(parser, content, provider)

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

    def _parse_items_via_ninjs(self, parser, content: bytes, provider):
        """Pass a single item at a time to the NinJS parser.

        Supports the following top-level shapes:
        - dict with a single NinJS object
        - dict with {"items": [ ... ]}
        - list of NinJS objects
        Falls back to writing the raw content to a temp file if JSON decoding fails.
        """
        results = []
        try:
            data = json.loads(content)
        except Exception:
            # Fallback: let parser.parse handle the raw file content by writing it to disk
            with NamedTemporaryFile("wb", delete=False, suffix=".json") as f:
                f.write(content)
                tmp = f.name
            try:
                results = self._call_parser(parser, tmp, provider)
            finally:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
            return results

        # Normalize to a list of item dicts
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

        for obj in iterable:
            if not isinstance(obj, dict):
                continue
            # Normalize date fields to UTC 'Z' so ninjs parser can parse them
            obj = self._normalize_dates_in_obj(obj)
            # Ensure ninjs 'service' is present if only 'anpa_category' exists
            obj = self._adapt_category_for_ninjs(obj)
            with NamedTemporaryFile("w", delete=False, suffix=".json") as f:
                json.dump(obj, f)
                tmp = f.name
            try:
                parsed = self._call_parser(parser, tmp, provider)
                if isinstance(parsed, list):
                    results.extend(parsed)
                elif parsed is not None:
                    results.append(parsed)
            finally:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

        return results

    def _call_parser(self, parser, file_path, provider):
        """Call parser.parse with a compatible signature."""
        try:
            return parser.parse(file_path, provider)
        except TypeError:
            return parser.parse(file_path)

    def _normalize_dates_in_obj(self, obj: dict) -> dict:
        """Return a shallow copy of obj with key date fields normalized to UTC 'Z'.

        The stock ninjs parser only accepts 'Z' or '+00:00' (and no fractional seconds).
        This converts any ISO8601 with timezone offset to '%Y-%m-%dT%H:%M:%SZ'.
        Also normalizes nested association items recursively.
        """

        def _to_utc_z(s: str) -> str:
            try:
                # Support 'Z' and explicit offsets like '+03:00'
                s2 = s.replace("Z", "+00:00")
                dt = datetime.datetime.fromisoformat(s2)
                if dt.tzinfo is None:
                    # Assume UTC if naive
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                dt_utc = dt.astimezone(datetime.timezone.utc)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                return s

        out = dict(obj)
        for key in ("versioncreated", "firstcreated", "embargoed"):
            val = out.get(key)
            if isinstance(val, str):
                out[key] = _to_utc_z(val)

        # Normalize associations recursively if present
        assoc = out.get("associations")
        if isinstance(assoc, dict):
            new_assoc = {}
            for k, v in assoc.items():
                if isinstance(v, dict):
                    new_assoc[k] = self._normalize_dates_in_obj(v)
                else:
                    new_assoc[k] = v
            out["associations"] = new_assoc

        return out

    def _adapt_category_for_ninjs(self, obj: dict) -> dict:
        """
        Normalize category-related fields into the NINJS-compatible "service" structure.

        This helper produces/normalizes a "service" field as a list of dictionaries
        each containing at least a "code" key (and optionally "name" and "scheme"),
        based on the following rules:

        - If "anpa_category" exists and "service" does not:
            - Accepts a string, a dict, or a list of strings/dicts.
            - For dict elements, "code" is taken from "code" or "qcode"; "name" and "scheme"
                are preserved if present.
            - For string elements, a service entry is created as {"code": <string>}.
            - Elements that do not yield a "code" are ignored.
            - The resulting list is stored in "service". The original "anpa_category" is preserved.

        - If "service" exists as a list:
            - Each element is normalized:
                - Dict elements must provide "code" or "qcode"; "name" and "scheme" are preserved.
                - String elements are converted to {"code": <string>}.
                - Dict elements without a resolvable code are dropped.

        - If "service" exists as a string:
            - It is converted to [{"code": <string>}].

        In all cases, a shallow copy of the input mapping is returned; the original is not modified.

        Parameters:
                obj (dict): Input mapping potentially containing "anpa_category" and/or "service".

        Returns:
                dict: A shallow copy of the input with "service" normalized to a list of
                dictionaries with at least a "code" key. Other fields are left unchanged.
        """
        out = dict(obj)
        if "anpa_category" in out and "service" not in out:
            val = out.get("anpa_category")
            svc: list = []
            # Normalize val to a list of entries
            if isinstance(val, list):
                src = val
            else:
                src = [val]
            for el in src:
                if isinstance(el, dict):
                    code = el.get("code") or el.get("qcode")
                    if code is not None:
                        entry = {"code": code}
                        if el.get("name"):
                            entry["name"] = el.get("name")
                        if el.get("scheme"):
                            entry["scheme"] = el.get("scheme")
                        svc.append(entry)
                elif isinstance(el, str):
                    svc.append({"code": el})
            out["service"] = svc
        elif isinstance(out.get("service"), list):
            # If service exists but contains strings, convert them to dicts
            normalized = []
            for el in out["service"]:
                if isinstance(el, dict):
                    if "code" in el or "qcode" in el:
                        code = el.get("code") or el.get("qcode")
                        entry = {"code": code}
                        if el.get("name"):
                            entry["name"] = el.get("name")
                        if el.get("scheme"):
                            entry["scheme"] = el.get("scheme")
                        normalized.append(entry)
                elif isinstance(el, str):
                    normalized.append({"code": el})
            out["service"] = normalized
        elif isinstance(out.get("service"), str):
            out["service"] = [{"code": out.get("service")}]
        return out


register_feeding_service(STTWithSinceHTTPFeedingService)
register_feeding_service_parser(STTWithSinceHTTPFeedingService.NAME, "ninjs")
