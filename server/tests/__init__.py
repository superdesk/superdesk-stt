import os

from lxml import etree

from superdesk.tests import TestCase as CoreTestCase
from apps.prepopulate.app_populate import AppPopulateCommand
from stt.parser import STTParser


class TestCase(CoreTestCase):

    fixture = None
    parser_class = STTParser
    add_stt_cvs = False
    parse_source = True

    def setUp(self):
        if self.add_stt_cvs:
            self.addSttCVs()

        if self.parse_source:
            self.parse_source_content()

    def parse_source_content(self):
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

    def addSttCVs(self):
        with self.app.app_context():
            cmd = AppPopulateCommand()
            filename = os.path.join(os.path.abspath(os.path.dirname("data/")), "vocabularies.json")
            cmd.run(filename)
