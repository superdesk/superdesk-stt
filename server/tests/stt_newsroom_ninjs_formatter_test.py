from tests import TestCase
from stt.stt_newsroom_ninjs_formatter import STTNewsroomNinjsFormatter


class STTNewsroomNinjsFormatterTest(TestCase):
    fixture = "stt_newsml_creditline_test.xml"
    add_stt_cvs = True
    formatter = STTNewsroomNinjsFormatter()

    def get_subscriber(self):
        return {
            "_id": "test_subscriber",
            "name": "Test Subscriber",
            "destinations": [{"format": "stt newsroom ninjs"}],
        }

    async def test_source_formatting(self):
        await self.parse_source_content()
        subscriber = self.get_subscriber()

        ninjs = await self.formatter._transform_to_ninjs(self.item, subscriber)
        self.assertEqual(ninjs["source"], "STT-AFP")

    async def test_source_formatting_no_sources_fallback(self):
        await self.parse_source_content()
        self.item["subject"] = []
        subscriber = self.get_subscriber()

        ninjs = await self.formatter._transform_to_ninjs(self.item, subscriber)
        self.assertEqual(ninjs["source"], "STT")

    async def test_source_formatting_duplicates_handling(self):
        await self.parse_source_content()
        # ensure duplicates are removed and STT always stays first
        self.item["subject"] = [
            {"name": "STT", "scheme": "sttsource"},
            {"name": "AFP", "scheme": "sttsource"},
            {"name": "AFP", "scheme": "sttsource"},
        ]
        subscriber = self.get_subscriber()

        ninjs = await self.formatter._transform_to_ninjs(self.item, subscriber)
        self.assertEqual(ninjs["source"], "STT-AFP")

    async def test_update_body_from_content_profiles(self):
        ninjs = {
            "profile": "viiva",
            "headline": "Breaking News",
            "body_html": "",
        }
        self.formatter.update_body_from_content_profiles(ninjs)
        self.assertEqual(ninjs.get("body_html"), "<p>Breaking News</p>")

    async def test_update_subheadline(self):
        ninjs = {
            "extra": {
                "sttsubheadline": "<b>Subtitle</b>",
            },
            "profile": "pikaplus",
            "body_html": "",
        }
        self.formatter.update_subheadline(ninjs)
        self.assertEqual(ninjs.get("body_html"), "<h2>Subtitle</h2>")

    async def test_update_sttversion_from_cv_match(self):
        ninjs = {"profile": "Viiva"}
        self.formatter.update_sttversion(ninjs)
        self.assertIn(
            {"name": "viiva", "scheme": "sttversion", "code": "1"},
            ninjs.get("subject", []),
        )

    async def test_update_sttversion_fallback(self):
        ninjs = {"profile": "unknown_profile"}
        self.formatter.update_sttversion(ninjs)
        self.assertNotIn(
            {"name": "unknown_profile", "scheme": "sttversion"},
            ninjs.get("subject", []),
        )

    async def test_update_editorial_note(self):
        ninjs = {
            "subject": [{"scheme": "sttnewsroomnote", "name": "Ei muita versioita"}],
            "ednote": "Base",
        }
        self.formatter.update_editorial_note(ninjs)
        self.assertEqual(ninjs.get("ednote"), "Ei muita versioita. Base")
