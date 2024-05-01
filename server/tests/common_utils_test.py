from . import TestCase
from stt.common import is_online_version


class CommonUtilsTest(TestCase):
    parse_source = False

    def test_is_online_version(self):
        self.fixture = "stt_newsml_link_content.xml"
        self.parse_source_content()
        self.assertFalse(is_online_version(self.item))

        self.fixture = "stt_newsml_online_version.xml"
        self.parse_source_content()
        self.assertTrue(is_online_version(self.item))
