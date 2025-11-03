from unittest import mock
from tests import TestCase
from stt.stt_planning_ml import STTPlanningMLParser
from datetime import datetime, timedelta
from dateutil.tz import tzoffset, tzutc
from superdesk.tests import TestCase as CoreTestCase
from superdesk.io.commands.update_ingest import ingest_item
from superdesk import get_resource_service
from bson import ObjectId


class STTPlanningMLParserTest(TestCase):
    fixture = "planning_ml_584717.xml"
    parser_class = STTPlanningMLParser
    add_stt_cvs = True

    def test_stt_metadata(self):
        # Extra metadata
        self.assertEqual(self.item["extra"]["stt_topics"], "584717")

        # Subjects (only ``sttdepartment`` found in provided xml files)
        self.assertIn(
            {"qcode": "9", "name": "Politiikka", "scheme": "sttdepartment"},
            self.item["subject"],
        )

        # Associated Event is missing
        assert "event_item" not in self.item

        # Make sure the coverage with ``subject.type=='cpnat:event`` is not included
        self.assertEqual(len(self.item["coverages"]), 2)
        self.assertEqual(
            self.item["coverages"][0]["coverage_id"], "ID_WORKREQUEST_159799"
        )

    def test_department(self):
        category = self.item["anpa_category"][0]
        self.assertEqual("9", category["qcode"])
        self.assertEqual("Politiikka", category["name"])

    def test_priority(self):
        self.assertEqual(3, self.item["priority"])

    def test_mediatopics(self):
        mediatopics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        assert mediatopics
        assert mediatopics[0]["name"] == "Politiikka"
        assert mediatopics[0]["qcode"] == "11000000"
        assert mediatopics[0]["wikidata"] == "Q7163"

    async def test_event_link(self):
        self.app.data.insert("events", [{"_id": "urn:newsml:stt.fi:259431"}])
        await self.parse_source_content()
        self.assertEqual(self.item["event_item"], "urn:newsml:stt.fi:259431")
        self.assertEqual(self.item["extra"]["stt_events"], "259431")

    async def test_placeholder_coverage(self):
        # Case 1 : If Ingest Item does not contain any Coverage

        self.fixture = "stt_planning_ml_placeholder.xml"
        await self.parse_source_content()
        self.assertEqual(self.item["guid"], "urn:newsml:stt.fi:620121")
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
                "coverage_id": "placeholder_urn:newsml:stt.fi:620121",
                "workflow_status": "draft",
                "firstcreated": datetime(
                    2023, 5, 15, 14, 50, 3, tzinfo=tzoffset(None, 7200)
                ),
                "planning": {
                    "slugline": "",
                    "g2_content_type": "text",
                    "scheduled": datetime(2023, 5, 29, 0, 0, tzinfo=tzutc()),
                },
                "flags": {"placeholder": True},
                "news_coverage_status": {
                    "qcode": "ncostat:notint",
                    "name": "coverage not intended",
                    "label": "Ei",
                },
            },
        )

        # Case 2 : If ingest item contain coverage.

        self.fixture = "stt_planning_ml_placeholder-2.xml"
        await self.parse_source_content()
        print(self.item["coverages"])
        self.assertEqual(self.item["guid"], "urn:newsml:stt.fi:620121")
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
                    "label": "Ei",
                },
            },
        )

    async def test_update_planning(self):
        service = get_resource_service("planning")
        self.fixture = "stt_planning_ml_placeholder.xml"
        await self.parse_source_content()
        source = self.item
        provider = {
            "_id": ObjectId(),
            "source": "sf",
            "name": "STT-PlanningML Ingest",
        }

        # Case 3 : Ingest Item with no coverage data
        ingested, ids = await ingest_item(source, provider=provider, feeding_service={})

        self.assertTrue(ingested)
        self.assertIn(source["guid"], ids)
        dest = list(service.get_from_mongo(req=None, lookup={"guid": source["guid"]}))[
            0
        ]
        self.assertEqual(len(dest["coverages"]), 1)
        coverage = dest["coverages"][0]
        self.assertEqual(
            coverage["coverage_id"], "placeholder_urn:newsml:stt.fi:620121"
        )
        self.assertEqual(
            coverage["news_coverage_status"],
            {
                "qcode": "ncostat:notint",
                "name": "coverage not intended",
                "label": "Ei",
            },
        )
        self.assertEqual(
            coverage["flags"], {"placeholder": True, "no_content_linking": False}
        )

        # Case 4 : Remove Placeholder Coverage if item updates has coverage
        self.fixture = "stt_planning_ml_placeholder-2.xml"
        await self.parse_source_content()
        source = self.item
        source["versioncreated"] += timedelta(hours=1)
        ingested, ids = await ingest_item(source, provider=provider, feeding_service={})
        dest = list(service.get_from_mongo(req=None, lookup={"guid": source["guid"]}))[
            0
        ]
        self.assertEqual(len(dest["coverages"]), 1)
        self.assertNotIn(
            "placeholder_urn:newsml:stt.fi:620121",
            dest["coverages"][0]["coverage_id"],
        )

    async def test_stt_internal_planning_fields_690975(self):
        """Test STT internal planning fields from 690975_timefix.xml"""
        self.fixture = "690975_timefix.xml"
        await self.parse_source_content()

        # Test planning item internal note
        self.assertEqual(
            self.item["internal_note"],
            "Anne ilmoitettu. Ilmoittautumiset viimeistään perjantaina 24.10. media@oph.fi. Teams-linkki lähetetään ilmoittautuneille ma 27.10.\n",
        )

        coverage_227301 = None
        for coverage in self.item["coverages"]:
            if coverage["coverage_id"] == "ID_WORKREQUEST_227301":
                coverage_227301 = coverage
                break

        self.assertIsNotNone(coverage_227301)

        # Test STT internal coverage fields
        planning = coverage_227301["planning"]
        self.assertEqual(
            planning["headline"],
            "Opetushallituksen mediatilaisuus ulkomaalaisten tutkinto-opiskelijoiden työllistymisestä",
        )
        self.assertEqual(planning["g2_content_type"], "picture")
        self.assertEqual(planning["sttimagetype"], "sttimage:28")
        self.assertEqual(planning["sttdoesphotographerknow"], "yes")

        # Test coverage internal note
        self.assertEqual(
            coverage_227301["internal_note"],
            "aarrggghhh tää on hankala.. lue juttu ja keksi jotain, tässä pari tyrkkyä -tt\n\n93775987,89568598,89568550,89568459\n\nKuinka hyvin ulkomaalaiset tutkinto-opiskelijat ovat työllistyneet? Opetushallituksen tilaisuudessa klo 10 aiheesta kerrotaan tuoreimpien tilastojen kautta: Vuonna 2020 valmistuneiden ulkomaalaisten opiskelijoiden työllistyminen kolme vuotta valmistumisen jälkeen. Toimittajana Anne Salomäki. Opetushallituksen mediatilaisuus ulkomaalaisten tutkinto-opiskelijoiden työllistymisestä, klo 10. 3150 merkkiä. Kuvitus: Kuvituskuvaa arkistosta.",
        )

        # Test Finnish text fields
        self.assertIn(
            "Mediatilaisuus 28.10. klo 10–11:", planning["sttpicturewhatisphotographed"]
        )
        self.assertIn(
            "Kuvituskuvaa arkistosta", planning.get("sttpicturewhatabout", "")
        )

    async def test_stt_internal_planning_fields_691631(self):
        """Test STT internal planning fields from 691631_timefix.xml"""
        self.fixture = "691631_timefix.xml"
        await self.parse_source_content()

        # Find coverages with STT internal fields
        coverage_227572 = None
        coverage_227573 = None

        for coverage in self.item["coverages"]:
            if coverage["coverage_id"] == "ID_WORKREQUEST_227572":
                coverage_227572 = coverage
            elif coverage["coverage_id"] == "ID_WORKREQUEST_227573":
                coverage_227573 = coverage

        self.assertIsNotNone(coverage_227572)
        planning_227572 = coverage_227572["planning"]
        self.assertEqual(
            planning_227572["headline"],
            "Nvidia sijoittaa miljardi dollaria Nokian osakkeisiin",
        )
        self.assertEqual(planning_227572["g2_content_type"], "picture")
        self.assertEqual(planning_227572["sttimagetype"], "sttimage:21")
        self.assertEqual(planning_227572["sttdoesphotographerknow"], "yes")
        self.assertEqual(
            planning_227572["sttpicturewhatabout"], "ja kv. kuvaa arkistosta."
        )

        self.assertIsNotNone(coverage_227573)
        planning_227573 = coverage_227573["planning"]
        self.assertEqual(
            planning_227573["headline"], "FREE-SEPPO // Nokia head office, Karakaari 7."
        )
        self.assertEqual(planning_227573["g2_content_type"], "picture")
        self.assertEqual(planning_227573["sttimagetype"], "sttimage:20")
        self.assertEqual(planning_227573["sttdoesphotographerknow"], "yes")
        self.assertEqual(
            planning_227573["sttpicturewhatabout"],
            "arkistokuvaa ja kv. kuvaa arkistosta.",
        )

    async def test_stt_coverage_status_mapping(self):
        """Test all STT workstatus mappings"""
        test_cases = [
            ("sttworkstatus:1", "ncostat:int", "coverage intended", "Kyllä"),
            ("sttworkstatus:2", "ncostat:int", "coverage intended", "Kyllä"),
            ("sttworkstatus:3", "ncostat:int", "coverage intended", "Kyllä"),
            ("sttworkstatus:4", "ncostat:notint", "coverage not intended", "Ei"),
            ("sttworkstatus:5", "ncostat:notdec", "coverage not decided yet", "Ei"),
        ]

        for stt_status, expected_qcode, expected_name, expected_label in test_cases:
            with self.subTest(stt_status=stt_status):
                parser = STTPlanningMLParser()

                self.assertEqual(
                    parser.get_coverage_status_name(expected_qcode), expected_name
                )
                self.assertEqual(
                    parser.get_coverage_status_label(expected_qcode), expected_label
                )

    async def test_stt_photographer_awareness_mapping(self):
        """Test photographer awareness mapping"""
        self.fixture = "691631_timefix.xml"
        await self.parse_source_content()

        for coverage in self.item["coverages"]:
            if coverage["coverage_id"].startswith("ID_WORKREQUEST_"):
                self.assertEqual(coverage["planning"]["sttdoesphotographerknow"], "yes")


