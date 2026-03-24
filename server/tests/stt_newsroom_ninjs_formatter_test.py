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
        self.app.data.insert(
            "content_types",
            [
                {
                    "_id": "pikaplus",
                    "editor": {"sttsubheadline": {"enabled": True}},
                },
                {
                    "_id": "viiva",
                    "editor": {"sttsubheadline": None},
                },
            ],
        )

        ninjs = {
            "extra": {
                "sttsubheadline": "<b>Subtitle</b>",
            },
            "body_html": "",
        }

        article = {"profile": "viiva"}
        self.formatter.update_subheadline(ninjs, article)
        self.assertEqual(ninjs.get("body_html", "").strip(), "")

        article = {"profile": "pikaplus"}
        self.formatter.update_subheadline(ninjs, article)
        self.assertEqual(ninjs.get("body_html", "").strip(), "<h2>Subtitle</h2>")

    async def test_update_sttversion_from_cv_match(self):
        ninjs = {"profile": "Viiva"}
        self.formatter.update_sttversion(ninjs)
        self.assertIn(
            {"name": "Viiva", "scheme": "sttversion", "code": "1"},
            ninjs.get("subject", []),
        )
        ninjs = {"profile": "pikaplus"}
        self.formatter.update_sttversion(ninjs)
        self.assertIn(
            {"name": "Pika+", "scheme": "sttversion", "code": "4"},
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
        self.assertEqual(ninjs.get("ednote"), "Ei muita versioita / Base")

    async def test_update_editorial_note_with_public_ednote(self):
        ninjs = {
            "subject": [{"scheme": "sttnewsroomnote", "name": "Newsroom note"}],
            "extra": {"sttpublicednote": "<p>Public note</p>"},
            "ednote": "Base",
        }
        self.formatter.update_editorial_note(ninjs)
        self.assertEqual(ninjs.get("ednote"), "Public note / Newsroom note / Base")

    async def test_update_editorial_note_public_ednote_only(self):
        ninjs = {
            "subject": [],
            "extra": {"sttpublicednote": "Public note"},
        }
        self.formatter.update_editorial_note(ninjs)
        self.assertEqual(ninjs.get("ednote"), "Public note")

    async def test_update_editorial_note_public_ednote_nbsp(self):
        ninjs = {
            "subject": [],
            "extra": {"sttpublicednote": "<p>&nbsp;Public note</p>"},
        }
        self.formatter.update_editorial_note(ninjs)
        self.assertEqual(ninjs.get("ednote"), "Public note")

    async def test_update_editorial_note_no_notes(self):
        ninjs = {"subject": [], "ednote": "Base"}
        self.formatter.update_editorial_note(ninjs)
        self.assertEqual(ninjs.get("ednote"), "Base")

    async def test_no_slugline(self):
        article = {"slugline": "foo", "type": "text", "guid": "test"}
        ninjs = await self.formatter._transform_to_ninjs(article, {})
        assert "slugline" not in ninjs

    async def test_filter_subjects(self):
        article = {
            "type": "text",
            "guid": "test",
            "subject": [
                {"name": "Test", "scheme": "sttversion"},
                {"name": "Other", "scheme": "stttopstory"},
                {"name": "Source", "scheme": "sttsource"},
                {"name": "Source", "scheme": "sttdepartment"},
                {"name": "Source", "scheme": "sttsubject"},
                {"name": "Koripallo", "scheme": "sttsubj"},
                {"name": "Source", "scheme": "sttdone1"},
            ],
        }
        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(
            [{"name": "Test", "scheme": "sttversion"}],
            ninjs.get("subject", []),
        )

    async def test_special_characters(self):
        article = {
            "type": "text",
            "guid": "test",
            "headline": "Test\u2013text with tab\tand thinsp\u2009and editorial---agreement¤.",
            "body_html": "Test\u2013text with tab\tand thinsp\u2009and editorial---agreement¤.",
        }
        ninjs = await self.formatter._transform_to_ninjs(article, {})
        self.assertEqual(
            "Test\u2013text with tab\tand thinsp\u2009and editorial\u2013agreement\u2009.",
            ninjs.get("headline", ""),
        )
        self.assertEqual(
            "Test&#8211;text with tab&#9;and thinsp&#8201;and editorial&#8211;agreement&#8201;.",
            ninjs.get("body_html", ""),
        )

    async def test_place(self):
        article = {
            "type": "text",
            "guid": "test",
            "place": [
                {
                    "name": "Suomi",
                    "qcode": "sttcountry:1",
                },
                {
                    "name": "Alajärvi",
                    "qcode": "sttcity:1",
                },
            ],
        }

        ninjs = await self.formatter._transform_to_ninjs(article, {})

        self.assertIn(
            {
                "name": "Suomi",
                "code": "sttcountry:1",
            },
            ninjs.get("place", []),
        )
