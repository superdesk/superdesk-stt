from tests import TestCase
from superdesk import get_resource_service
from stt.stt_events_ml import STTEventsMLParser, search_existing_contacts


class STTEventsMLParserTest(TestCase):
    fixture = 'events_ml_259431.xml'
    parser_class = STTEventsMLParser

    def test_subjects(self):
        self.assertEqual(self.item["extra"]["stt_events"], "259431")
        self.assertEqual(self.item["extra"]["stt_topics"], "584717")

        self.assertTrue(self.item["invitation_details"].startswith("<p>"))
        url = "www.foobar.com/event/invitation"
        link = f'<a href="{url}" target="_blank">{url}</a>'
        self.assertTrue(self.item["invitation_details"].startswith("<p>"))
        self.assertIn(link, self.item["invitation_details"])

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
        self.assertEqual(location["details"], ["Knock 3 times"])


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


class STTEventsMLParserContactInfoTest(TestCase):
    fixture = 'events_ml_259431.xml'
    parser_class = STTEventsMLParser
    parse_source = False
    contact = {
        "is_active": True,
        "public": True,
        "first_name": "foo",
        "last_name": "bar",
        "contact_email": ["foo@bar.com"],
        "job_title": "Viestintäasiantuntija",
        "contact_phone": [{
            "number": "123 4567890,Mob:012-345 6789",
            "public": True,
        }],
    }

    def test_create_new_contact(self):
        # Make sure the contact doesn't already exist
        self.assertIsNone(search_existing_contacts({"contact_email": ["foo@bar.com"]}))

        # Process the source content, which should create a new contact
        self.parse_source_content()
        self.assertIsNotNone(self.item["event_contact_info"][0])

        # Make sure the created contact has the correct details
        created_contact = search_existing_contacts({"contact_email": ["foo@bar.com"]})
        self.assertIsNotNone(created_contact)
        self.assertEqual(created_contact["first_name"], self.contact["first_name"])
        self.assertEqual(created_contact["last_name"], self.contact["last_name"])
        self.assertEqual(created_contact["contact_email"], self.contact["contact_email"])
        self.assertEqual(created_contact["job_title"], self.contact["job_title"])
        self.assertEqual(created_contact["contact_phone"], self.contact["contact_phone"])

    def test_reuse_existing_contact(self):
        # Add the contact before processing the source content
        contact_id = get_resource_service("contacts").post([self.contact])[0]
        self.assertIsNotNone(search_existing_contacts({"contact_email": ["foo@bar.com"]}))

        # Process the source content, which should re-use the one in the DB
        self.parse_source_content()
        self.assertEqual(self.item["event_contact_info"][0], contact_id)