def is_placeholder_coverage(coverage):
    try:
        return coverage["flags"]["placeholder"] is True
    except (KeyError, TypeError):
        return False


class STTPlanningMLParserPlaceholderTests(CoreTestCase):
    @mock.patch("stt.stt_planning_ml.STTPlanningMLParser.parse_news_coverage_status")
    def test_set_placeholder_coverage(self, mock_parse_news_coverage_status):
        parser = STTPlanningMLParser()

        item = {}
        parser.set_placeholder_coverage(item, None)
        self.assertEqual(len(item["coverages"]), 1)
        self.assertTrue(item["coverages"][0]["flags"]["placeholder"])

        item = {"coverages": [{"planning": {"g2_content_type": "picture"}}]}
        parser.set_placeholder_coverage(item, None)
        self.assertEqual(len(item["coverages"]), 2)
        self.assertFalse(is_placeholder_coverage(item["coverages"][0]))
        self.assertTrue(is_placeholder_coverage(item["coverages"][1]))

        item = {
            "coverages": [
                {"planning": {"g2_content_type": "text"}},
                {"planning": {"g2_content_type": "picture"}},
            ]
        }
        parser.set_placeholder_coverage(item, None)
        self.assertEqual(len(item["coverages"]), 2)
        self.assertFalse(is_placeholder_coverage(item["coverages"][0]))
        self.assertFalse(is_placeholder_coverage(item["coverages"][1]))

    @mock.patch("stt.stt_planning_ml.STTPlanningMLParser.parse_news_coverage_status")
    def test_check_coverage_removes_placeholder(self, mock_parse_news_coverage_status):
        parser = STTPlanningMLParser()

        original = {
            "coverages": [
                {
                    "coverage_id": "placeholder_cov",
                    "planning": {"g2_content_type": "text"},
                    "flags": {"placeholder": True},
                },
            ]
        }
        updates = {
            "coverages": [
                {"coverage_id": "text_cov_1", "planning": {"g2_content_type": "text"}},
            ]
        }
        parser.check_coverage(original, updates, None)
        self.assertFalse(is_placeholder_coverage(updates["coverages"][0]))
        self.assertEqual(updates["coverages"][0]["coverage_id"], "text_cov_1")

        original = {
            "coverages": [
                {
                    "coverage_id": "pic_cov_1",
                    "planning": {"g2_content_type": "picture"},
                },
                {
                    "coverage_id": "placeholder_cov",
                    "planning": {"g2_content_type": "text"},
                    "flags": {"placeholder": True},
                },
            ]
        }
        updates = {
            "coverages": [
                {
                    "coverage_id": "pic_cov_1",
                    "planning": {"g2_content_type": "picture"},
                },
                {"coverage_id": "text_cov_1", "planning": {"g2_content_type": "text"}},
            ]
        }
        parser.check_coverage(original, updates, None)
        self.assertFalse(is_placeholder_coverage(updates["coverages"][0]))
        self.assertFalse(is_placeholder_coverage(updates["coverages"][1]))
        self.assertEqual(updates["coverages"][0]["coverage_id"], "pic_cov_1")
        self.assertEqual(updates["coverages"][1]["coverage_id"], "text_cov_1")
