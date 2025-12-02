import lxml.etree as etree

from tests import TestCase

from stt.publish.stt_newsml_g2 import format_filename, STTNewsmLG2Formatter


def test_format_filename():
    assert "foo.jpg" == format_filename({"media": "foo.jpg", "mimetype": "image/jpeg"})
    assert "foo.jpg" == format_filename({"media": "foo.jpg", "mimetype": "image/jpeg"})
    assert "test-foo.jpg" == format_filename(
        {"media": "test/foo.jpeg", "mimetype": "image/jpeg"}
    )


class TestSTTNewsmLG2Formatter(TestCase):

    async def format_and_parse(self, article):
        formatter = STTNewsmLG2Formatter()
        xml = await formatter.format(article, {})
        assert xml[0][1]
        print("XML", xml[0][1])

        root = etree.fromstring(xml[0][1].encode("utf-8"))
        assert root
        return root

    async def test_picture_link(self):
        article = {
            "type": "text",
            "subject": [],
            "associations": {
                "featuremedia": {
                    "type": "picture",
                    "guid": "image-guid",
                    "mimetype": "image/jpeg",
                    "description_text": "Info",
                    "renditions": {
                        "original": {
                            "media": "test/original.jpg",
                            "mimetype": "image/jpeg",
                        },
                        "baseImage": {
                            "media": "test/baseimage.jpg",
                            "mimetype": "image/jpeg",
                        },
                    },
                },
            },
        }

        newsml = await self.format_and_parse(article)

        link = newsml.find("itemMeta", namespaces=newsml.nsmap).find(
            "link[@rel='seeAlso']", namespaces=newsml.nsmap
        )
        assert link is not None
        assert link.attrib.get("residref") == "image-guid"
        assert link.attrib.get("contenttype") == "image/jpeg"

        description = link.find("title", namespaces=newsml.nsmap)
        assert description is not None
        assert description.text == "Info"

        filename = link.find("filename", namespaces=newsml.nsmap)
        assert filename is not None
        assert filename.text == "test-original.jpg"

    async def test_signal_correct(self):
        article = {
            "type": "text",
            "guid": "correction",
            "version": 123,
            "state": "corrected",
        }
        newsml = await self.format_and_parse(article)
        item_meta = newsml.find("itemMeta", namespaces=newsml.nsmap)
        signal = item_meta.find("signal", namespaces=newsml.nsmap)
        assert signal is not None
        assert signal.get("qcode") == "sig:corrected"
        link = signal.find("link", namespaces=newsml.nsmap)
        assert link is not None
        assert link.get("guidref") == "urn:newsml:stt.fi::correction"
        assert link.get("version") == "123"

    async def test_signal_update(self):
        # with self.app.app_context():
        self.app.data.insert(
            "archive",
            [
                {"_id": "original", "type": "text", "guid": "original"},
                {
                    "_id": "update",
                    "type": "text",
                    "guid": "update",
                    "rewrite_of": "original",
                },
            ],
        )
        article = {
            "type": "text",
            "guid": "another",
            "version": 123,
            "rewrite_of": "update",
        }
        newsml = await self.format_and_parse(article)
        assert newsml.get("guid") == "urn:newsml:stt.fi::original"
        item_meta = newsml.find("itemMeta", namespaces=newsml.nsmap)
        signal = item_meta.find("signal", namespaces=newsml.nsmap)
        assert signal is not None
        assert signal.get("qcode") == "sig:update"
        link = signal.find("link", namespaces=newsml.nsmap)
        assert link is not None
        assert link.get("guidref") == "urn:newsml:stt.fi::original"

    async def test_ednote_error(self):
        article = {
            "type": "text",
            "guid": "ednote-test",
            "ednote": None,
            "subject": [
                {
                    "name": "Mittaversio (printtiin)",
                    "qcode": "printformat",
                    "scheme": "sttnewsroomnote",
                },
            ],
        }
        newsml = await self.format_and_parse(article)
        assert newsml is not None
        item_meta = newsml.find("itemMeta", namespaces=newsml.nsmap)
        ednotes = item_meta.findall("edNote", namespaces=newsml.nsmap)
        assert 2 == len(ednotes)
        assert ednotes[1].text == "Mittaversio (printtiin)."
        assert ednotes[1].get("role") == "sttnote:private"

    async def test_subheadline_error(self):
        article = {
            "type": "text",
            "guid": "subheadline-test",
            "extra": {"sttsubheadline": "<p><b>Subheadline.</b></p>"},
            "body_html": "<p>Body</p>",
        }
        newsml = await self.format_and_parse(article)
        assert newsml is not None
        contentSet = etree.tostring(
            newsml.find("contentSet", namespaces=newsml.nsmap), encoding="unicode"
        )
        assert "<h2>Subheadline.</h2>" in contentSet
