from tests import TestCase
from stt.stt_events_ml import STTEventsMLParser


class STTEventsMLParserTest(TestCase):
    fixture = 'events_ml_259431.xml'
    parser_class = STTEventsMLParser

    def test_subjects(self):
        self.assertEqual(self.item["extra"]["stt_events"], "259431")
        self.assertEqual(self.item["extra"]["stt_topics"], "584717")

        subjects = self.item["subject"]
        self.assertEqual(len(subjects), 7)

        expected_subjects = [
            {"qcode": "9", "name": "Politiikka", "scheme": "sttdepartment"},
            {"qcode": "11000000", "name": "Politiikka", "scheme": "sttsubj"},
            {"qcode": "11010000", "name": "Puolueet Yhteiskunnalliset liikkeet ", "scheme": "sttsubj"},
            {"qcode": "11000000", "name": "Politiikka", "scheme": "sttsubj"},
            {"qcode": "11006000", "name": "Julkinen hallinto", "scheme": "sttsubj"},
            {"qcode": "11006009", "name": "Ministerit", "scheme": "sttsubj"},
            {"qcode": "21", "name": "Mediatilaisuudet", "scheme": "event_type"},
        ]
        for subject in expected_subjects:
            self.assertIn(subject, subjects)

    def test_locations(self):
        self.assertEqual(len(self.item["location"]), 1)
        location = self.item["location"][0]
        self.assertEqual(location["address"]["extra"]["sttlocationalias"], "14068")
        self.assertEqual(location["name"], "Sokos Hotel Presidentti")
        self.assertEqual(location["address"]["title"], "Sokos Hotel Presidentti")
        self.assertEqual(location["address"]["city"], "Helsinki")
        self.assertEqual(location["address"]["extra"]["sttcity"], "35")
        self.assertEqual(location["address"]["state"], "Uusimaa")
        self.assertEqual(location["address"]["extra"]["sttstate"], "31")
        self.assertEqual(location["address"]["country"], "Suomi")
        self.assertEqual(location["address"]["extra"]["sttcountry"], "1")
        self.assertEqual(location["address"]["extra"]["iso3166"], "iso3166-1a2:FI")
        self.assertEqual(location["address"]["line"][0], "Eteläinen Rautatiekatu 4")


class STTEventsMLParserEventTypeCVTest(TestCase):
    fixture = "events_ml_259431.xml"
    parser_class = STTEventsMLParser
    parse_source = False

    def test_event_type_cv_updated(self):
        self.assertIsNone(self.app.data.find_one("vocabularies", req=None, _id="event_type"))
        self.parse_source_content()
        event_types = self.app.data.find_one("vocabularies", req=None, _id="event_type")
        self.assertIsNotNone(event_types)
        self.assertIn({"qcode": "21", "name": "Mediatilaisuudet", "is_active": True}, event_types["items"])
