import logging
import html
from superdesk.io.registry import register_feed_parser
from superdesk.etree import etree
from superdesk.io.feed_parsers.newsml_1_2 import NewsMLOneFeedParser
from superdesk.errors import ParserError
from superdesk import etree as sd_etree
from superdesk.metadata.utils import generate_guid
from superdesk.metadata.item import GUID_TAG
from superdesk.utc import utcnow
from copy import deepcopy

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class STTInfoRelease(NewsMLOneFeedParser):
    """STT Info XML ingest.

    STT Info is a custom NewsML 1.2 format
    """

    NAME = "stt_parse_sttinfo"

    label = "STT Info tiedotteet"

    # User for cleaning unwanted markup
    ALLOWED_TAGS = ["p", "b", "a", "br", "h1", "h2", "h3", "li", "dt", "dd", "strong"]
    ALLOWED_ATTRS = {"a": ["href"]}
    REMOVABLE_TAGS = ["figcaption"]

    """ Example of replacing links in text with old Neo style output. """
    """
    TAG_CONVERSION_TABLE = [
        { "source": "li", "destination": "p", "prefix": "- " },
        { "source": "dt", "destination": "p", "prefix": "- " },
        { "source": "dd", "destination": "p", "prefix": "- " },
        { "source": "strong", "destination": "b", "prefix": "" },
        { "source": "em", "destination": "p", "prefix": "" },
        {
            "source": "a",
            "action": "replace",
            "template": '"{href}": "{text}"',
            "attributes": ["href"],
            "text": True
        }
    ]

    """

    TAG_CONVERSION_TABLE = [
        {"source": "li", "destination": "p", "prefix": "- "},
        {"source": "dt", "destination": "p", "prefix": "- "},
        {"source": "dd", "destination": "p", "prefix": "- "},
        {"source": "strong", "destination": "b", "prefix": ""},
    ]

    def __init__(self):
        super().__init__()

    def can_parse(self, xml):
        return xml.tag == "release"

    # Handle single tag conversion into something else defined by template style configuration
    # For example:
    # Convert this:
    # <a href="http://stt.fi">Suomen Tietotoimisto Oy</a>
    # Into this:
    # http://stt.fi: Suomen Tietotoimisto Oy
    def conversionTableReplaceAction(self, item, tag):
        data = {}

        for attr in item.get("attributes", []):
            data[attr] = tag.get(attr, "")

        if item.get("text"):
            data["text"] = tag.get_text(strip=True)

            replacement = item["template"].format(**data)
            tag.replace_with(replacement)

    # Iterate through list of child tags and unwrap unwanted tags
    def removeUnwantedMarkup(self, rootTag):

        if not rootTag:
            return ""

        # HTML decode whole release
        encodedHTML = rootTag.decode_contents()
        decodedHTML = html.unescape(encodedHTML)

        fragment = BeautifulSoup(decodedHTML, "html.parser")

        conversionMap = {item["source"]: item for item in self.TAG_CONVERSION_TABLE}

        for tag in fragment.find_all(True):

            if tag.parent is None:
                continue

            tagName = tag.name.lower()

            # Does tag belong to removable tags?
            if tagName in self.REMOVABLE_TAGS:
                tag.decompose()
                continue

            # If tag is not in the allowed list, unwrap it
            if tagName not in self.ALLOWED_TAGS:
                tag.unwrap()
                continue

            # If tag is allowed, check possible conversions
            item = conversionMap.get(tagName)

            if item:
                if item.get("action") == "replace":
                    self.conversionTableReplaceAction(item, tag)
                    continue
                else:
                    tag.name = item["destination"]

                if item.get("prefix"):
                    tag.insert(0, item["prefix"])

                    tagName = tag.name.lower()

            # Filter attributes
            allowedAttrs = self.ALLOWED_ATTRS.get(tagName, [])
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowedAttrs}

        return "".join(str(child) for child in fragment.contents)

    async def parse(self, xml, provider=None):
        try:
            # Remove namespace for easier XPath
            xml = deepcopy(xml)

            # Genereate headline in form of: "*** Tiedote/<publisher>: <title of the release> ***"
            headline = "*** Tiedote/{publisher}: {title} ***".format(
                publisher=xml.xpath("/release/publisher/name")[0].text,
                title=xml.xpath("/release/title")[0].text,
            )

            soup = BeautifulSoup(etree.tostring(xml, encoding="unicode"), "xml")

            body = ""

            # LEADTEXT
            leadtextTag = soup.find("leadtext")

            if leadtextTag:
                body += self.removeUnwantedMarkup(leadtextTag)

            # BODY
            bodyTag = soup.find("body")

            if bodyTag:
                body += self.removeUnwantedMarkup(bodyTag)

            # CONTACTS
            contactsTag = soup.find("contacts")

            if contactsTag:
                if contactsTag.find("contact"):
                    body += "<p>Yhteyshenkilöt:</p>"
                for contact in contactsTag.find_all("contact"):
                    name = contact.find("name").get_text()
                    title = contact.find("title").get_text()
                    phone = contact.find("phone").get_text()
                    email = contact.find("email").get_text()
                    body += "<p>" + name + "</p>"
                    body += "<p>" + title + "</p>"
                    body += "<p>" + phone + "</p>"
                    body += "<p>" + email + "</p>"

            # CONTACT AS TEXT
            contactsAsTextTag = soup.find("contactsAsText")

            if contactsAsTextTag and contactsAsTextTag.contents:
                body += "<p>Yhteyshenkilöt:</p>"
                body += "<p>" + contactsAsTextTag.get_text() + "</p>"

            # MAIN IMAGE
            mainImageTag = soup.find("mainImage")

            if mainImageTag:
                caption = mainImageTag.find("caption").get_text()
                url = mainImageTag.find("url").get_text()
                body += "<p>Pääkuva:</p>"
                body += "<p>" + caption + "</p>"
                body += '<p><a href="' + url + '">' + url + "</a></p>"

            # IMAGES
            imagesTag = soup.find("images")

            if imagesTag:
                if imagesTag.find("image"):
                    body += "<p>Kuvat:</p>"
                for image in imagesTag.find_all("image"):
                    caption = image.find("caption").get_text()
                    url = image.find("url").get_text()
                    body += "<p>" + caption + "</p>"
                    body += '<p><a href="' + url + '">' + url + "</a></p>"

            # LINKS
            linksTag = soup.find("links")

            if linksTag:
                if linksTag.find("link"):
                    body += "<p>Linkit:</p>"
                for link in linksTag.find_all("link"):
                    url = link.find("url").get_text()
                    description = link.find("description").get_text()
                    body += "<p>" + description + "</p>"
                    body += '<p><a href="' + url + '">' + url + "</a></p>"

            # DOCUMENTS
            documentsTag = soup.find("documents")

            if documentsTag:
                if documentsTag.find("document"):
                    body += "<p>Liitteet:</p>"
                for document in documentsTag.find_all("document"):
                    title = document.find("title").get_text()
                    url = document.find("url").get_text()
                    body += "<p>" + title + "</p>"
                    body += '<p><a href="' + url + '">' + url + "</a></p>"

            # BOILERPLATE
            boilerplateTag = soup.find("boilerplate")

            if boilerplateTag:
                body += "<p>" + self.removeUnwantedMarkup(boilerplateTag) + "</p>"

            item = {
                "guid": generate_guid(type=GUID_TAG),
                "headline": headline,
                "body_html": body,
                "urgency": 3,
                "version": 1,
                "anpa_category": [{"qcode": "12", "name": "Tiedotepalvelu"}],
                "genre": [{"qcode": "sttgenre:1", "name": "Uutinen"}],
                "firstcreated": utcnow(),
                "versioncreated": utcnow(),
            }

            # Add source STT
            item["subject"] = []
            item["subject"].append(
                {"qcode": "STT", "name": "STT", "scheme": "sttsource"}
            )

            return [item]

        except Exception as ex:
            raise ParserError.newsmlOneParserError(ex, provider)

    def get_body(self, news_item):
        try:
            raw_content = news_item.xpath(
                'NewsComponent/ContentItem[@Euid="announcement_html"]/DataContent/text()'
            )[0]
        except IndexError:
            public_id = (
                news_item.findtext("Identification/NewsIdentifier/PublicIdentifier")
                or news_item.findtext("Identification/NewsIdentifier/NewsItemId")
                or ""
            )
            logger.warning("No content found in element; public_id=%s", public_id)
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
            p_elt.text = "Lue koko juttu: "
            a_elt = etree.SubElement(p_elt, "a", attrib={"href": url})
            a_elt.text = url

        ret = sd_etree.to_string(content_elt)
        return ret


# Register the parser
register_feed_parser(STTInfoRelease.NAME, STTInfoRelease())
