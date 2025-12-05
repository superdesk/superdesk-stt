"""

STT version of the NewsML G2 Superdesk formatter

"""

import superdesk
import logging
import pytz
import re

from lxml import etree, html
from lxml.etree import SubElement
from superdesk.etree import parse_html
from superdesk.resource_fields import VERSION
from superdesk import text_utils
from superdesk.metadata.item import ITEM_TYPE, CONTENT_TYPE
from superdesk.errors import FormatterError
from superdesk.publish_async.utils import generate_sequence_number
from superdesk.publish.formatters.newsml_g2_formatter import NewsMLG2Formatter
from superdesk.media.renditions import get_rendition_file_name
from datetime import datetime, timezone

from stt.publish.utils import encode_special_characters

from .exclude_metadata import removeMetadata

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
STT_FORMATVERSION = "{http://www.stt-lehtikuva.fi/NewsML}formatversion"
XSI_SCHEMALOCATION = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"

logger = logging.getLogger(__name__)


def format_filename(rendition) -> str:
    filename = get_rendition_file_name(rendition)
    filename = filename.replace(".jpeg", ".jpg")
    return filename


class STTNewsmLG2Formatter(NewsMLG2Formatter):

    ENCODING = "UTF-8"
    XML_ROOT = '<?xml version="1.0" encoding="{}"?>\n'.format(ENCODING)

    type = "sttnewsmlg2"
    name = "STT NewsML G2"

    _message_nsmap = {
        None: "http://iptc.org/std/nar/2006-10-01/",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "stt": "http://www.stt-lehtikuva.fi/NewsML",
    }

    # Helpers: signal
    def format_signal(self, article, parentNode, original):
        state = article.get("state", None)
        versionNumber = article.get("version", "")

        if state == "corrected":
            signal = SubElement(parentNode, "signal", attrib={"qcode": "sig:corrected"})
            SubElement(
                signal,
                "link",
                attrib={
                    "guidref": "urn:newsml:stt.fi::" + original.get("guid", ""),
                    "version": str(versionNumber),
                },
            )
        elif article.get("rewrite_of"):
            signal = SubElement(parentNode, "signal", attrib={"qcode": "sig:update"})
            SubElement(
                signal,
                "link",
                attrib={
                    "guidref": "urn:newsml:stt.fi::" + original.get("guid", ""),
                    "version": str(versionNumber),
                },
            )

    # Helpers: location
    def format_location(self, article, parentNode):

        places = article.get("place", "")
        for s in places:
            if s.get("name", None):
                location = SubElement(
                    parentNode, "located", attrib={"type": s.get("qcode", "")}
                )
                SubElement(location, "name").text = s.get("name", "")

    # Helpers: assignments
    def format_assignments(self, article, parentNode):

        if article.get("assignment_id", None):

            assignment = superdesk.get_resource_service("assignments").find_one(
                req=None, _id=article.get("assignment_id")
            )

            if assignment is not None:
                if assignment.get("planning", None):
                    try:
                        coverageStatus = assignment.get("planning", "")[
                            "news_coverage_status"
                        ]["label"]
                        coverageStatusCode = "-1"
                    except KeyError:
                        coverageStatus = None
                        coverageStatusCode = "-1"

                    match coverageStatus:
                        case "Tehdään":
                            coverageStatusCode = "1"
                        case "Ehkä":
                            coverageStatusCode = "2"
                        case "Ei":
                            coverageStatusCode = "3"
                        case "Vain tsekkaus":
                            coverageStatusCode = "4"

                    SubElement(
                        parentNode,
                        "subject",
                        attrib={
                            "type": "cpnat:abstract",
                            "literal": "Related topic id",
                            "qcode": "stt-topics:"
                            + assignment.get("planning_item", ""),
                        },
                    )
                    SubElement(
                        parentNode,
                        "subject",
                        attrib={
                            "type": "cpnat:abstract",
                            "qcode": "sttdone1:" + coverageStatusCode,
                        },
                    )

    # Helpers: department
    def format_department(self, article, parentNode):

        # Department
        # Map 'anpa_category' into subject tag with correct attributes
        # Events should only have one value in 'anpa_category' but this
        # solution could also handle multiple values.
        anpa_category = article.get("anpa_category", {})
        for s in anpa_category:
            department = SubElement(
                parentNode,
                "subject",
                attrib={
                    "type": "cpnat:abstract",
                    "qcode": "sttdepartment:" + s.get("qcode", ""),
                },
            )
            SubElement(department, "name").text = s.get("name", "")

    # Helpers: IPTC
    def format_IPTC(self, article, parentNode):

        subjects = article.get("subject", {})

        for s in subjects:
            if s.get("scheme", None) == "topics":
                subj = SubElement(
                    parentNode,
                    "subject",
                    attrib={
                        "type": "cpnat:abstract",
                        "qcode": s.get("scheme", "") + ":" + s.get("qcode", ""),
                    },
                )
                SubElement(subj, "name").text = s.get("name", "")

    # Helpers: texttype
    def format_texttype(self, article, parentNode):

        if article.get("genre"):
            for s in article["genre"]:
                genre = SubElement(
                    parentNode, "genre", attrib={"qcode": s.get("qcode", "")}
                )
                SubElement(genre, "name").text = s.get("name", "")

    # Helpers: versiontype
    def format_versiontype(self, article, parentNode):

        versiontype = article.get("profile", None)

        if versiontype:

            match versiontype:

                case "viiva":
                    genre = SubElement(
                        parentNode, "genre", attrib={"qcode": "sttversion:1"}
                    )
                    SubElement(genre, "name").text = "Viiva"

                    # Character count
                    characterCount = text_utils.get_char_count(
                        article.get("headline", "")
                    )
                    SubElement(
                        genre,
                        "related",
                        attrib={
                            "qcode": "sttrel:actuallength",
                            "value": str(characterCount),
                        },
                    )

                case "sms":
                    genre = SubElement(
                        parentNode, "genre", attrib={"qcode": "sttversion:2"}
                    )
                    SubElement(genre, "name").text = "SMS"

                case "pika":
                    genre = SubElement(
                        parentNode, "genre", attrib={"qcode": "sttversion:3"}
                    )
                    SubElement(genre, "name").text = "Pika"

                    # Character count
                    if article.get("body_html", None):
                        characterCount = text_utils.get_char_count(
                            article.get("body_html", "")
                        )
                        SubElement(
                            genre,
                            "related",
                            attrib={
                                "qcode": "sttrel:actuallength",
                                "value": str(characterCount),
                            },
                        )

                case "pikaplus":
                    genre = SubElement(
                        parentNode, "genre", attrib={"qcode": "sttversion:4"}
                    )
                    SubElement(genre, "name").text = "Pika+"

                    # Character count
                    if article.get("body_html", None):
                        characterCount = text_utils.get_char_count(
                            article.get("body_html", "")
                        )
                        SubElement(
                            genre,
                            "related",
                            attrib={
                                "qcode": "sttrel:actuallength",
                                "value": str(characterCount),
                            },
                        )

                case "nettiuutinen":
                    genre = SubElement(
                        parentNode, "genre", attrib={"qcode": "sttversion:6"}
                    )
                    SubElement(genre, "name").text = "Nettiuutiset"

                    # Character count
                    if article.get("body_html", None):
                        characterCount = text_utils.get_char_count(
                            article.get("body_html", "")
                        )
                        SubElement(
                            genre,
                            "related",
                            attrib={
                                "qcode": "sttrel:actuallength",
                                "value": str(characterCount),
                            },
                        )

    # Helpers: creditline
    def format_creditline(self, article, parentNode):

        subjects = article.get("subject", [])
        numOfSources = sum(1 for s in subjects if s.get("scheme") == "sttsource")

        # If we only have one source
        if numOfSources == 1:

            sttSource = [item for item in subjects if item.get("scheme") == "sttsource"]
            SubElement(parentNode, "creditline").text = sttSource[0].get("name")

        # If we have multiple sources, combine them
        elif numOfSources > 1:

            str = ""
            count = 0
            creditline = SubElement(parentNode, "creditline")

            for s in subjects:
                if s.get("scheme", "") == "sttsource":
                    str += s.get("name", "")
                    count += 1

                    # Add endash to all but the last source
                    if count < numOfSources:
                        str += "–"

            creditline.text = str

    # Helpers: topstory
    def format_topstory(self, article, parentNode):

        subjects = article.get("subject", {})

        for s in subjects:
            if s.get("scheme", None) == "stttopstory":
                # yesno = 1 if name == 'Kyllä'
                # yesno = 0 if name is not 'Kyllä'
                topStoryYesNo = "1" if s.get("name", "") == "Kyllä" else "0"
                SubElement(
                    parentNode,
                    "subject",
                    attrib={
                        "type": "cpnat:abstract",
                        "qcode": "stttopstory:" + topStoryYesNo,
                    },
                )

    # Helpers: format featured media
    def format_images(self, article, parentNode):

        associations = article.get("associations", None)

        if associations:
            featureMedia = associations.get("featuremedia", None)

            if featureMedia:
                link = SubElement(
                    parentNode,
                    "link",
                    attrib={
                        "rel": "seeAlso",
                        "residref": featureMedia.get("guid", ""),
                        "contenttype": featureMedia.get("mimetype", ""),
                    },
                )
                SubElement(link, "title", attrib={"role": "drol:caption"}).text = (
                    featureMedia.get("description_text", "")
                )

                renditions = featureMedia.get("renditions", None)
                if renditions:
                    original = renditions.get("original", None)
                    if original:
                        SubElement(link, "filename").text = format_filename(original)

    def format_datetime(self, dt: datetime) -> str:
        return dt.astimezone(pytz.timezone("Europe/Helsinki")).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

    # Format itemMeta
    def format_itemMeta(self, article, parentNode, original):

        itemMeta = SubElement(parentNode, "itemMeta")

        SubElement(itemMeta, "itemClass", attrib={"qcode": "ninat:text"})
        SubElement(itemMeta, "provider", attrib={"literal": "STT"})

        versioncreated = article.get("versioncreated") or datetime.now(timezone.utc)
        SubElement(itemMeta, "versionCreated").text = self.format_datetime(
            versioncreated
        )

        firstcreated = article.get("firstcreated") or versioncreated
        SubElement(itemMeta, "firstCreated").text = self.format_datetime(firstcreated)

        # Embargo
        schedule = article.get("schedule_settings", None)
        if schedule:
            if schedule.get("utc_embargo", None):
                SubElement(itemMeta, "embargoed").text = self.format_datetime(
                    schedule.get("utc_embargo")
                )

        SubElement(itemMeta, "pubStatus", attrib={"qcode": "stat:usable"})

        is_sttnewsroomnote = False
        newsroomnoteStr = ""

        # Check STT Newsroom note
        subjects = article.get("subject", {})
        for s in subjects:
            if s.get("scheme") == "sttnewsroomnote":
                is_sttnewsroomnote = True
                newsroomnoteStr += s.get("name", "") + ". "

        edNoteStr = ""

        # Private edNote
        if is_sttnewsroomnote:

            SubElement(itemMeta, "edNote", attrib={"role": "sttnewsroomnote"}).text = (
                newsroomnoteStr
            )

            # Check if the last character of the note is period. If not add it and extra space
            # This is a try to make sure that sttnewsroomnote and private note alway have '. ' in between them
            match = re.search(r"([\. ]+$)", newsroomnoteStr)
            if match:
                newsroomnoteStr = re.sub(r"([\. ]+$)", ". ", newsroomnoteStr)
            else:
                newsroomnoteStr = newsroomnoteStr + ". "

            edNoteStr = newsroomnoteStr + (article.get("ednote") or "")
            SubElement(itemMeta, "edNote", attrib={"role": "sttnote:private"}).text = (
                edNoteStr.strip()
            )
        elif article.get("ednote"):
            edNoteStr = article.get("ednote")
            SubElement(itemMeta, "edNote", attrib={"role": "sttnote:private"}).text = (
                edNoteStr.strip()
            )

        # Public edNote - to all other profiles but 'nettiuutinen'
        if article.get("profile") != "nettiuutinen":

            extra = article.get("extra", {})

            if extra:
                if "sttpublicednote" in extra:
                    # For some reason data is inside P tag
                    parser = etree.XMLParser()
                    if extra.get("sttpublicednote", None):
                        element = etree.XML(extra.get("sttpublicednote", ""), parser)
                        SubElement(
                            itemMeta, "edNote", attrib={"role": "sttnote:public"}
                        ).text = element.text

        # Signals
        self.format_signal(article, itemMeta, original)

        # Collect all links from the body into itemMeta
        tree = parse_html(article.get("body_html", ""), content="html")

        # Generate link for every a -element found
        for element in tree.xpath("//a"):
            SubElement(
                itemMeta,
                "link",
                attrib={"rel": "irel:seeAlso", "href": element.get("href")},
            ).text = element.text

        self.format_images(article, itemMeta)

    # Format contentMeta
    def format_contentMeta(self, article, parentNode):

        contentMeta = SubElement(parentNode, "contentMeta")

        SubElement(contentMeta, "urgency").text = str(article.get("urgency", 5))

        versioncreated = article.get("versioncreated") or datetime.now(timezone.utc)
        SubElement(contentMeta, "contentCreated").text = self.format_datetime(
            versioncreated
        )
        SubElement(contentMeta, "contentModified").text = self.format_datetime(
            versioncreated
        )

        SubElement(contentMeta, "altId", attrib={"type": "sttidtype:textid"}).text = (
            article.get("guid", "")
        )

        self.format_location(article, contentMeta)

        infoSource = SubElement(
            contentMeta, "infoSource", attrib={"qcode": "sttsource:1"}
        )
        SubElement(infoSource, "name").text = "STT"

        if "byline" in article:
            creator = SubElement(contentMeta, "creator")
            SubElement(creator, "name").text = article.get("byline", "")

        SubElement(
            contentMeta,
            "altId",
            attrib={
                "type": "sttidtype:runningnumber",
                "environment": "sttcounter:daily",
            },
        ).text = str(article.get("publish_sequence_no", ""))

        self.format_assignments(article, contentMeta)
        self.format_department(article, contentMeta)
        self.format_IPTC(article, contentMeta)
        self.format_topstory(article, contentMeta)

        # Näitä tietoja ei enää ole?
        self.format_texttype(article, contentMeta)
        self.format_versiontype(article, contentMeta)

        SubElement(contentMeta, "slugline").text = ""

        dateline = article.get("dateline", None)
        if dateline is not None:
            located = dateline.get("located", None)
            if located is not None:
                city = located.get("city", None)
                if city is not None:
                    SubElement(contentMeta, "dateline").text = (
                        article.get("dateline", "").get("located", "").get("city", "")
                    )

        if article.get("byline", None):
            SubElement(contentMeta, "by").text = article.get("byline", "")

        SubElement(contentMeta, "description", attrib={"role": "drol:summary"})
        SubElement(contentMeta, "headline").text = article.get("headline", "")

        self.format_creditline(article, contentMeta)

    def format_contentSet_body(self, article, body):
        """Format the body content. Can be overridden in subclasses.

        :param dict article: The article to format
        :param Element body: The body element to append content to
        """
        # Body
        if article.get("body_html", None):

            tree = parse_html(article.get("body_html", ""), content="html")

            # Replace all h3 tags with <p><h3></h3></p> structure, to mimic Neo's old output
            for h3 in tree.xpath("//h3"):
                newElement = html.Element("p")
                parent = h3.getparent()
                index = parent.index(h3)
                parent.remove(h3)

                newElement.append(h3)
                parent.insert(index, newElement)

            # Replace all company tags, ie. <span custom-editor-tag-id="EDITOR_TAG_company"> with <Company>
            for element in tree.xpath(
                '//span[@custom-editor-tag-id="EDITOR_TAG_company"]'
            ):
                newElement = html.Element("Company")
                newElement.text = "".join(element.itertext())
                if element.tail:
                    newElement.tail = element.tail
                element.getparent().replace(element, newElement)

            # Replace all person tags, ie. <span custom-editor-tag-id="EDITOR_TAG_person"> with <Person>
            for element in tree.xpath(
                '//span[@custom-editor-tag-id="EDITOR_TAG_person"]'
            ):
                newElement = html.Element("Person")
                newElement.text = "".join(element.itertext())
                if element.tail:
                    newElement.tail = element.tail
                element.getparent().replace(element, newElement)

            for e in tree:
                body.append(e)

            # If the profile is 'nettiuutinen' add public ednote to the end of body
            if article.get("profile") == "nettiuutinen":
                extra = article.get("extra", {})

                if extra:
                    if "sttpublicednote" in extra:
                        # For some reason data is inside P tag
                        parser = etree.XMLParser()
                        if extra.get("sttpublicednote", None):
                            element = etree.XML(
                                extra.get("sttpublicednote", ""), parser
                            )

                            p = html.Element("p")
                            p.text = element.text
                            body.append(p)

        # If we don't have body, check if the profile is 'viiva'.
        else:
            # If viiva generate new body content with same content as headline
            if article.get("profile", "") == "viiva":
                SubElement(body, "p").text = article.get("headline", "")

    def format_contentSet(self, article, parentNode):

        contentSet = SubElement(parentNode, "contentSet")
        inlineXML = SubElement(
            contentSet, "inlineXML", attrib={"contenttype": "xhtml/xml"}
        )
        htmlTag = SubElement(inlineXML, "html")
        body = SubElement(htmlTag, "body")
        subheadline = ""

        # Subheadline
        extra = article.get("extra", None)

        if extra:
            if extra.get("sttsubheadline", None):
                htmltree = html.fromstring(extra.get("sttsubheadline", ""))
                subheadline = etree.Element("h2")

                # Find the paragraph and get the content to H2
                try:
                    subheadline_p = htmltree.xpath("//p")[0]
                except IndexError:
                    subheadline_p = None
                if subheadline_p is not None and subheadline_p.text_content():
                    subheadline.text = subheadline_p.text_content()
                    body.append(subheadline)

        # Format body content (can be overridden in subclasses)
        self.format_contentSet_body(article, body)

    def can_format(self, format_type, article):
        """Method check if the article can be formatted to NewsML G2 or not.

        :param str format_type:
        :param dict article:
        :return: True if article can formatted else False
        """
        return format_type == self.type and article.get(ITEM_TYPE) in {
            CONTENT_TYPE.TEXT,
            CONTENT_TYPE.PREFORMATTED,
            CONTENT_TYPE.COMPOSITE,
            CONTENT_TYPE.PICTURE,
            CONTENT_TYPE.VIDEO,
            CONTENT_TYPE.AUDIO,
        }

    async def format(self, article, subscriber, codes=None):
        """Create article in STT's version of NewsML G2

        :param dict article:
        :param dict subscriber:
        :param list codes: selector codes
        :return [(int, str)]: return a List of tuples. A tuple consist of
            publish sequence number and formatted article string.
        :raises FormatterError: if the formatter fails to format an article
        """

        try:
            article = removeMetadata(article)
            original = self._get_original_article(article)

            pub_seq_num = await generate_sequence_number(subscriber)

            newsItem = etree.Element(
                "newsItem",
                attrib={
                    "guid": "urn:newsml:stt.fi::" + original.get("guid", ""),
                    "version": str(article.get(VERSION, "")),
                    "standardversion": "2.12",
                    "conformance": "power",
                    XML_LANG: "fi-FI",
                    "standard": "NewsML-G2",
                    XSI_SCHEMALOCATION: "http://iptc.org/std/nar/2006-10-01/ http://www.iptc.org/std/NewsML-G2/2.12/specification/NewsML-G2_2.12-spec-All-Power.xsd http://www.stt-lehtikuva.fi/NewsML http://www.stt-lehtikuva.fi/newsml/schema/STT-Lehtikuva_NewsML_G2.xsd",
                    STT_FORMATVERSION: "1.1",
                },
                nsmap=self._message_nsmap,
            )

            # Add Catalogs to newsItem
            SubElement(
                newsItem,
                "catalogRef",
                attrib={
                    "href": "http://www.iptc.org/std/catalog/catalog.IPTC-G2-Standards_19.xml"
                },
            )
            SubElement(
                newsItem,
                "catalogRef",
                attrib={
                    "href": "http://www.iptc.org/std/catalog/catalog.IPTC-G2-Standards_18.xml"
                },
            )
            SubElement(
                newsItem,
                "catalogRef",
                attrib={
                    "href": "http://www.stt-lehtikuva.fi/newsml/doc/stt-NewsCodesCatalog_1.xml"
                },
            )

            self.format_itemMeta(article, newsItem, original)
            self.format_contentMeta(article, newsItem)
            self.format_contentSet(article, newsItem)

            xmlStr = etree.tostring(
                newsItem, method="xml", pretty_print=True, encoding=self.ENCODING
            ).decode(self.ENCODING)

            xmlStr = encode_special_characters(xmlStr)

            return [
                (
                    pub_seq_num,
                    self.XML_ROOT + xmlStr,
                )
            ]

        except Exception as ex:
            raise await FormatterError.newmsmlG2FormatterError(
                ex, subscriber
            ).send_notifications()

    def _get_original_article(self, article):
        """Get the original article for the given article by following the rewrite_of chain.
        If the article is not a rewrite, return the article itself.

        :param dict article: The article to get the original for
        :return: The original article
        :rtype: dict
        """
        for i in range(99):  # Prevent infinite loops
            rewrite_of = article.get("rewrite_of", None)
            if not rewrite_of:
                return article
            original_article = superdesk.get_resource_service("archive").find_one(
                req=None, _id=rewrite_of
            )
            if not original_article:
                return article
            article = original_article


class ISODatetimeMixin:
    """
    Mixin class to format datetime in ISO 8601 format with timezone info.
    """

    def format_datetime(self, dt: datetime) -> str:
        return dt.astimezone(pytz.timezone("Europe/Helsinki")).isoformat()
