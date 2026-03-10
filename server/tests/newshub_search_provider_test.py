from datetime import datetime, timezone
import unittest

from stt.search_providers.newshub import NewshubSearchProvider


class NewshubSearchProviderTestCase(unittest.TestCase):
    def setUp(self):
        self.provider = NewshubSearchProvider.__new__(NewshubSearchProvider)
        self.provider.provider = {
            "config": {"password": "token"},
            "search_provider": "newshub",
        }

    def test_extend_data_item_normalizes_string_timestamps(self):
        item = {
            "_id": "urn:newsml:stt.fi::12345",
            "firstcreated": "2026-03-09T12:30:00+02:00",
            "versioncreated": "2026-03-09T10:45:00Z",
        }

        extended = self.provider.extend_data_item(item)

        self.assertIsInstance(extended["firstcreated"], datetime)
        self.assertIsInstance(extended["versioncreated"], datetime)
        self.assertEqual(extended["firstcreated"].tzinfo, timezone.utc)
        self.assertEqual(extended["versioncreated"].tzinfo, timezone.utc)
        self.assertEqual(
            extended["firstcreated"], datetime(2026, 3, 9, 10, 30, tzinfo=timezone.utc)
        )
        self.assertEqual(
            extended["versioncreated"],
            datetime(2026, 3, 9, 10, 45, tzinfo=timezone.utc),
        )

    def test_extend_data_item_defaults_from_normalized_versioncreated(self):
        item = {
            "_id": "urn:newsml:stt.fi::12345",
            "versioncreated": "2026-03-09T10:45:00+02:00",
        }

        extended = self.provider.extend_data_item(item)

        self.assertEqual(
            extended["firstcreated"], datetime(2026, 3, 9, 8, 45, tzinfo=timezone.utc)
        )
        self.assertEqual(extended["firstcreated"], extended["versioncreated"])

    def test_extend_data_item_replaces_invalid_timestamp_with_default_datetime(self):
        item = {
            "_id": "urn:newsml:stt.fi::12345",
            "firstcreated": "not-a-date",
        }

        extended = self.provider.extend_data_item(item)

        self.assertIsInstance(extended["firstcreated"], datetime)
        self.assertIsInstance(extended["versioncreated"], datetime)
        self.assertEqual(extended["firstcreated"].tzinfo, timezone.utc)
        self.assertEqual(extended["versioncreated"].tzinfo, timezone.utc)

    def test_get_search_text_quotes_and_escapes_byline(self):
        query = {
            "query": {
                "filtered": {
                    "query": {"query_string": {"query": "economy"}},
                }
            }
        }

        search_text = self.provider.get_search_text(
            query,
            {"byline": 'Jane "JJ" Doe: Bureau\\Desk'},
        )

        self.assertEqual(search_text, 'economy "Jane \\"JJ\\" Doe: Bureau\\\\Desk"')

    def test_get_search_text_does_not_append_byline_to_id_lookup(self):
        query = {
            "query": {
                "filtered": {
                    "filter": {
                        "or": [
                            {
                                "term": {
                                    "_id": "urn:newsml:stt.fi::12345",
                                }
                            }
                        ]
                    }
                }
            }
        }

        search_text = self.provider.get_search_text(query, {"byline": 'Jane "JJ" Doe'})

        self.assertEqual(search_text, '_id:"urn:newsml:stt.fi::12345"')
