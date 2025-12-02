import os

from lxml import etree

from superdesk.tests import TestCase as CoreTestCase
from apps.prepopulate.app_populate import AppPopulateCommand
from stt.parser import STTParser


def fixture(filename):
    dirname = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(dirname, "fixtures", filename)


class TestCase(CoreTestCase):
    fixture = None
    parser_class = STTParser
    add_stt_cvs = False
    parse_source = True

    app_config = {
        "HTML_TAGS_WHITELIST": (
            "h1",
            "h2",
            "h3",
            "h4",
            "h6",
            "blockquote",
            "figure",
            "ul",
            "ol",
            "li",
            "div",
            "p",
            "em",
            "strong",
            "i",
            "b",
            "a",
            "pre",
        )
    }

    async def asyncSetUp(self):
        await super().asyncSetUp()
        if self.add_stt_cvs:
            await self.addSttCVs()

        if self.parse_source:
            await self.parse_source_content()

    async def parse_source_content(self):
        if not self.fixture:
            return
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "fixtures", self.fixture)
        provider = {"name": "Test"}
        async with self.ctx:
            with open(fixture, "rb") as f:
                parser = self.parser_class()
                self.xml_root = etree.parse(f).getroot()
                parsed = await parser.parse(self.xml_root, provider)
                self.item = parsed[0]

    async def addSttCVs(self):
        async with self.app.app_context():
            cmd = AppPopulateCommand()
            filename = os.path.join(
                os.path.abspath(os.path.dirname("data/")), "vocabularies.json"
            )
            await cmd.run(filename)
