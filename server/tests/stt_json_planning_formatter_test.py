from tests import TestCase
from superdesk import get_resource_service
from stt.stt_json_planning_formatter import STTJsonPlanningFormatter


class STTJsonPlanningFormatterTest(TestCase):
    add_stt_cvs = True
    parse_source = False

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
