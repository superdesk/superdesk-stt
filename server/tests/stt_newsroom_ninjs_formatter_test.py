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

    async def test_update_place_sets_locators(self):
        ninjs = {"place": [{"code": "sttcountry:1"}, {"code": "sttcountry:2"}]}
        self.formatter.update_place(ninjs)
        self.assertEqual(ninjs.get("locators"), ["sttcountry:1", "sttcountry:2"])

    async def test_update_body_from_content_profiles(self):
        ninjs = {
            "extra": {"content_profile_name": "viiva"},
            "headline": "Breaking News",
            "body_html": "",
        }
        self.formatter.update_body_from_content_profiles(ninjs)
        self.assertEqual(ninjs.get("body_html"), "<p>Breaking News</p>")

    async def test_update_subheadline(self):
        ninjs = {
            "extra": {
                "content_profile_name": "pikaplus",
                "sttsubheadline": "<b>Subtitle</b>",
            },
            "body_html": "",
        }
        self.formatter.update_subheadline(ninjs)
        self.assertEqual(ninjs.get("body_html"), "<h2>Subtitle</h2>")

    async def test_update_sttversion_from_profile(self):
        ninjs = {"extra": {"content_profile_name": "viiva"}}
        self.formatter.update_sttversion(ninjs)
        self.assertEqual(ninjs.get("sttversion"), "viiva")

    async def test_update_sttversion_from_profile_fallback(self):
        ninjs = {"profile": "v3"}
        self.formatter.update_sttversion(ninjs)
        self.assertEqual(ninjs.get("sttversion"), "v3")

    async def test_update_editorial_note(self):
        ninjs = {
            "subject": [{"scheme": "sttnewsroomnote", "name": "Ei muita versioita"}],
            "ednote": "Base",
        }
        self.formatter.update_editorial_note(ninjs)
        self.assertEqual(ninjs.get("ednote"), "Ei muita versioita. Base")
