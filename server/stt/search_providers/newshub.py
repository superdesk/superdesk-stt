from urllib.parse import urljoin
import logging
from datetime import datetime, timezone

import arrow
import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from dateutil import parser as dtparse

import superdesk
from superdesk.core import get_config
from superdesk.core.utils import get_nested_value
from superdesk.utils import ListCursor


logger = logging.getLogger(__name__)
TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)


class NewshubListCursor(ListCursor):
    def __init__(self, docs: list[dict], count: int):
        super().__init__(docs)
        self._count = count

    def count(self, **kwargs) -> int:
        return self._count


class NewshubSearchProvider(superdesk.SearchProvider):
    label = "Newshub"
    # TODO: set the base_url to the production URL when ready
    base_url = "https://stt-next.newshub.pro/newsapi/v1/"
    api_token = None
    search_endpoint = "news/search"
    items_field = "_items"
    count_field = "_meta.total"
    PERIODS = {
        "day": {"days": -1},
        "week": {"weeks": -1},
        "month": {"months": -1},
        "year": {"years": -1},
    }
    INCLUDE_FIELDS = ",".join(
        [
            "type",
            "urgency",
            "priority",
            "language",
            "description_html",
            "located",
            "keywords",
            "source",
            "subject",
            "place",
            "wordcount",
            "charcount",
            "body_html",
            "readtime",
            "profile",
            "service",
            "genre",
            "headline",
        ]
    )

    def __init__(self, provider):
        logger.info(
            f"Newshub search provider: init {provider.get('name')} "
            f"({provider.get('_id')})"
        )
        super().__init__(provider)
        self.base_url = provider.get("config", {}).get("url") or self.base_url
        self.api_token = provider.get("config", {}).get("password")

    def url(self, resource):
        return urljoin(self.base_url, resource.lstrip("/"))

    def _get_fetch_guid(self, item: dict) -> str | None:
        guid = item.get("guid") or item.get("_id")

        if guid is None:
            return None

        guid = str(guid)
        if guid.startswith("urn:newsml:stt.fi::"):
            return guid.split("::", 1)[1]

        return guid

    def _normalize_timestamp(self, value) -> datetime | None:
        if not value:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        try:
            parsed = dtparse.parse(str(value))
        except (TypeError, ValueError, OverflowError) as exc:
            logger.warning("Failed to parse timestamp %r: %s", value, exc)
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    def _escape_query_phrase(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def extend_data_item(self, item: dict) -> dict:
        # Shape results like a regular external text item so the search UI can
        # resolve actions and preview behavior consistently.
        now = datetime.now(timezone.utc)
        firstcreated = self._normalize_timestamp(item.get("firstcreated"))
        versioncreated = self._normalize_timestamp(item.get("versioncreated"))

        if firstcreated is None:
            firstcreated = versioncreated or now
        if versioncreated is None:
            versioncreated = firstcreated or now

        item["_type"] = "externalsource"
        item["type"] = "text"
        item["mimetype"] = "application/superdesk.item.text"
        item.setdefault("state", "published")
        item.setdefault("pubstatus", "usable")
        item["firstcreated"] = firstcreated
        item["versioncreated"] = versioncreated
        item["_fetchable"] = True
        item["search_provider"] = self.provider.get("search_provider", "newshub")
        item["fetch_endpoint"] = "search_providers_proxy"

        # Newshub returns the content profile label (e.g. "Nettiuutinen"), but
        # the client loads the profile by its _id, which is lowercase in STT.
        if isinstance(item.get("profile"), str):
            item["profile"] = item["profile"].lower()

        fetch_guid = self._get_fetch_guid(item)
        if fetch_guid:
            item.setdefault("guid", fetch_guid)

        return item

    def _get_cv_items(self, vocabulary_id: str) -> list[dict]:
        return superdesk.get_resource_service("vocabularies").get_items(vocabulary_id)

    def set_stt_sources(self, item: dict) -> None:
        """
        Map Newshub ``source`` string (e.g. ``STT-Veikkaus``)
        to sttsource subjects.
        """
        source = item.get("source")
        if not source or not isinstance(source, str):
            return

        try:
            cv_sources = {cv["qcode"]: cv for cv in self._get_cv_items("sttsource")}
        except Exception as e:
            logger.warning(f"Failed to load sttsource vocabulary: {e}")
            return

        subject = item["subject"] = item.get("subject") or []
        existing = {
            s.get("qcode")
            for s in subject
            if isinstance(s, dict) and s.get("scheme") == "sttsource"
        }
        for code in source.split("-"):
            code = code.strip()
            if not code or code in existing:
                continue
            cv_source = cv_sources.get(code)
            if cv_source:
                subject.append(
                    {
                        "qcode": cv_source["qcode"],
                        "name": cv_source.get("name"),
                        "scheme": "sttsource",
                    }
                )
                existing.add(code)
            else:
                logger.warning(f"Unknown Newshub source: {code}")

    def set_anpa_category(self, item: dict) -> None:
        """
        Map Newshub ``service`` codes to ``anpa_category``
        via the categories CV.
        """
        codes = [
            str(service["code"])
            for service in item.get("service") or []
            if isinstance(service, dict) and service.get("code") is not None
        ]
        if not codes:
            return

        try:
            categories = {cv["qcode"]: cv for cv in self._get_cv_items("categories")}
        except Exception as e:
            logger.warning(f"Failed to load categories vocabulary: {e}")
            return

        anpa_category = []
        for code in codes:
            category = categories.get(code)
            if category:
                anpa_category.append(
                    {"qcode": category["qcode"], "name": category.get("name")}
                )
            else:
                logger.warning(f"Unknown Newshub service code: {code}")

        if anpa_category:
            item["anpa_category"] = anpa_category

    async def find_async(
        self, query: dict, params: dict | None = None
    ) -> NewshubListCursor:
        async with aiohttp.ClientSession() as session:
            return await self.perform_find(session, query, params)

    async def perform_find(
        self, session: aiohttp.ClientSession, query: dict, params: dict | None = None
    ) -> NewshubListCursor:
        logger.info(f"Query: {query}")
        logger.info(f"Params: {params}")
        page_size = query.get("size", 25)
        api_params: dict = {
            "page_size": page_size,
            "page": int(query.get("from", 0) / page_size) + 1,
            "timezone": get_config(str, "DEFAULT_TIMEZONE"),
            "include_fields": self.INCLUDE_FIELDS,
        }
        if params:
            dates = params.get("dates", {})
            if dates.get("start"):
                api_params["start_date"] = self._get_date(dates["start"], start=True)
            if dates.get("end"):
                api_params["end_date"] = self._get_date(dates["end"])

            if params.get("period"):
                # override value of search by date
                api_params.update(self._get_period(params["period"]))
            if params.get("sort"):
                api_params["sort"] = params["sort"]
            if params.get("urgency"):
                api_params["urgency"] = params["urgency"]
            if params.get("genre"):
                api_params["genre"] = params["genre"]
            if params.get("categories"):
                api_params["service"] = params["categories"]
            if params.get("sttversion") or params.get("subject"):
                api_params["subject"] = params.get("sttversion") or params.get(
                    "subject"
                )

        api_params["q"] = self.get_search_text(query, params)

        logger.info(f"API params: {api_params}")

        try:
            data = await self.api_get(session, self.search_endpoint, api_params)
            if not data or not data.get(self.items_field):
                logger.warning("No items found.")
                return NewshubListCursor([], 0)
        except ClientResponseError as e:
            logger.error(f"Request failed: {e}")
            return NewshubListCursor([], 0)
        docs = [self.extend_data_item(item) for item in data.get(self.items_field, [])]
        total = get_nested_value(int, data, self.count_field, None)

        if total is None:
            logger.warning("Total count is None.")
            return NewshubListCursor([], 0)

        return NewshubListCursor(docs, total)

    async def fetch_async(self, item_id: str) -> dict | None:
        async with aiohttp.ClientSession() as session:
            return await self.perform_fetch(session, item_id)

    async def perform_fetch(
        self, session: aiohttp.ClientSession, item_id: str
    ) -> dict | None:
        logger.info(f"Fetch item: {item_id}")
        # Some Newshub instances use plain ids, others STT urns - try both
        search_id = str(item_id)
        urn_prefix = "urn:newsml:stt.fi::"
        if search_id.startswith(urn_prefix):
            search_ids = [search_id.removeprefix(urn_prefix), search_id]
        else:
            search_ids = [search_id, f"{urn_prefix}{search_id}"]

        for search_id in search_ids:
            api_params = {
                "q": f'_id:"{search_id}"',
                "include_fields": self.INCLUDE_FIELDS,
            }
            try:
                data = await self.api_get(session, self.search_endpoint, api_params)
            except ClientResponseError as e:
                logger.error(f"Request failed: {e}")
                return None
            items = data.get(self.items_field, []) if data else []
            if items:
                item = self.extend_data_item(items[0])
                self.set_anpa_category(item)
                self.set_stt_sources(item)
                return item

        logger.warning(f"No item found for {item_id}.")
        return None

    async def api_get(
        self, session: aiohttp.ClientSession, endpoint: str, params: dict
    ) -> dict:
        # Add self.api_token as Bearer token
        session.headers.update({"Authorization": f"Bearer {self.api_token}"})
        async with session.get(
            self.url(endpoint),
            params={key: val for key, val in params.items() if val is not None},
            timeout=TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    def get_search_text(self, query: dict, params: dict | None = None) -> str | None:
        try:
            search_text = query["query"]["filtered"]["query"]["query_string"]["query"]
        except KeyError:
            search_text = ""
        try:
            # check also for '_id' from query
            if query["query"]["filtered"]["filter"]["or"]:
                for condition in query["query"]["filtered"]["filter"]["or"]:
                    if "term" in condition:
                        search_text = f'_id:"{condition["term"]["_id"]}"'
                        break
        except KeyError:
            pass

        byline = (params or {}).get("byline")
        if byline:
            byline = byline.strip()
            if byline and not str(search_text).startswith('_id:"'):
                safe_byline = self._escape_query_phrase(byline)
                search_text = f'{search_text} "{safe_byline}"'.strip()

        return search_text or None

    def _get_period(self, period: str) -> dict[str, str]:
        today = arrow.now(get_config(str, "DEFAULT_TIMEZONE"))
        datetime_delta = self.PERIODS.get(period)
        if not datetime_delta:
            logger.warning(f"Invalid period: {period}")
            return {}

        return {
            "start_date": today.shift(check_imaginary=True, **datetime_delta).format(
                "YYYY-MM-DD"
            ),
        }

    def _get_date(self, date: str, start: bool = False) -> str:
        try:
            # if start, add hours to the date like 00:00:00
            if start:
                return arrow.get(date, "DD/MM/YYYY").format("YYYY-MM-DD") + "T00:00:00"
            # otherwise add hours to the date like 23:59:59
            return arrow.get(date, "DD/MM/YYYY").format("YYYY-MM-DD") + "T23:59:59"
        except arrow.parser.ParserError:
            logger.error(f"Error parsing date: {date}")
            return ""

    def available(self):
        if not self.api_token:
            logger.warning(
                "API token is not set for {label}, "
                "please set it to the password "
                "variable to use it"
            )
            return False
        return True


superdesk.register_search_provider("newshub", provider_class=NewshubSearchProvider)


def init_app(app):
    pass
