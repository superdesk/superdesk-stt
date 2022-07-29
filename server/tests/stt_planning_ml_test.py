from tests import TestCase
from stt.stt_planning_ml import STTPlanningMLParser


class STTPlanningMLParserTest(TestCase):
    fixture = "planning_ml_584717.xml"
    parser_class = STTPlanningMLParser
    add_stt_cvs = True

    def test_stt_metadata(self):
        # Extra metadata
        self.assertEqual(self.item["extra"]["stt_events"], "259431")
        self.assertEqual(self.item["extra"]["stt_topics"], "584717")

        # Subjects (only ``sttdepartment`` found in provided xml files)
        self.assertIn({"qcode": "9", "name": "Politiikka", "scheme": "sttdepartment"}, self.item["subject"])

        # Associated Event ID
        self.assertEqual(self.item["event_item"], "urn:newsml:stt.fi:20220402:259431")
