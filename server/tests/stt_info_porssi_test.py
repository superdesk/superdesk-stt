from tests import TestCase
from stt.stt_info_porssi import STTInfoPorssi


class STTInfoPorssiParserTestCase(TestCase):
    fixture = "stt_info_porssi_3866383609.xml"  # Use the existing fixture
    parser_class = STTInfoPorssi

    def test_headline_extracted(self):
        # Test that the source name is extracted correctly
        expected_source = "LapWall Oyj"
        assert self.item["name"] == expected_source

    def test_guid_exists(self):
        # Test that GUID is extracted correctly with prefix
        expected_guid = "stt-info-porssi_stt:announcement:8067-fi"
        assert self.item["guid"] == expected_guid

    def test_language_detected(self):
        # Test that language is detected correctly as Finnish
        assert self.item["language"] == "fi"

    def test_source_and_priority(self):
        # Test that source and priority are set correctly
        assert self.item["source"] == "STT"
        assert self.item["priority"] == 3

    def test_required_fields_present(self):
        # Test that all required fields are present
        required_fields = [
            "guid",
            "name",
            "source",
            "priority",
            "language",
            "original_xml",
        ]
        for field in required_fields:
            assert field in self.item, f"Required field '{field}' is missing"

    def test_body_html_processed(self):
        # Test that body_html contains processed content (not placeholder)
        assert self.item["body_html"] != "<p>Handled by XSLT</p>"
        assert len(self.item["body_html"]) > 0
        # Should contain the category and processed HTML content
        assert "Yhtiötiedote" in self.item["body_html"]

    def test_additional_fields(self):
        # Test additional fields that should be present
        expected_headline = "LapWall Oyj:n Arvopaperimarkkinalain 9 luvun 10 pykälän mukainen ilmoitus omistusosuudesta (Timo Pekkarinen)"
        assert (
            self.item["description"] == expected_headline
        )  # Should be same as headline
        assert "task" in self.item
        assert self.item["task"]["desk"] == "Kotimaa"
        assert "anpa_category" in self.item
        assert "subject" in self.item
        assert self.item["slugline"] == expected_headline
        assert self.item["headline"] == expected_headline
