from typing import Tuple, cast, Any
from tests import TestCase


class STTParserTestCase(TestCase):
    fixture = "stt_newsml_location_test.xml"
    add_stt_cvs = True

    def test_extra_fields(self):
        self.assertEqual(self.item["urgency"], 3)
        self.assertEqual(self.item["extra"]["sttidtype_textid"], "117616076")
        self.assertEqual(
            self.item["extra"]["newsItem_guid"], "urn:newsml:stt.fi:20170131:101159380"
        )
        self.assertEqual(self.item["extra"]["creator_name"], "Areva Mari")
        self.assertEqual(self.item["extra"]["creator_id"], "stteditorid:26634")
        self.assertEqual(self.item["extra"]["filename"], "1029359.jpg")
        self.assertEqual(self.item["extra"]["stt_topics"], "490933")
        self.assertEqual(self.item["extra"]["stt_events"], "213870")
        self.assertEqual(self.item["extra"]["sttrating_webprio"], 4)
        self.assertEqual(self.item["extra"]["imagetype"]["id"], "20")
        self.assertEqual(self.item["extra"]["imagetype"]["name"], "Kuvaaja paikalla")

    def test_preserve_links(self):
        body_html = self.item["body_html"]
        expected_link_text = '<a href="https://coronavirus.jhu.edu/map.html" target="_blank">Johns Hopkins </a>'
        self.assertIn(expected_link_text, body_html)

    def test_department(self):
        category = self.item["anpa_category"][0]
        self.assertEqual("9", category["qcode"])
        self.assertEqual("Politiikka", category["name"])

    def test_language(self):
        self.assertEqual("fi", self.item["language"])

    def test_mediatopics(self):
        mediatopics = [
            s["qcode"] for s in self.item["subject"] if s.get("scheme") == "topics"
        ]
        assert len(mediatopics) == len(set(mediatopics))
        assert mediatopics
        assert "11000000" in mediatopics
        assert "06000000" in mediatopics

    def test_source(self):
        sources = [s for s in self.item["subject"] if s.get("scheme") == "sttsource"]
        assert len(sources) == 1
        assert sources[0]["name"] == "STT"
        assert sources[0]["qcode"] == "STT"

    def test_place(self):
        places = [s for s in self.item["place"]]
        assert len(places) == 2
        assert places[0]["name"] == "Viro"
        assert places[0]["qcode"] == "sttcountry:238"
        assert not places[0]["scheme"]
        assert places[1]["name"] == "Suomi"
        assert places[1]["qcode"] == "sttcountry:1"
        assert not places[1]["scheme"]

    def test_genre(self):
        genres = [g for g in self.item["genre"]]
        assert len(genres) == 1
        assert genres[0]["name"] == "Uutinen"
        assert genres[0]["qcode"] == "sttgenre:1"


class STTParserHyperlinkTestCase(TestCase):
    fixture = "stt_newsml_hyperlink.xml"
    app_config: dict[str, Any] = {
        **TestCase.app_config,
        "HTML_TAGS_WHITELIST": cast(
            Tuple[str, ...],
            tuple(
                tag for tag in TestCase.app_config["HTML_TAGS_WHITELIST"] if tag != "a"
            ),
        ),
    }

    def test_preserve_anchor_href(self):
        body_html = self.item["body_html"]
        expected_link = (
            '<a href="https://www.hs.fi/politiikka/art-2000011637243.html" '
            'target="_blank">Helsingin Sanomat</a>'
        )
        self.assertIn(expected_link, body_html)


class STTParserPRETestCase(TestCase):
    fixture = "stt_newsml_pre_test.xml"

    def test_replace_pre_with_p(self):
        body_html = self.item["body_html"]
        self.assertIn("<p>It used to be a pre</p>", body_html)


class STTParserEnglishTestCase(TestCase):
    fixture = "stt_newsml_link_content_2.xml"

    def test_language(self):
        self.assertEqual("en", self.item["language"])
