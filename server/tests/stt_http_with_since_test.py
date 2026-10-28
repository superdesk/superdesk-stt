# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import re

from superdesk.errors import IngestApiError
from superdesk.tests import TestCase
from superdesk.tests.http_mocks import mock_http

from stt.io.feeding_services.stt_http_with_since import STTWithSinceHTTPFeedingService


FEED_URL = "https://api.example.com/results"
MATCH_FEED_URL = re.compile(rf"^{FEED_URL}(\?.*)?$")

TEST_ITEMS = [
    {
        "guid": "result-1",
        "type": "text",
        "headline": "Result 1",
        "versioncreated": "2026-10-27T10:00:00+00:00",
    },
    {
        "guid": "result-2",
        "type": "text",
        "headline": "Result 2",
        "versioncreated": "2026-10-27T11:00:00+00:00",
    },
]


class STTWithSinceHTTPFeedingServiceTestCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.service = STTWithSinceHTTPFeedingService()
        self.http_mock = mock_http(self)

    def get_provider(self, **config):
        return {
            "_id": "sport-results",
            "name": "STT Sport results",
            "feeding_service": STTWithSinceHTTPFeedingService.NAME,
            "last_updated": datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc),
            "config": {"url": FEED_URL, "auth_token": "TEST_TOKEN", **config},
        }

    async def fetch_items(self, provider):
        generator = await self.service.update(provider, {})
        items = []
        async for batch in generator:
            items.extend(batch)
        return items

    async def test_update_sends_bearer_token_header(self):
        self.http_mock.get(MATCH_FEED_URL, payload={"items": TEST_ITEMS})

        items = await self.fetch_items(self.get_provider())

        self.assertEqual(["result-1", "result-2"], [item["guid"] for item in items])

        (_, url), calls = next(iter(self.http_mock.requests.items()))
        self.assertEqual("2026-10-27T09:00:00Z", url.query["since"])
        # aiohttp only accepts BasicAuth for ``auth``, the token must go in the headers
        self.assertIsNone(calls[0].kwargs.get("auth"))
        self.assertEqual(
            "Bearer TEST_TOKEN", calls[0].kwargs["headers"]["Authorization"]
        )

    async def test_update_without_auth_token_raises(self):
        provider = self.get_provider(auth_token="")

        with self.assertRaises(IngestApiError):
            await self.fetch_items(provider)

        self.assertEqual(0, len(self.http_mock.requests))

    async def test_update_auth_error(self):
        self.http_mock.get(MATCH_FEED_URL, status=401)

        with self.assertRaises(IngestApiError):
            await self.fetch_items(self.get_provider())
