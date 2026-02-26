from tests import TestCase
from stt.stt_datapankki_ninjs_formatter import STTDatapankkiNinjsFormatter


class STTDatapankkiNinjsFormatterTest(TestCase):
    add_stt_cvs = True
    formatter = STTDatapankkiNinjsFormatter()

    async def test_events_count_from_planning(self):
        planning_id = "urn:newsml:stt.fi:123"
        self.app.data.insert(
            "planning",
            [
                {
                    "_id": planning_id,
                    "related_events": [{"_id": "event-1"}, {"_id": "event-2"}],
                }
            ],
        )

        article = {
            "type": "text",
            "guid": "urn:newsml:stt.fi:article-1",
            "planning_id": planning_id,
        }

        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(ninjs.get("extra", {}).get("stt_events_count"), 2)

    async def test_planning_anpa_category_in_extra(self):
        planning_id = "urn:newsml:stt.fi:456"
        self.app.data.insert(
            "planning",
            [
                {
                    "_id": planning_id,
                    "anpa_category": [
                        {"name": "Test Category", "qcode": "9", "scheme": None}
                    ],
                }
            ],
        )

        article = {
            "type": "text",
            "guid": "urn:newsml:stt.fi:article-2",
            "planning_id": planning_id,
        }

        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(
            ninjs.get("extra", {}).get("anpa_category"),
            [{"name": "Test Category", "qcode": "9", "scheme": None}],
        )

    async def test_signal_for_update(self):
        article = {
            "type": "text",
            "guid": "test",
            "rewrite_of": "urn:newsml:stt.fi:old",
            "operation": "publish",
        }

        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(ninjs.get("extra", {}).get("signal"), "update")

    async def test_creator_from_task_user(self):
        self.app.data.insert(
            "users",
            [
                {
                    "_id": "user-1",
                    "display_name": "Test Reporter",
                }
            ],
        )

        article = {
            "type": "text",
            "guid": "test",
            "task": {"user": "user-1"},
        }

        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(ninjs.get("extra", {}).get("creator_id"), "user-1")
        self.assertEqual(ninjs.get("extra", {}).get("creator_name"), "Test Reporter")

    async def test_imagetype_from_planning_coverages(self):
        planning_id = "urn:newsml:stt.fi:901"
        self.app.data.insert(
            "planning",
            [
                {
                    "_id": planning_id,
                    "coverages": [
                        {
                            "planning": {
                                "subject": [
                                    {
                                        "scheme": "sttimagetype",
                                        "qcode": "sttimage:20",
                                        "name": "Kuvaaja paikalla",
                                    }
                                ]
                            }
                        }
                    ],
                }
            ],
        )

        article = {
            "type": "text",
            "guid": "urn:newsml:stt.fi:article-4",
            "planning_id": planning_id,
        }

        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(
            ninjs.get("extra", {}).get("imagetype"),
            {"id": "20", "name": "Kuvaaja paikalla"},
        )

    async def test_place_name_filled_from_locators(self):
        ninjs = {
            "language": "fi",
            "place": [
                {"name": None, "code": "sttcity:35"},
                {"name": None, "code": "sttcountry:1"},
            ],
        }

        self.formatter.update_place_names(ninjs)
        by_code = {p["code"]: p.get("name") for p in ninjs.get("place", [])}
        self.assertEqual(by_code.get("sttcity:35"), "Helsinki")
        self.assertEqual(by_code.get("sttcountry:1"), "Suomi")

    def test_update_stt_sources_ignores_missing_names(self):
        ninjs = {
            "subject": [
                {"scheme": "sttsource", "name": "STT"},
                {"scheme": "sttsource"},
                {"scheme": "sttsource", "name": ""},
                {"scheme": "sttsource", "name": "Alpha"},
            ]
        }

        self.formatter.update_stt_sources(ninjs)

        self.assertEqual(ninjs.get("source"), "STT-Alpha")
