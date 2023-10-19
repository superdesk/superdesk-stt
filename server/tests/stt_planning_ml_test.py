from tests import TestCase
from stt.stt_planning_ml import STTPlanningMLParser
from datetime import datetime, timedelta
from dateutil.tz import tzoffset, tzutc
from superdesk.io.commands.update_ingest import ingest_item
from superdesk import get_resource_service
from bson import ObjectId


class STTPlanningMLParserTest(TestCase):
    fixture = "planning_ml_584717.xml"
    parser_class = STTPlanningMLParser
    add_stt_cvs = True
    max_diff = None

    def test_stt_metadata(self):
        # Extra metadata
        self.assertEqual(self.item["extra"]["stt_events"], "259431")
        self.assertEqual(self.item["extra"]["stt_topics"], "584717")

        # Subjects (only ``sttdepartment`` found in provided xml files)
        self.assertIn(
            {"qcode": "9", "name": "Politiikka", "scheme": "sttdepartment"},
            self.item["subject"],
        )

        # Associated Event ID
        self.assertEqual(self.item["event_item"], "urn:newsml:stt.fi:20220402:259431")

        # Make sure the coverage with ``subject.type=='cpnat:event`` is not included
        self.assertEqual(len(self.item["coverages"]), 1)
        self.assertEqual(
            self.item["coverages"][0]["coverage_id"], "ID_WORKREQUEST_159799"
        )

        # Urgency [STTNHUB-200]
        self.assertIn(
            {
                "name": "Keskipitkä juttu",
                "qcode": "stturgency-3",
                "scheme": "stturgency",
            },
            self.item["subject"],
        )

    def test_placeholder_coverage(self):
        # Case 1 : If Ingest Item does not contain any Coverage

        self.fixture = "stt_planning_ml_placeholder.xml"
        self.parse_source_content()
        self.assertEqual(self.item["guid"], "urn:newsml:stt.fi:20230529:620121")
        self.assertEqual(self.item["state"], "ingested")
        self.assertEqual(len(self.item["coverages"]), 1)
        self.assertEqual(
            self.item["versioncreated"],
            datetime(2023, 5, 15, 14, 50, 3, tzinfo=tzoffset(None, 7200)),
        )
        self.assertEqual(
            self.item["firstcreated"],
            datetime(2023, 5, 15, 14, 50, 3, tzinfo=tzoffset(None, 7200)),
        )
        self.assertEqual(
            self.item["name"], "Karelian Lock 23 -taisteluharjoituksen mediapäivä"
        )
        self.assertEqual(
            self.item["coverages"][0],
            {
                "coverage_id": "placeholder_urn:newsml:stt.fi:20230529:620121",
                "workflow_status": "draft",
                "firstcreated": datetime(
                    2023, 5, 15, 14, 50, 3, tzinfo=tzoffset(None, 7200)
                ),
                "planning": {
                    "slugline": "Placeholder Coverage",
                    "g2_content_type": "text",
                    "scheduled": datetime(2023, 5, 28, 21, 0, tzinfo=tzutc()),
                },
                "flags": {"placeholder": True},
                "news_coverage_status": {
                    "qcode": "ncostat:notint",
                    "name": "coverage not intended",
                    "label": "Not planned",
                },
            },
        )

        # Case 2 : If ingest item contain coverage.

        self.fixture = "stt_planning_ml_placeholder-2.xml"
        self.parse_source_content()
        print(self.item["coverages"])
        self.assertEqual(self.item["guid"], "urn:newsml:stt.fi:20230529:620121")
        self.assertEqual(len(self.item["coverages"]), 1)
        self.assertEqual(
            self.item["coverages"][0],
            {
                "coverage_id": "ID_TEXT_120844691",
                "workflow_status": "draft",
                "firstcreated": datetime(
                    2023, 5, 15, 14, 50, 3, tzinfo=tzoffset(None, 7200)
                ),
                "versioncreated": datetime(
                    2023, 5, 15, 14, 50, 3, tzinfo=tzoffset(None, 7200)
                ),
                "planning": {
                    "slugline": "Sudanissa taistelut jatkuvat",
                    "g2_content_type": "text",
                    "scheduled": datetime(
                        2023, 6, 1, 19, 30, tzinfo=tzoffset(None, 7200)
                    ),
                    "genre": [{"qcode": "sttgenre:1", "name": "Pääjuttu"}],
                },
                "news_coverage_status": {
                    "qcode": "ncostat:notint",
                    "name": "coverage not intended",
                    "label": "Not planned",
                },
            },
        )

    def test_update_planning(self):
        service = get_resource_service("planning")
        self.fixture = "stt_planning_ml_placeholder.xml"
        self.parse_source_content()
        source = self.item
        provider = {
            "_id": ObjectId(),
            "source": "sf",
            "name": "STT-PlanningML Ingest",
        }

        # Case 3 : Ingest Item with no coverage data
        ingested, ids = ingest_item(source, provider=provider, feeding_service={})

        self.assertTrue(ingested)
        self.assertIn(source["guid"], ids)
        dest = list(service.get_from_mongo(req=None, lookup={"guid": source["guid"]}))[
            0
        ]
        self.assertEqual(len(dest["coverages"]), 1)
        coverage = dest["coverages"][0]
        self.assertEqual(
            coverage["coverage_id"], "placeholder_urn:newsml:stt.fi:20230529:620121"
        )
        self.assertEqual(
            coverage["news_coverage_status"],
            {
                "qcode": "ncostat:notint",
                "name": "coverage not intended",
                "label": "Not planned",
            },
        )
        self.assertEqual(
            coverage["flags"], {"placeholder": True, "no_content_linking": False}
        )

        # Case 4 : Remove Placeholder Coverage if item updates has coverage
        self.fixture = "stt_planning_ml_placeholder-2.xml"
        self.parse_source_content()
        source = self.item
        source["versioncreated"] += timedelta(hours=1)
        ingested, ids = ingest_item(source, provider=provider, feeding_service={})
        dest = list(service.get_from_mongo(req=None, lookup={"guid": source["guid"]}))[
            0
        ]
        self.assertEqual(len(dest["coverages"]), 1)
        self.assertNotIn(
            "placeholder_urn:newsml:stt.fi:20230529:620121",
            dest["coverages"][0]["coverage_id"],
        )

    def test_text_link(self):
        self.fixture = "planning_ml_link.xml"
        self.parse_source_content()
        self.assertEqual(
            self.item["ednote"],
            """Testi: Lisätietoja aiheesta erityisesti media-asiakkaille\n\n<a href="https://www.stt.fi">www.stt.fi</a> STT\n\n<a href="https://stt.fi">stt.fi</a>\n\n<a href="https://stt.fi/">https://stt.fi/</a>\n\nSTT""",  # noqa
        )
        self.assertEqual(
            self.item["description_text"],
            '<a href="https://www.stt.fi">www.stt.fi</a> \n\n<a href="https://stt.fi">stt.fi</a> \n\n<a href="https://stt.fi/">https://stt.fi/</a>',  # noqa
        )
