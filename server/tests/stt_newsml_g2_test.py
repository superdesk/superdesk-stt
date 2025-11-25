from tests import TestCase
import lxml.etree as etree

from stt.publish.stt_newsml_g2 import format_filename, STTNewsmLG2Formatter


def test_format_filename():
    assert "foo.jpg" == format_filename({"media": "foo.jpg", "mimetype": "image/jpeg"})
    assert "foo.jpg" == format_filename({"media": "foo.jpg", "mimetype": "image/jpeg"})
    assert "test-foo.jpg" == format_filename(
        {"media": "test/foo.jpeg", "mimetype": "image/jpeg"}
    )


class TestSTTNewsmLG2Formatter(TestCase):

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

        formatter = STTNewsmLG2Formatter()
        xml = await formatter.format(article, {})
        assert xml[0][1]
        print("XML", xml[0][1])

        root = etree.fromstring(xml[0][1].encode("utf-8"))
        assert root

        link = root.find("itemMeta", namespaces=root.nsmap).find(
            "link[@rel='seeAlso']", namespaces=root.nsmap
        )
        assert link is not None
        assert link.attrib.get("residref") == "image-guid"
        assert link.attrib.get("contenttype") == "image/jpeg"

        description = link.find("title", namespaces=root.nsmap)
        assert description is not None
        assert description.text == "Info"

        filename = link.find("filename", namespaces=root.nsmap)
        assert filename is not None
        assert filename.text == "test-original.jpg"
