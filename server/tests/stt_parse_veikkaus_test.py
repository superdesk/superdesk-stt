# tests/stt_parse_veikkaus_text_test.py
import os
import tempfile
from pathlib import Path
from tests import TestCase

from stt.stt_parse_lottery_veikkaus import (
    VeikkausTextFeedParser,
    to_body_html,
    fix_encoding_issues,
)


class VeikkausTextFeedParserTestCase(TestCase):
    fixture = "txt/pelitulos.Y_06.08.2022.txt"
    parser_class = VeikkausTextFeedParser
    parse_source = False  # Don't parse fixture as XML

    def setUp(self):
        super().setUp()
        self.parser = self.parser_class()
        # Get fixture file path
        dirname = os.path.dirname(os.path.realpath(__file__))
        self.fixture_path = os.path.join(dirname, "fixtures", self.fixture)
        # Create temp directory for additional test files
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super().tearDown()
        # Clean up temporary directory
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_fixture_file_parsing(self):
        """Test parsing the actual fixture file."""
        items = self.parser.parse(self.fixture_path)
        self.assertEqual(len(items), 1)
        item = items[0]

        # Test that headline is first line of fixture
        self.assertEqual(item["headline"], "TOTO75-ravi")
        self.assertIn("<p>", item["body_html"])
        self.assertEqual(item["description_text"], "pelitulos.Y_06.08.2022.txt")
        self.assertEqual(item["urgency"], 4)
        self.assertEqual(item["extra"]["veikkaus"]["department"], "Peliuutiset")

        # Test that body contains expected content
        self.assertIn("Voitonjako:", item["body_html"])
        self.assertIn("Special Major", item["body_html"])
        # Test that encoding issues are fixed
        self.assertIn("lähtö:", item["body_html"])
        self.assertNotIn("l‰htˆ:", item["body_html"])

    def test_can_parse_method(self):
        """Test the can_parse method with the fixture file."""
        self.assertTrue(self.parser.can_parse(self.fixture_path))

    def test_metadata_fields(self):
        """Test all metadata fields are properly set."""
        items = self.parser.parse(self.fixture_path)
        item = items[0]

        # Test all required fields
        self.assertEqual(item["type"], "text")
        self.assertEqual(item["original_source"], "STT")
        self.assertEqual(item["pubstatus"], "usable")
        self.assertEqual(item["slugline"], "Veikkaus")
        self.assertEqual(item["keywords"], ["Veikkaus", "lottery"])
        self.assertEqual(item["extra"]["veikkaus"]["desk"], "Kotimaa")
        self.assertEqual(
            item["extra"]["veikkaus"]["filename"], "pelitulos.Y_06.08.2022.txt"
        )

    def test_body_html_structure(self):
        """Test the HTML body structure and content."""
        items = self.parser.parse(self.fixture_path)
        item = items[0]

        body_html = item["body_html"]
        # Should start with <p> and contain the first line
        self.assertTrue(body_html.startswith("<p>TOTO75-ravi<br/>"))
        self.assertTrue(body_html.endswith("</p>"))
        # Should contain br tags for line breaks
        self.assertIn("<br/>", body_html)
        # Should contain all major content
        self.assertIn("Lauantai 06.08", body_html)
        self.assertIn("Oikea rivi:", body_html)

    def test_xml_wrapped_format(self):
        """Test parsing XML-wrapped text format."""
        xml_content = "<root><p>Keno tulokset\nArvotut numerot: 1, 5, 12, 23\nVoittajia 5 kpl</p></root>"
        temp_file = Path(self.temp_dir) / "test_xml.xml"
        temp_file.write_text(xml_content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Keno tulokset")
        self.assertIn("Arvotut numerot:", item["body_html"])
        self.assertIn("Voittajia 5 kpl", item["body_html"])
        self.assertTrue(item["body_html"].startswith("<p>"))
        self.assertTrue(item["body_html"].endswith("</p>"))

    def test_empty_file_handling(self):
        """Test handling of empty files."""
        temp_file = Path(self.temp_dir) / "empty.txt"
        temp_file.write_text("", encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Veikkaus")  # Default fallback
        self.assertEqual(item["body_html"], "<p></p>")

    def test_whitespace_only_file(self):
        """Test handling of files with only whitespace."""
        temp_file = Path(self.temp_dir) / "whitespace.txt"
        temp_file.write_text("   \n\n  \t  \n   ", encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Veikkaus")  # Default fallback
        self.assertEqual(item["body_html"], "<p></p>")  # Whitespace trimmed

    def test_single_line_file(self):
        """Test parsing of single-line files."""
        temp_file = Path(self.temp_dir) / "single_line.txt"
        temp_file.write_text("Eurojackpot tulokset", encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Eurojackpot tulokset")
        self.assertEqual(item["body_html"], "<p>Eurojackpot tulokset</p>")

    def test_special_characters_and_encoding(self):
        """Test handling of special characters and Finnish text."""
        content = "Älypää-arvonta\nVoittajat: Jääkiekko Ässät\nÄänestä parasta: ÖÄÅ"
        temp_file = Path(self.temp_dir) / "special_chars.txt"
        temp_file.write_text(content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Älypää-arvonta")
        self.assertIn("Jääkiekko Ässät", item["body_html"])
        self.assertIn("ÖÄÅ", item["body_html"])

    def test_multiple_empty_lines(self):
        """Test handling of multiple empty lines."""
        content = "Lotto\n\n\nOikeat numerot:\n\n1, 2, 3\n\n\n"
        temp_file = Path(self.temp_dir) / "empty_lines.txt"
        temp_file.write_text(content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Lotto")
        # Should preserve empty lines as <br/> but trim trailing ones
        self.assertIn("<br/>\n<br/>\n<br/>", item["body_html"])
        self.assertNotIn("1, 2, 3<br/>\n<br/>\n<br/></p>", item["body_html"])

    def test_different_line_endings(self):
        """Test handling of different line ending formats."""
        # Test Windows line endings
        content_windows = "Vikinglotto\r\nTulokset:\r\n1, 2, 3"
        temp_file = Path(self.temp_dir) / "windows_endings.txt"
        temp_file.write_bytes(content_windows.encode("utf-8"))

        items = self.parser.parse(str(temp_file))
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item["headline"], "Vikinglotto")
        self.assertIn("Tulokset:", item["body_html"])

    def test_can_parse_different_extensions(self):
        """Test can_parse method with different file extensions."""
        # Test .txt files
        txt_file = Path(self.temp_dir) / "test.txt"
        txt_file.write_text("test", encoding="utf-8")
        self.assertTrue(self.parser.can_parse(str(txt_file)))

        # Test .xml files
        xml_file = Path(self.temp_dir) / "test.xml"
        xml_file.write_text("<root><p>test</p></root>", encoding="utf-8")
        self.assertTrue(self.parser.can_parse(str(xml_file)))

        # Test other extensions
        other_file = Path(self.temp_dir) / "test.doc"
        other_file.write_text("test", encoding="utf-8")
        self.assertFalse(self.parser.can_parse(str(other_file)))

    def test_can_parse_xml_content_detection(self):
        """Test can_parse method with XML content detection."""
        # File without extension but with XML content
        xml_content = "<root><p>Veikkaus content</p></root>"
        no_ext_file = Path(self.temp_dir) / "noextension"
        no_ext_file.write_text(xml_content, encoding="utf-8")
        self.assertTrue(self.parser.can_parse(str(no_ext_file)))

        # File without extension and no XML content
        plain_file = Path(self.temp_dir) / "plainfile"
        plain_file.write_text("Just plain text", encoding="utf-8")
        self.assertFalse(self.parser.can_parse(str(plain_file)))

    def test_guid_generation(self):
        """Test GUID generation is stable and unique."""
        temp_file = Path(self.temp_dir) / "test_guid.txt"
        temp_file.write_text("Test content", encoding="utf-8")

        items1 = self.parser.parse(str(temp_file))
        items2 = self.parser.parse(str(temp_file))

        # GUID should be stable (same for same file)
        self.assertEqual(items1[0]["guid"], items2[0]["guid"])

        # GUID should contain filename reference
        self.assertIn("test_guid.txt", items1[0]["guid"])

    def test_filename_handling(self):
        """Test various filename scenarios."""
        # Test with special characters in filename
        special_file = Path(self.temp_dir) / "veikkaus_ääkköset_2024.txt"
        special_file.write_text("Test content", encoding="utf-8")

        items = self.parser.parse(str(special_file))
        item = items[0]

        self.assertEqual(item["description_text"], "veikkaus_ääkköset_2024.txt")
        self.assertEqual(
            item["extra"]["veikkaus"]["filename"], "veikkaus_ääkköset_2024.txt"
        )

    def test_to_body_html_function(self):
        """Test the to_body_html utility function directly."""
        # Test normal content
        lines = ["Line 1", "Line 2", "Line 3"]
        result = to_body_html(lines)
        self.assertEqual(result, "<p>Line 1<br/>\nLine 2<br/>\nLine 3</p>")

        # Test with empty lines at end
        lines_with_empty = ["Content", "", ""]
        result = to_body_html(lines_with_empty)
        self.assertEqual(result, "<p>Content</p>")

        # Test empty list
        result = to_body_html([])
        self.assertEqual(result, "<p></p>")

        # Test with whitespace
        lines_with_whitespace = ["  Content  ", "  "]
        result = to_body_html(lines_with_whitespace)
        self.assertEqual(result, "<p>  Content</p>")

    def test_error_handling_nonexistent_file(self):
        """Test error handling for non-existent files."""
        nonexistent_file = "/path/that/does/not/exist.txt"

        with self.assertRaises(FileNotFoundError):
            self.parser.parse(nonexistent_file)

    def test_parser_attributes(self):
        """Test parser class attributes."""
        self.assertEqual(self.parser.NAME, "veikkaus_text")
        self.assertEqual(self.parser.label, "STT Veikkaus Text Parser")

    def test_provider_parameter(self):
        """Test parse method with provider parameter."""
        temp_file = Path(self.temp_dir) / "provider_test.txt"
        temp_file.write_text("Provider test", encoding="utf-8")

        provider = {"name": "Test Provider", "config": {}}
        items = self.parser.parse(str(temp_file), provider)

        self.assertEqual(len(items), 1)
        # Provider doesn't affect the output in current implementation
        self.assertEqual(items[0]["headline"], "Provider test")

    def test_long_content_handling(self):
        """Test handling of long content."""
        # Create content with many lines
        lines = [
            f"Line {i}: Content with lottery numbers {i}, {i+1}, {i+2}"
            for i in range(100)
        ]
        content = "\n".join(lines)

        temp_file = Path(self.temp_dir) / "long_content.txt"
        temp_file.write_text(content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        item = items[0]

        self.assertEqual(
            item["headline"], "Line 0: Content with lottery numbers 0, 1, 2"
        )
        # Body should contain all lines
        self.assertIn("Line 99:", item["body_html"])
        # Should have proper HTML structure
        self.assertTrue(item["body_html"].startswith("<p>"))
        self.assertTrue(item["body_html"].endswith("</p>"))

    def test_mixed_content_with_numbers(self):
        """Test content with lottery-style numbers and formatting."""
        content = """Eurojackpot-arvonta 15.1.2025
Arvontapäivä: Tiistai
Päävoittaja: Ei voittajia

Oikeat numerot: 7, 14, 21, 28, 35
Tähtinumerot: 3, 9

5+2 oikein: 0 voittajaa
5+1 oikein: 2 voittajaa, 123.456,78 €
4+2 oikein: 15 voittajaa, 1.234,56 €"""

        temp_file = Path(self.temp_dir) / "eurojackpot.txt"
        temp_file.write_text(content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        item = items[0]

        self.assertEqual(item["headline"], "Eurojackpot-arvonta 15.1.2025")
        self.assertIn("7, 14, 21, 28, 35", item["body_html"])
        self.assertIn("123.456,78 €", item["body_html"])
        self.assertIn("Tähtinumerot:", item["body_html"])

    def test_encoding_fixes(self):
        """Test encoding issue fixes for Finnish characters."""
        # Test the fix_encoding_issues function directly
        corrupted_text = "1. l‰htˆ: Hevonen"
        fixed_text = fix_encoding_issues(corrupted_text)
        self.assertEqual(fixed_text, "1. lähtö: Hevonen")

        # Test with file containing corrupted encoding
        corrupted_content = "TOTO75-ravi\n1. l‰htˆ: Special Major\n2. l‰htˆ: Vaellus"
        temp_file = Path(self.temp_dir) / "corrupted_encoding.txt"
        temp_file.write_text(corrupted_content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        item = items[0]

        # Should be fixed in the output
        self.assertIn("1. lähtö: Special Major", item["body_html"])
        self.assertIn("2. lähtö: Vaellus", item["body_html"])
        self.assertNotIn("l‰htˆ", item["body_html"])

    def test_fixture_encoding_correction(self):
        """Test that the fixture file's encoding issues are corrected."""
        items = self.parser.parse(self.fixture_path)
        item = items[0]

        # The fixture contains "l‰htˆ:" which should be corrected to "lähtö:"
        self.assertIn("lähtö:", item["body_html"])
        self.assertNotIn("l‰htˆ:", item["body_html"])

    def test_mixed_encoding_issues(self):
        """Test various encoding issues together."""
        mixed_content = "Lotto‰-arvonta\nVoitt‰j‰t: J‰‰kiekko ˆss‰t\nSumma: 1000€"
        temp_file = Path(self.temp_dir) / "mixed_encoding.txt"
        temp_file.write_text(mixed_content, encoding="utf-8")

        items = self.parser.parse(str(temp_file))
        item = items[0]

        # Should be corrected
        self.assertIn("Lottoä-arvonta", item["body_html"])
        self.assertIn("Voittäjät: Jääkiekko össät", item["body_html"])
        self.assertIn("1000€", item["body_html"])
