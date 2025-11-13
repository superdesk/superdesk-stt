"""STTSMS for Loordi"""

import logging
import pytz
import re
from lxml import etree
from lxml.etree import SubElement

from superdesk.errors import FormatterError
from superdesk.publish.formatters.newsml_g2_formatter import NewsMLG2Formatter
from superdesk.publish_async.utils import generate_sequence_number

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
STT_FORMATVERSION = "{http://www.stt-lehtikuva.fi/NewsML}formatversion"
XSI_SCHEMALOCATION = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"

logger = logging.getLogger(__name__)


class STTSMSFormatter(NewsMLG2Formatter):
    """STTSMS Formatter"""

    ENCODING = "ISO-8859-1"
    # XML_ROOT = '<?xml version="1.0" encoding="{}"?>\n'.format(ENCODING)

    name = "STT SMS"
    type = "sttsms"

    def format_smscategory(self, article, parentNode):

        smsCategory = SubElement(parentNode, "ms_leaf3_2")
        categoryStr = ""

        if "subject" in article and article["subject"] is not None:
            for subject in article["subject"]:
                if "scheme" in subject:
                    if subject["scheme"] == "sttsmscategory":
                        categoryStr += "PUSH " + subject["name"] + ", "

        # Remove unnecessary ", " from the end of string
        smsCategory.text = re.sub(r",\s*$", "", categoryStr)

    async def format(self, article, subscriber, codes=None):
        """Create article in STT SMS format (XML)

        :param dict article:
        :param dict subscriber:
        :param list codes: selector codes
        :return [(int, str)]: return a List of tuples. A tuple consist of
            publish sequence number and formatted article string.
        :raises FormatterError: if the formatter fails to format an article
        """

        try:
            self.subscriber = subscriber
            pub_seq_num = await generate_sequence_number(subscriber)

            newsItem = etree.Element("onlinearticle", attrib={})

            # START OF HEADER
            header = SubElement(newsItem, "header")
            iddoc = SubElement(header, "iddoc")
            iddoc.text = article.get("guid", "")
            fk_yesno_3 = SubElement(header, "fk_yesno_3")
            fk_yesno_3.text = "Kyllä"

            timeheaderupd = SubElement(header, "timeheaderupd")
            timeheaderupd.text = (
                article["versioncreated"]
                .astimezone(pytz.timezone("Europe/Helsinki"))
                .strftime("%Y%m%d%H%M%S")
            )
            timelastedited = SubElement(header, "timelastedited")
            timelastedited.text = (
                article["firstcreated"]
                .astimezone(pytz.timezone("Europe/Helsinki"))
                .strftime("%Y%m%d%H%M%S")
            )
            fk_yesno_7 = SubElement(header, "fk_yesno_7", attrib={})
            fk_yesno_7.text = "Kyllä"

            self.format_smscategory(article, header)

            sms = SubElement(newsItem, "sms")
            sms.text = article.get("headline", "")

            xmlStr = etree.tostring(
                newsItem, method="xml", pretty_print=True, encoding=self.ENCODING
            ).decode(self.ENCODING)

            # Replace special Unicode characters as entities manually (ndhas, thinsp, tab, etc.)
            xmlStr = xmlStr.replace("\u2013", "&ndash;")
            xmlStr = xmlStr.replace("\t", "&tab;")
            xmlStr = xmlStr.replace("\u2009", "&thinsp;")
            xmlStr = xmlStr.replace("&amp;", "&amp;amp;")

            return [
                (
                    # pub_seq_num,
                    # etree.tostring(news_item, method='xml', pretty_print=True, encoding=self.ENCODING).decode(self.ENCODING),
                    pub_seq_num,
                    xmlStr,
                )
            ]

        except Exception as ex:
            raise await FormatterError.newsmlG2FormatterError(ex, subscriber)

    def can_format(self, format_type, article):
        """Method check if the article can be formatted to STT SMS or not.

        :param str format_type:
        :param dict article:
        :return: True if article can formatted else False
        """

        return format_type == self.type
