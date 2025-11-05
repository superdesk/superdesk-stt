import json
import os
from tests import TestCase
from superdesk import get_resource_service
from stt.stt_json_planning_formatter import STTJsonPlanningFormatter


class STTJsonPlanningFormatterTest(TestCase):
    add_stt_cvs = True
    parse_source = False
    fixture = "json/stt_json_planning_item.json"

    def get_sample_item(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", self.fixture)
        with open(fixture_path, "r") as f:
            return json.load(f)

    async def test_update_stt_urgency_mappings(self):
        async with self.app.app_context():
            formatter = STTJsonPlanningFormatter()
            vocab_items = get_resource_service("vocabularies").get_items("stturgency")
            name_map = {v["qcode"]: v["name"] for v in vocab_items}

            for priority, expected_qcode in [
                (1, "stturgency-1"),
                (2, "stturgency-2"),
                (3, "stturgency-2"),
                (4, "stturgency-4"),
                (5, "stturgency-5"),
                (0, "stturgency-5"),
            ]:
                item = {"priority": priority}
                formatter.update_stt_urgency(item)
                self.assertEqual(len(item.get("subject", [])), 1)
                subj = item["subject"][0]
                self.assertEqual(subj["qcode"], expected_qcode)
                self.assertEqual(subj["scheme"], "stturgency")
                self.assertEqual(subj["name"], name_map[expected_qcode])

    async def test_exclude_internal_planning_fields(self):
        async with self.app.app_context():
            formatter = STTJsonPlanningFormatter()
            item = self.get_sample_item()

            self.assertIn("internal_note", item)
            self.assertTrue(
                any(
                    subj.get("scheme") == "sttcheckedby"
                    for subj in item.get("subject", [])
                )
            )

            formatter.exclude_internal_planning_fields(item)

            self.assertNotIn("internal_note", item)
            self.assertFalse(
                any(
                    subj.get("scheme") == "sttcheckedby"
                    for subj in item.get("subject", [])
                )
            )
            self.assertTrue(
                any(
                    subj.get("scheme") == "stturgency"
                    for subj in item.get("subject", [])
                )
            )

    async def test_exclude_internal_coverage_fields(self):
        async with self.app.app_context():
            formatter = STTJsonPlanningFormatter()
            item = self.get_sample_item()

            coverage = item["coverages"][0]
            planning = coverage["planning"]
            self.assertIn("headline", planning)
            self.assertIn("location", planning)
            self.assertIn("internal_note", planning)
            self.assertIn("scheduled", planning)
            fields = planning["fields"]
            subjects = planning["subject"]
            self.assertTrue(
                any(field["field"] == "sttpicturewhatabout" for field in fields)
            )
            self.assertTrue(
                any(field["field"] == "sttregistrationinfo" for field in fields)
            )
            self.assertTrue(
                any(
                    subject.get("scheme") == "sttdoesphotographerknow"
                    for subject in subjects
                )
            )
            self.assertTrue(
                any(
                    subject.get("scheme") == "sttpictureregistrationok"
                    for subject in subjects
                )
            )

            formatter.exclude_internal_coverage_fields(item)

            self.assertNotIn("headline", planning)
            self.assertNotIn("location", planning)
            self.assertNotIn("internal_note", planning)
            self.assertIn("scheduled", planning)
            fields_after = planning["fields"]
            subjects_after = planning["subject"]
            self.assertFalse(
                any(field["field"] == "sttpicturewhatabout" for field in fields_after)
            )
            self.assertFalse(
                any(field["field"] == "sttregistrationinfo" for field in fields_after)
            )
            self.assertFalse(
                any(
                    subject.get("scheme") == "sttdoesphotographerknow"
                    for subject in subjects_after
                )
            )
            self.assertFalse(
                any(
                    subject.get("scheme") == "sttpictureregistrationok"
                    for subject in subjects_after
                )
            )

    async def test_map_agendas(self):
        async with self.app.app_context():
            formatter = STTJsonPlanningFormatter()
            item = self.get_sample_item()

            self.assertEqual(item["agendas"], [])

            formatter.map_agenda_output(item)
            expected_agendas = [
                {
                    "_id": "julkishallinnontiedotepalvelu",
                    "name": "Julkishallinnon tiedotepalvelu",
                },
                {"_id": "673f47ba1562ef05527e195c", "name": "Urheilu"},
                {"_id": "673f47982c95fe4cab8ee67e", "name": "Muut kuin urheilu"},
            ]
            self.assertEqual(item["agendas"], expected_agendas)
