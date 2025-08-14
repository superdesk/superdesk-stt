from tests import TestCase
from stt.parser_hippos import HipposParser


class STTParserHipposTest(TestCase):
    fixture = "hippos_1.xml"
    parser_class = HipposParser

    def test_hippos(self):
        # Test that the headline is parsed correctly
        self.assertEqual(self.item["headline"], "Ravituloksia/Helsinki")
