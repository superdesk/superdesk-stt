
import os

from lxml import etree
from stt.parser import STTParser
from superdesk.tests import TestCase


class STTParseTestCase(TestCase):
    fixture = 'stt_newsml_location_test.xml'

    def setUp(self):
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, 'fixtures', self.fixture)
        provider = {'name': 'Test'}
        with open(fixture, 'rb') as f:
            parser = STTParser()
            self.xml_root = etree.parse(f).getroot()
            self.item = parser.parse(self.xml_root, provider)[0]

    def test_location_parsing(self):
        subject = self.item['subject']

        locality = next((subj for subj in subject if subj.get('qcode') == '392'))
        self.assertEqual('Tallinna', locality['name'])
        self.assertEqual('locality', locality['scheme'])

        with self.assertRaises(StopIteration):
            next((subj for subj in subject if subj.get('scheme') == 'state'))

        country = next((subj for subj in subject if subj.get('qcode') == '238'))
        self.assertEqual('Viro', country['name'])
        self.assertEqual('country', country['scheme'])

        region = next((subj for subj in subject if subj.get('qcode') == '150'))
        self.assertEqual('Eurooppa', region['name'])
        self.assertEqual('world_region', region['scheme'])

        rich = next((subj for subj in subject if subj.get('qcode') == '20016'))
        self.assertEqual('Myanmar', rich['name'])
        self.assertEqual('sttlocmeta', rich['scheme'])

        rich_reg = next((subj for subj in subject if subj.get('qcode') == '142'))
        self.assertEqual('Aasia', rich_reg['name'])
        self.assertEqual('world_region', rich_reg['scheme'])

    def test_extra_fields(self):
        self.assertEqual(self.item['urgency'], 3)
        self.assertEqual(self.item['extra']['sttidtype_textid'], '117616076')
        self.assertEqual(self.item['extra']['newsItem_guid'], 'urn:newsml:stt.fi:20170131:101159380')
        self.assertEqual(self.item['extra']['creator_name'], 'Areva Mari')
        self.assertEqual(self.item['extra']['creator_id'], 'stteditorid:26634')
        self.assertEqual(self.item['extra']['filename'], '1029359.jpg')
        self.assertEqual(self.item['extra']['stt_topics'], '490933')
        self.assertEqual(self.item['extra']['stt_events'], '213870')
        self.assertEqual(self.item['extra']['sttrating_webprio'], 4)
        self.assertEqual(self.item['extra']['imagetype']['id'], '20')
        self.assertEqual(self.item['extra']['imagetype']['name'], 'Kuvaaja paikalla')
