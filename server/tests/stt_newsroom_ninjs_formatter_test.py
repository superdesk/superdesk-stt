from tests import TestCase
from stt.stt_newsroom_ninjs_formatter import STTNewsroomNinjsFormatter


class STTNewsroomNinjsFormatterTest(TestCase):
    fixture = "stt_newsml_creditline_test.xml"
    add_stt_cvs = True

    async def test_source_formatting(self):
        await self.parse_source_content()
        subscriber = {
            "_id": "test_subscriber",
            "name": "Test Subscriber",
            "destinations": [{"format": "stt newsroom ninjs"}],
        }
        formatter = STTNewsroomNinjsFormatter()
        ninjs = await formatter._transform_to_ninjs(self.item, subscriber)
        self.assertEqual(ninjs["source"], "STT-AFP")

    async def test_source_formatting_no_sources_fallback(self):
        await self.parse_source_content()
        self.item["subject"] = []
        subscriber = {
            "_id": "test_subscriber",
            "name": "Test Subscriber",
            "destinations": [{"format": "stt newsroom ninjs"}],
        }
        formatter = STTNewsroomNinjsFormatter()
        ninjs = await formatter._transform_to_ninjs(self.item, subscriber)
        self.assertEqual(ninjs["source"], "STT")

    async def test_source_formatting_duplicates_handling(self):
        # ensure duplicates are removed and STT always stays first
        self.item["subject"] = [
            {"name": "STT", "scheme": "sttsource"},
            {"name": "AFP", "scheme": "sttsource"},
            {"name": "AFP", "scheme": "sttsource"},
        ]
        subscriber = {
            "_id": "test_subscriber",
            "name": "Test Subscriber",
            "destinations": [{"format": "stt newsroom ninjs"}],
        }
        formatter = STTNewsroomNinjsFormatter()
        ninjs = await formatter._transform_to_ninjs(self.item, subscriber)
        self.assertEqual(ninjs["source"], "STT-AFP")
