import os

from lxml import etree

from superdesk.tests import TestCase as CoreTestCase
from stt.parser import STTParser


class TestCase(CoreTestCase):

    fixture = None
    parser_class = STTParser

    def setUp(self):
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, 'fixtures', self.fixture)
        provider = {'name': 'Test'}
        with self.ctx:
            with open(fixture, 'rb') as f:
                parser = self.parser_class()
                self.xml_root = etree.parse(f).getroot()
                self.item = parser.parse(self.xml_root, provider)[0]

    def setUpForChildren(self):
        super().setUpForChildren()
        # stt related configs
        self.app.config['HTML_TAGS_WHITELIST'] = ('h1', 'h2', 'h3', 'h4', 'h6', 'blockquote', 'figure', 'ul', 'ol',
                                                  'li', 'div', 'p', 'em', 'strong', 'i', 'b', 'a', 'pre')
