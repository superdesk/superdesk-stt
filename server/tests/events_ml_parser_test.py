from tests import TestCase
from stt.stt_events_ml import STTEventsMLParser


class STTEventsMLParserTest(TestCase):
    fixture = 'events_ml_259431.xml'
    parser_class = STTEventsMLParser

    def test_subjects(self):
        self.assertEqual(self.item["extra"]["stt_events"], "259431")
        self.assertEqual(self.item["extra"]["stt_topics"], "584717")

        subjects = self.item["subject"]
        self.assertEqual(len(subjects), 6)

        expected_subjects = [
            {"qcode": "9", "name": "Politiikka", "scheme": "sttdepartment"},
            {"qcode": "11000000", "name": "Politiikka", "scheme": "sttsubj"},
            {"qcode": "11010000", "name": "Puolueet Yhteiskunnalliset liikkeet ", "scheme": "sttsubj"},
            {"qcode": "11000000", "name": "Politiikka", "scheme": "sttsubj"},
            {"qcode": "11006000", "name": "Julkinen hallinto", "scheme": "sttsubj"},
            {"qcode": "11006009", "name": "Ministerit", "scheme": "sttsubj"},
        ]
        for subject in expected_subjects:
            self.assertIn(subject, subjects)
