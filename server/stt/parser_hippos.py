# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from superdesk.io.feed_parsers import XMLFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.utc import utcnow
from superdesk.metadata.utils import generate_guid
from superdesk.metadata.item import GUID_TAG
from pytz import utc
import logging

logger = logging.getLogger(__name__)
HipposNS = {
    "ns3": "http://hippos.fi/heppa/event",
    "ns2": "http://hippos.fi/heppa/horse",
}


class HipposParser(XMLFeedParser):
    NAME = "stthipposparser"
    label = "STT Hippos XML"

    def can_parse(self, xml):
        return xml.tag.endswith("{http://hippos.fi/heppa/event}result")

    def printHorses(self, element):

        str = ""

        horsesResult = element.xpath(
            'ns3:horseResultEntry[ns3:horseResult/ns3:placing = "1"] | ns3:horseResultEntry[ns3:horseResult/ns3:placing = "2"] | ns3:horseResultEntry[ns3:horseResult/ns3:placing = "3"] | ns3:horseResultEntry[ns3:horseResult/ns3:placing = "4"]',
            namespaces=HipposNS,
        )

        if len(horsesResult) > 0:

            """Loop through all horses"""
            for index, element in enumerate(horsesResult):

                result = None
                horseName = None
                driverName = None
                horseKMTime = None
                horseIsBreak = None
                horseWinOdds = None

                """ Horse name """
                result = element.xpath("ns3:horseData/ns2:name", namespaces=HipposNS)
                if len(result) > 0:
                    horseName = result[0].text

                """ kmTime """
                result = element.xpath(
                    "ns3:horseResult/ns3:kmTime", namespaces=HipposNS
                )
                if len(result) > 0:
                    horseKMTime = result[0].text

                """ isBreak """
                result = element.xpath(
                    "ns3:horseResult/ns3:isBreak", namespaces=HipposNS
                )
                if len(result) > 0:
                    horseIsBreak = result[0].text

                """ winOdds """
                result = element.xpath(
                    "ns3:horseResult/ns3:winOdds", namespaces=HipposNS
                )
                if len(result) > 0:
                    horseWinOdds = result[0].text

                if horseIsBreak == "true":
                    horseKMTime += " x"

                """ If we are at the first horse get the complete driver name """
                if index == 0:
                    result = element.xpath(
                        "ns3:horseResult/ns3:driverNameComplete", namespaces=HipposNS
                    )
                    if len(result) > 0:
                        driverName = result[0].text

                """ Print only if we have horse present """
                if horseName is not None:
                    str += f"{index+1}) {horseName}"

                    if driverName is not None:
                        str += f"/{driverName}"

                    if horseKMTime is not None:
                        str += f" {horseKMTime}"

                    if horseWinOdds is not None:
                        str += f" ({horseWinOdds})"

                    if index < len(horsesResult) - 1:
                        str += ", "
                    else:
                        str += ". "
        return str

    async def parse(self, xml, provider=None):

        uid = generate_guid(type=GUID_TAG)

        locationStr = xml.xpath("//ns3:locationPlace", namespaces=HipposNS)[0].text
        dateOfEvent = xml.xpath("//ns3:date", namespaces=HipposNS)[0].text
        typeOfEvent = xml.xpath("//ns3:type", namespaces=HipposNS)[0].text

        items = []

        item = dict()
        item["guid"] = uid
        item["uid"] = uid
        item["version"] = "1"
        item["headline"] = "Ravituloksia/" + locationStr
        item["genre"] = [{"qcode": "sttgenre:13", "name": "Tulokset"}]
        item["anpa_category"] = [{"qcode": "16", "name": "Urheilu"}]
        item["urgency"] = 3
        item["firstcreated"] = (
            utc.localize(item["firstcreated"]) if item.get("firstcreated") else utcnow()
        )
        item["versioncreated"] = (
            utc.localize(item["versioncreated"])
            if item.get("versioncreated")
            else utcnow()
        )

        #  Make sure 'subject' is found in item, default values is empty list
        if "subject" not in item:
            # print('No subject found, create it!')
            item.setdefault("subject", [])

        # Always add STT as sources
        item["subject"].append({"qcode": "STT", "name": "STT", "scheme": "sttsource"})

        item["body_html"] = (
            "<p>"
            + locationStr
            + " "
            + dateOfEvent[8:10]
            + "."
            + dateOfEvent[5:7]
            + "."
            + " "
            + typeOfEvent
            + "</p>"
        )

        """ First we do pony starts if there is any """
        """ ponies = xml.xpath(u"/ns3:result/ns3:raceEvent/ns3:race[ns3:raceInfo/ns3:classification='TOTO']", namespaces=HipposNS) """

        ponies = xml.xpath(
            "/ns3:result/ns3:raceEvent/ns3:race[ns3:raceInfo/ns3:classification='PONI']//child::*",
            namespaces=HipposNS,
        )
        regularHorses = xml.xpath(
            "/ns3:result/ns3:raceEvent/ns3:race[ns3:raceInfo/ns3:classification='TOTO']//child::*",
            namespaces=HipposNS,
        )

        """ If we found pony start """
        if len(ponies) > 0:

            item["body_html"] += "<p></p>"
            item["body_html"] += "<p>"

            for element in ponies:

                if element.tag == "{http://hippos.fi/heppa/event}raceInfo":

                    descriptionStr = element.xpath(
                        "ns3:description", namespaces=HipposNS
                    )[0].text
                    item["body_html"] += descriptionStr + ": "

                if element.tag == "{http://hippos.fi/heppa/event}raceResults":

                    horseStr = self.printHorses(element)

                    missingHorsesStr = "Poissa: "

                    """ List all absent horses for the race """
                    absentHorses = element.xpath(
                        "ns3:absentHorses/ns3:programNumber", namespaces=HipposNS
                    )

                    """ Make sure commas and dots are correct in the absent horses list """
                    if len(absentHorses) > 0:

                        for index, missingHorse in enumerate(absentHorses):
                            missingHorsesStr += missingHorse.text

                            if index == (len(absentHorses) - 1):
                                missingHorsesStr += ". "
                            else:
                                missingHorsesStr += ", "

                    """ Add horses into body text """
                    item["body_html"] += horseStr

                    """ Add missing horses into body text if there is any"""
                    if len(absentHorses) > 0:
                        item["body_html"] += missingHorsesStr

                    item["body_html"] += "</p><p>"

            item["body_html"] += "</p>"

        """ If we found regular horses """
        if len(regularHorses) > 0:
            item["body_html"] += "<p></p>"
            item["body_html"] += "<p>"

            for element in regularHorses:

                if element.tag == "{http://hippos.fi/heppa/event}raceInfo":

                    descriptionStr = element.xpath(
                        "ns3:description", namespaces=HipposNS
                    )[0].text
                    item["body_html"] += descriptionStr + ": "

                if element.tag == "{http://hippos.fi/heppa/event}raceResults":

                    horseStr = self.printHorses(element)

                    missingHorsesStr = "Poissa: "

                    """ List all absent horses for the race """
                    absentHorses = element.xpath(
                        "ns3:absentHorses/ns3:programNumber", namespaces=HipposNS
                    )

                    """ Make sure commas and dots are correct in the absent horses list """
                    if len(absentHorses) > 0:

                        for index, missingHorse in enumerate(absentHorses):
                            missingHorsesStr += missingHorse.text

                            if index == (len(absentHorses) - 1):
                                missingHorsesStr += ". "
                            else:
                                missingHorsesStr += ", "

                    """ Add horses into body text """
                    item["body_html"] += horseStr

                    """ Add missing horses into body text if there is any"""
                    if len(absentHorses) > 0:
                        item["body_html"] += missingHorsesStr

                    item["body_html"] += "</p><p>"

            item["body_html"] += "</p>"
            items.append(item)
        return items


register_feed_parser(HipposParser.NAME, HipposParser())
