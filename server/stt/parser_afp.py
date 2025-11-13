# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from superdesk.io.feed_parsers.newsml_1_2 import NewsMLOneFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.utc import utcnow
from pytz import utc
from superdesk import etree
import logging
import re

logger = logging.getLogger(__name__)


class AFPNewsMLFeedParser(NewsMLOneFeedParser):
    """
    Feed Parser which can parse AFP variant of NewsML
    """

    NAME = "sttafpnewsml"
    label = "STT AFP NewsML"

    def can_parse(self, xml):
        return xml.tag.endswith("NewsML")

    async def parse(self, xml, provider=None):

        subjectmatter_mappings = [
            {"pattern": "^01[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^02[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^03[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^04[0-9]+$", "mappingid": "11", "mappingstr": "Talous"},
            {"pattern": "^05[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {
                "pattern": "^06[0-9]+$",
                "mappingid": "13",
                "mappingstr": "Toimituksille tiedoksi",
            },
            {"pattern": "^07[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {
                "pattern": "^08[0-9]+$",
                "mappingid": "13",
                "mappingstr": "Toimituksille tiedoksi",
            },
            {"pattern": "^09[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^10[0-9]+$", "mappingid": "11", "mappingstr": "Talous"},
            {"pattern": "^11[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^12[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^13[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^14[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^15[0-9]+$", "mappingid": "16", "mappingstr": "Urheilu"},
            {"pattern": "^16[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
            {"pattern": "^17[0-9]+$", "mappingid": "14", "mappingstr": "Ulkomaat"},
        ]

        item = await super().parse(xml, provider)
        item["firstcreated"] = (
            utc.localize(item["firstcreated"]) if item.get("firstcreated") else utcnow()
        )
        item["versioncreated"] = (
            utc.localize(item["versioncreated"])
            if item.get("versioncreated")
            else utcnow()
        )

        item["anpa_category"] = []

        # Get all possible department values from XML
        deps = xml.xpath("//SubjectMatter/@FormalName")

        # Loop through all of them
        for d in deps:

            # Do the mapping into STT department values
            for p in subjectmatter_mappings:

                match = re.search(p["pattern"], d)

                # Check if we have a match
                if match is not None:

                    # Is the subject already added to the list of subjects or not
                    alreadyAdded = False

                    # Need to check if the match is already added or not. We can only add one copy of the match
                    for sub in item["anpa_category"]:
                        if sub["name"] == p["mappingstr"]:
                            alreadyAdded = True

                    # If match is not found add it to the subjects
                    if alreadyAdded is False:
                        item["anpa_category"].append(
                            {
                                "qcode": p["mappingid"],
                                "name": p["mappingstr"],
                            }
                        )

        # Check if there is not subjects found. Then use default value for it: Ulkomaat
        if len(item["anpa_category"]) == 0:
            item["anpa_category"].append({"qcode": "14", "name": "Ulkomaat"})

        # Headline fallback
        if not item.get("headline") and item.get("body_html"):
            first_line = item.get("body_html").strip().split("\n")[0]
            parsed_headline = etree.parse_html(first_line, "html")
            item["headline"] = (
                etree.to_string(parsed_headline, method="text").strip().split("\n")[0]
            )

        # --- Always add AFP and STT as sources
        item["subject"].append({"qcode": "AFP", "name": "AFP", "scheme": "sttsource"})
        item["subject"].append({"qcode": "STT", "name": "STT", "scheme": "sttsource"})
        # --- Always add main genre
        item["genre"].append({"qcode": "sttgenre:1", "name": "Uutinen"})

        return item


register_feed_parser(AFPNewsMLFeedParser.NAME, AFPNewsMLFeedParser())
