import logging
from datetime import datetime
from superdesk.io.registry import register_feed_parser
from superdesk.etree import etree
from superdesk.io.feed_parsers.newsml_1_2 import NewsMLOneFeedParser
from superdesk.errors import ParserError
from superdesk import etree as sd_etree
from copy import deepcopy

logger = logging.getLogger(__name__)

NEWSML_NS = "http://iptc.org/std/NewsML/2003-10-10/"


class STTInfoPorssi(NewsMLOneFeedParser):
    """STT Info Porssi XML ingest.

    STT Info Porssi is a custom NewsML 1.2 format
    """

    NAME = "stt_info_porssi"

    label = "STT Info Porssi"

    def __init__(self):
        super().__init__()
        self.default_mapping = {
            "guid": {
                "xpath": "Identification/NewsIdentifier/NewsItemId/text()",
                "filter": lambda i: "stt-info-porssi_{}".format(i),
            },
            "headline": "NewsComponent/NewsLines/HeadLine",
            "slugline": "NewsComponent/AdministrativeMetadata/Source/Party/@FormalName",
            "body_html": self.get_body,
            "name": {
                "xpath": "NewsComponent/AdministrativeMetadata/Source/Party/@FormalName",
                "key_hook": lambda item, name: item.setdefault("extra", {}).__setitem__(
                    "ntb_pub_name", name
                ),
            },
        }

    def can_parse(self, xml):
        return (
            xml.tag == "{http://iptc.org/std/NewsML/2003-10-10/}NewsML"
            and xml.get("Version", "") == "1.2"
        )

    def parse(self, xml, provider=None):
        try:
            # Remove namespace for easier XPath
            xml = deepcopy(xml)
            for elt in xml.iter():
                elt.tag = elt.tag.replace("{" + NEWSML_NS + "}", "")
            news_items = xml.findall("NewsItem")

            selected = None
            for news_item in news_items:
                try:
                    lang = news_item.xpath(
                        "NewsComponent/DescriptiveMetadata/Language/@FormalName"
                    )[0]
                except IndexError:
                    logger.warning(
                        "missing language in item, ignoring it.\nxml: {xml}".format(
                            xml=etree.tostring(news_item, encoding="unicode")
                        )
                    )
                    continue

                if selected is None or lang in ("fi", "sv", "en"):
                    selected = news_item
                if lang == "fi":
                    break

            if selected is None:
                raise ParserError.parseFileError(
                    source=etree.tostring(xml, encoding="unicode")
                )

            guid = selected.findtext("Identification/NewsIdentifier/NewsItemId")
            body = self.get_body(selected)

            # Use xpath() for attribute selectors
            source_elements = selected.xpath(
                "NewsComponent/AdministrativeMetadata/Source/Party/@FormalName"
            )
            source = source_elements[0] if source_elements else "STT"

            headline = selected.findtext("NewsComponent/NewsLines/HeadLine") or ""

            item = {
                "guid": f"stt-info-porssi_{guid}",
                "headline": headline,
                "slugline": headline,
                "body_html": body,
                "source": source,
                "priority": 3,
                "language": lang,
                "anpa_category": [],
                "subject": [],
                "type": "text",
                "versioncreated": datetime.utcnow().isoformat() + "Z",
            }
            return [item]

        except Exception as ex:
            raise ParserError.newsmlOneParserError(ex, provider)

    def get_body(self, news_item):
        try:
            raw_content = news_item.xpath(
                'NewsComponent/ContentItem[@Euid="announcement_html"]/DataContent/text()'
            )[0]
        except IndexError:
            logger.warning(
                "No content found in element: {xml}".format(
                    xml=etree.tostring(news_item, encoding="unicode")
                )
            )
            return ""

        content_elt = sd_etree.parse_html(raw_content)
        h1 = content_elt.find("h1")
        if h1 is not None:
            content_elt.remove(h1)

        categories = news_item.xpath(
            'NewsComponent/Metadata/Property[@FormalName="Message Category"]/@Value'
        )

        if categories:
            category = categories[0]
            p_elt = etree.Element("p")
            p_elt.text = category
            content_elt.insert(0, p_elt)

        ori_ann_urls = news_item.xpath(
            'NewsComponent/Metadata/Property[@FormalName="nordicAgencyWebsite"]/@Value'
        )
        if ori_ann_urls:
            url = ori_ann_urls[0]
            if not url.startswith("http"):
                raise ValueError("Invalid url: {url}".format(url=url))
            p_elt = etree.SubElement(content_elt, "p")
            p_elt.text = "Se saken i sin helhet: "
            a_elt = etree.SubElement(p_elt, "a", attrib={"href": url})
            a_elt.text = url

        ret = sd_etree.to_string(content_elt)
        return ret


# Register the parser
register_feed_parser(STTInfoPorssi.NAME, STTInfoPorssi())
