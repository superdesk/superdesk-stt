# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from superdesk.io.feed_parsers.newsml_2_0 import NewsMLTwoFeedParser
from superdesk.io.registry import register_feed_parser
import logging
import re

logger = logging.getLogger(__name__)


class BNSNewsMLFeedParser(NewsMLTwoFeedParser):
    """
    Feed Parser which can parse BNS variant of NewsML
    """

    NAME = "bnsnewsml"
    label = "BNS NewsML"

    def can_parse(self, xml):
        return xml.tag.endswith("NewsML")

    async def parse(self, xml, provider=None):

        items = []

        item = dict()
        item["guid"] = xml.xpath("//PublicIdentifier")[0].text
        item["uid"] = xml.xpath("//PublicIdentifier")[0].text
        item["version"] = "1"
        item["headline"] = xml.xpath("//HeadLine")[0].text
        item["urgency"] = int(xml.xpath("//Urgency/@FormalName")[0])
        item["subject"] = []
        item["body_html"] = ""

        # Get department value from XML
        dep = xml.xpath("/NewsML/NewsItem/NewsComponent/TopicSet/Topic/FormalName")[
            0
        ].text

        # Parse dep value and choose STT corresponding department: Ulkomaat or talous
        match = re.search("^.*B$", dep)

        # If last character is B then departmen is talous
        if match is not None:
            item["subject"].append(
                {"qcode": "11", "name": "Talous", "scheme": "sttdepartment"}
            )
        # Otherwise all other values default to department ulkomaat
        else:
            item["subject"].append(
                {"qcode": "14", "name": "Ulkomaat", "scheme": "sttdepartment"}
            )

        # Get body paragraps
        paragraphs = xml.xpath(
            "/NewsML/NewsItem/NewsComponent/ContentItem/DataContent/html/body//p"
        )

        # Concatenate all paragaphs into single string in body_html
        for p in paragraphs:
            item["body_html"] = item["body_html"] + "<p>" + p.text + "</p>"

        items.append(item)

        logger.warning("Parsing end")

        return items


register_feed_parser(BNSNewsMLFeedParser.NAME, BNSNewsMLFeedParser())
