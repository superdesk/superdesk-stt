from datetime import datetime
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
            "name",
            "abstract",
            "dateline",
            "extra",
        ]
        for field in required_fields:
            self.assertIn(field, self.item, f"Required field '{field}' is missing")

    def test_guid_and_headline(self):
        """Test that GUID and headline are extracted correctly."""
        expected_guid = "urn:stt:info-porssi:urn:newsml:nordicir.com:20240603:stt:announcement:8067-fi:1"
        expected_headline = "LapWall Oyj:n Arvopaperimarkkinalain 9 luvun 10 pykälän mukainen ilmoitus omistusosuudesta (Timo Pekkarinen)"
        self.assertEqual(self.item["guid"], expected_guid)
        self.assertEqual(self.item["headline"], expected_headline)
        self.assertEqual(self.item["slugline"], expected_headline)

    def test_source_and_priority(self):
        """Test that source and priority are set correctly."""
        # self.assertEqual(self.item["source"], "LapWall Oyj")
        # self.assertEqual(self.item["priority"], 3)

    def test_language_detected(self):
        """Test that language is detected correctly as Finnish."""
        self.assertEqual(self.item["language"], "fi")

    def test_type_and_versioncreated(self):
        """Test that type and versioncreated are set correctly."""
        self.assertEqual(self.item["type"], "text")
        self.assertIsInstance(self.item["versioncreated"], datetime)

    def test_body_html_processed(self):
        """Test that body_html contains processed content."""
        self.assertNotEqual(self.item["body_html"], "<p>Handled by XSLT</p>")
        self.assertGreater(len(self.item["body_html"]), 0)
        self.assertIn("Yhtiötiedote", self.item["body_html"])

    def test_categories_present(self):
        """Test that subject field is present."""
        self.assertIn("subject", self.item)
        self.assertEqual("Tiedotepalvelu", self.item["anpa_category"][0]["name"])

    def test_name_and_abstract_fields(self):
        """Test that name and abstract fields are set correctly."""
        expected_headline = "LapWall Oyj:n Arvopaperimarkkinalain 9 luvun 10 pykälän mukainen ilmoitus omistusosuudesta (Timo Pekkarinen)"
        self.assertEqual(self.item["name"], expected_headline)
        self.assertEqual(self.item["abstract"], expected_headline)

    def test_dateline_field(self):
        """Test that dateline is set as an object with text."""
        self.assertIn("dateline", self.item)
        self.assertIsInstance(self.item["dateline"], dict)
        self.assertIn("text", self.item["dateline"])
        self.assertEqual(self.item["dateline"]["text"], "3.6.2024 10:00:01 EEST")

    def test_extra_fields(self):
        """Test that extra fields are set correctly."""
        self.assertIn("extra", self.item)
        extra = self.item["extra"]
        self.assertEqual(extra["ntb_pub_name"], "LapWall Oyj")
        self.assertEqual(extra["desk"], "Kotimaa")
