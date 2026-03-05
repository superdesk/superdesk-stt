import unittest
from stt.template_filters import count_body_html_characters


class TemplateFiltersTest(unittest.TestCase):
    def test_count_body_html_characters(self):
        # Empty inputs
        self.assertEqual(count_body_html_characters(None), 0)
        self.assertEqual(count_body_html_characters(""), 0)

        # Simple text
        self.assertEqual(count_body_html_characters("Hello world"), 11)

        # Text with HTML paragraphs
        self.assertEqual(count_body_html_characters("<p>Hello world</p>"), 11)

        # Text with line breaks
        self.assertEqual(count_body_html_characters("Hello<br>world"), 11)
        self.assertEqual(count_body_html_characters("Hello<br/>world"), 11)
        self.assertEqual(count_body_html_characters("Hello<br />world"), 11)

        # Text with embeds
        self.assertEqual(
            count_body_html_characters(
                "start <!-- EMBED START 123 <!-- EMBED END --> end"
            ),
            10,  # 'start  end' is 10 characters
        )

        # Text with newlines and carriage returns
        # "Hello\nworld" -> strip `\n` -> "Helloworld" -> 10 chars
        self.assertEqual(count_body_html_characters("Hello\nworld"), 10)
        self.assertEqual(count_body_html_characters("Hello\r\nworld"), 10)

        # HTML entities
        # "A &amp; B" -> unescaped to "A & B" -> 5 chars
        self.assertEqual(count_body_html_characters("A &amp; B"), 5)

        # Multiple tags
        self.assertEqual(count_body_html_characters("<div><span>test</span></div>"), 4)


if __name__ == "__main__":
    unittest.main()
