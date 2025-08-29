from tests import TestCase
from stt.stt_info_porssi import STTInfoPorssi


class STTInfoPorssiParserTestCase(TestCase):
    fixture = "stt_info_porssi_3866383609.xml"
    parser_class = STTInfoPorssi

    def test_required_fields_present(self):
        """Test that all required fields are present."""
        required_fields = [
            "guid",
            "headline",
            "slugline",
            "body_html",
            "source",
            "priority",
            "language",
            "type",
            "versioncreated",
        ]
        for field in required_fields:
            self.assertIn(field, self.item, f"Required field '{field}' is missing")

    def test_guid_and_headline(self):
        """Test that GUID and headline are extracted correctly."""
        expected_guid = "stt-info-porssi_stt:announcement:8067-fi"
        expected_headline = "LapWall Oyj:n Arvopaperimarkkinalain 9 luvun 10 pykälän mukainen ilmoitus omistusosuudesta (Timo Pekkarinen)"
        self.assertEqual(self.item["guid"], expected_guid)
        self.assertEqual(self.item["headline"], expected_headline)
        self.assertEqual(self.item["slugline"], expected_headline)

    def test_source_and_priority(self):
        """Test that source and priority are set correctly."""
        self.assertEqual(self.item["source"], "LapWall Oyj")
        self.assertEqual(self.item["priority"], 3)

    def test_language_detected(self):
        """Test that language is detected correctly as Finnish."""
        self.assertEqual(self.item["language"], "fi")

    def test_type_and_versioncreated(self):
        """Test that type and versioncreated are set correctly."""
        self.assertEqual(self.item["type"], "text")
        self.assertIsInstance(self.item["versioncreated"], str)

    def test_body_html_processed(self):
        """Test that body_html contains processed content."""
        self.assertNotEqual(self.item["body_html"], "<p>Handled by XSLT</p>")
        self.assertGreater(len(self.item["body_html"]), 0)
        self.assertIn("Yhtiötiedote", self.item["body_html"])

    def test_categories_present(self):
        """Test that category fields are present."""
        self.assertIn("anpa_category", self.item)
        self.assertIn("subject", self.item)
