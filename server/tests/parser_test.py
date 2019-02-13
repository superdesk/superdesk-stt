
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

        locality = next((subj for subj in subject if subj.get('scheme') == 'locality'))
        self.assertEqual('Tallinna', locality['name'])
        self.assertEqual('392', locality['qcode'])

        with self.assertRaises(StopIteration):
            next((subj for subj in subject if subj.get('scheme') == 'state'))

        country = next((subj for subj in subject if subj.get('scheme') == 'country'))
        self.assertEqual('Viro', country['name'])
        self.assertEqual('238', country['qcode'])
