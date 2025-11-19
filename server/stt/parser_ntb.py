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

logger = logging.getLogger(__name__)


class NTBNewsMLFeedParser(NewsMLTwoFeedParser):
    """
    Feed Parser which can parse NTB variant of NewsML
    """

    NAME = "ntbnewsml"
    label = "NTB NewsML"

    def can_parse(self, xml):
        return xml.tag.endswith("newsMessage")

    async def parse(self, xml, provider=None):

        ns = {"n": "http://iptc.org/std/nar/2006-10-01/"}

        items = []

        item = dict()
        item["guid"] = xml.xpath(
            "string(/n:newsMessage/n:itemSet/n:newsItem/@guid)", namespaces=ns
        )
        item["uid"] = xml.xpath(
            "string(/n:newsMessage/n:itemSet/n:newsItem/@guid)", namespaces=ns
        )
        item["version"] = "1"
        item["headline"] = xml.xpath(
            "string(/n:newsMessage/n:itemSet/n:newsItem/n:contentMeta/n:headline)",
            namespaces=ns,
        )
        item["anpa_category"] = []
        item["body_html"] = ""

        # Get department
        dep = xml.xpath(
            "string(/n:newsMessage/n:itemSet/n:newsItem/n:contentMeta/n:subject/@qcode)",
            namespaces=ns,
        )

        match dep:
            case "subj:Innenriks":
                item["anpa_category"].append({"qcode": "3", "name": "Kotimaa"})
            case "subj:Utenriks":
                item["anpa_category"].append({"qcode": "14", "name": "Ulkomaat"})
            case "subj:Sport":
                item["anpa_category"].append({"qcode": "16", "name": "Urheilu"})
            case _:
                item["anpa_category"].append({"qcode": "12", "name": "Tiedotepalvelu"})

        # Make sure 'subject' is found in item, default valus is empty list
        if "subject" not in item:
            item.setdefault("subject", [])

        # Always add NTB and STT as sources
        item["subject"].append({"qcode": "NTB", "name": "NTB", "scheme": "sttsource"})
        item["subject"].append({"qcode": "STT", "name": "STT", "scheme": "sttsource"})

        # Get body paragraps
        paragraphs = xml.xpath(
            "/n:newsMessage/n:itemSet/n:newsItem/n:contentSet/n:inlineXML/n:nitf/n:body/n:body.content//n:p",
            namespaces=ns,
        )

        # Concatenate all paragaphs into single string in body_html
        for p in paragraphs:
            item["body_html"] = item["body_html"] + f"<p>{p.text or ''}</p>"

        items.append(item)

        logger.warning("Parsing end")

        return items


register_feed_parser(NTBNewsMLFeedParser.NAME, NTBNewsMLFeedParser())
