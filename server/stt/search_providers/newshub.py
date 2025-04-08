import superdesk
import arrow
import logging
from urllib.parse import urljoin
import requests

from superdesk.utils import ListCursor

logger = logging.getLogger(__name__)
session = requests.Session()
TIMEOUT = 10


def get_nested_value(data, key):
    for part in key.split("."):
        data = data.get(part)
        if data is None:
            return None
    return data


class NewshubListCursor(ListCursor):
    def __init__(self, docs, count):
        super().__init__(docs)
        self._count = count

    def count(self, **kwargs):
        return self._count


class NewshubSearchProvider(superdesk.SearchProvider):
    label = "Newshub"
    # TODO: set the base_url to the production URL when ready
    base_url = "https://stt-uat.newshub.pro/newsapi/v1/"
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

    def __init__(self, provider):
        logger.info(f"Newshub search provider: init {provider}")
        super().__init__(provider)
        self.base_url = provider.get("config", {}).get("url") or self.base_url
        self.api_token = provider.get("config", {}).get("password")

    def url(self, resource):
        return urljoin(self.base_url, resource.lstrip("/"))

    def extend_data_item(self, item):
        # add "_fetchable": True, to the item
        item["_fetchable"] = True
        return item

    def find(self, query, params=None):
        logger.info(f"Query: {query}")
        logger.info(f"Params: {params}")
        api_params = {
            "page_size": query.get("size", 25),
        }
        if params:
            dates = params.get("dates", {})
            if dates.get("start"):
                api_params["start_date"] = self._get_date(dates["start"], start=True)
            if dates.get("end"):
                api_params["end_date"] = self._get_date(dates["end"])

            period = params.get("period")
            if period and self.PERIODS.get(period):
                # override value of search by date
                api_params.update(self._get_period(period))
            if params.get("sort"):
                api_params["sort"] = params["sort"]
            if params.get("urgency"):
                api_params["urgency"] = params["urgency"]
            if params.get("genre"):
                api_params["genre"] = params["genre"]
            if params.get("subject"):
                api_params["subject"] = params["subject"]

        api_params["q"] = self.get_search_text(query)

        logger.info(f"API params: {api_params}")

        try:
            data = self.api_get(self.search_endpoint, api_params)
            if not data or not data.get(self.items_field):
                logger.warning("No items found.")
                return NewshubListCursor([], 0)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return NewshubListCursor([], 0)
        docs = [self.extend_data_item(item) for item in data.get(self.items_field, [])]
        total = get_nested_value(data, self.count_field)

        if total is None:
            logger.warning("Total count is None.")
            return NewshubListCursor([], 0)

        return NewshubListCursor(docs, total)

    def fetch(self, item_id):
        logger.info(f"Fetch item: {item_id}")
        api_params = {
            # this should be like _id:"urn:newsml:stt.fi::106858998"
            "q": f'_id:"urn:newsml:stt.fi::{item_id}"',
        }
        try:
            data = self.api_get(self.search_endpoint, api_params)
            if not data:
                logger.warning("No item found.")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
        return self.extend_data_item(data)

    def api_get(self, endpoint, params):
        # Add self.api_token as Bearer token
        session.headers.update({"Authorization": f"Bearer {self.api_token}"})
        resp = session.get(self.url(endpoint), params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def get_search_text(self, query):
        try:
            searchText = query["query"]["filtered"]["query"]["query_string"]["query"]
        except KeyError:
            searchText = ""
        try:
            # check also for '_id' from query
            if query["query"]["filtered"]["filter"]["or"]:
                for condition in query["query"]["filtered"]["filter"]["or"]:
                    if "term" in condition:
                        searchText = f'_id:"{condition["term"]["_id"]}"'
                        break
        except KeyError:
            pass
        return searchText or None

    def _get_period(self, period):
        today = arrow.now(superdesk.app.config["DEFAULT_TIMEZONE"])
        return {
            "start_date": today.shift(**self.PERIODS.get(period)).format("YYYY-MM-DD")
            + "T00:00:00",
            "end_date": today.format("YYYY-MM-DD") + "T23:59:59",
        }

    def _get_date(self, date, start=False):
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
                "API token is not set for {label}, please set it to the password variable to use it"
            )
            return False
        return True


superdesk.register_search_provider("newshub", provider_class=NewshubSearchProvider)


def init_app(app):
    pass
