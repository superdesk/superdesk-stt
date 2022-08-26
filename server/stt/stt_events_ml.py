from xml.etree.ElementTree import Element

from superdesk.utc import local_to_utc
from superdesk.io.registry import register_feed_parser
from planning.feed_parsers.events_ml import EventsMLParser

TIMEZONE = "Europe/Helsinki"


class STTEventsMLParser(EventsMLParser):
    NAME = "stteventsml"
    label = "STT Events ML"

    SUBJ_QCODE_PREFIXES = {
        "stt-subj": None,
        "sttdepartment": "sttdepartment",
        "sttsubj": "sttsubj",
    }

    def parse(self, tree: Element, provider=None):
        items = super(STTEventsMLParser, self).parse(tree, provider)
        for item in items:
            self.set_extra_fields(item, tree)

        return items

    def datetime(self, value):
        """When there is no timezone info, assume it's Helsinki timezone."""
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

    def set_extra_fields(self, item, xml):
        """Adds extra fields"""

        concept = xml.find(self.qname("concept"))

        # Add ``sttevents``, if one found
        try:
            values = concept.find(self.qname("conceptId")).get("qcode", "").split(":")
            if values and values[0] == "sttevents":
                item.setdefault("extra", {})["stt_events"] = values[1]
        except AttributeError:
            pass

        event_details = concept.find(self.qname("eventDetails"))

        # Add ``stt-topics``, if one found
        try:
            for subject in event_details.findall(self.qname("subject")):
                values = subject.get("qcode", "").split(":")
                if values and values[0] == "stt-topics":
                    item.setdefault("extra", {})["stt_topics"] = values[1]
        except AttributeError:
            pass

        # Add `sttEventType` if found to subject[scheme=event_type]
        try:
            related = concept.find(self.qname("related"))

            if related is not None and related.get("rel", "") == "sttnat:sttEventType":
                qcode_parts = related.get("qcode", "").split(":")
                qcode = qcode_parts[1] if len(qcode_parts) == 2 else qcode_parts
                name = self.getVocabulary("event_type", qcode, related.find(self.qname("name")).text)

                item.setdefault("subject", []).append({
                    "qcode": qcode,
                    "name": name,
                    "scheme": "event_type",
                })
        except AttributeError:
            pass

        self.set_location_details(item, event_details.find(self.qname("location")))

    def set_location_details(self, item, location_xml):
        """Add Location information, if found"""
        if location_xml is None:
            return

        location = {"address": {"extra": {}}}

        try:
            name = location_xml.find(self.qname("name")).text
            location["name"] = name
            location["address"]["title"] = name
        except AttributeError:
            pass

        try:
            sttlocationalias = location_xml.get("qcode").split("sttlocationalias:")[1]
            location["address"]["extra"]["sttlocationalias"] = sttlocationalias
        except AttributeError:
            pass

        for broader in location_xml.findall(self.qname("broader")):
            values = broader.get("qcode", "").split(":")
            if len(values) != 2 or not values[0].startswith("stt"):
                continue
            elif values[0] == "sttcity":
                location["address"]["extra"]["sttcity"] = values[1]

                try:
                    location["address"]["city"] = broader.find(self.qname("name")).text
                except AttributeError:
                    continue
            elif values[0] == "sttstate":
                location["address"]["extra"]["sttstate"] = values[1]
                try:
                    location["address"]["state"] = broader.find(self.qname("name")).text
                except AttributeError:
                    continue
            elif values[0] == "sttcountry":
                location["address"]["extra"]["sttcountry"] = values[1]
                try:
                    location["address"]["country"] = broader.find(self.qname("name")).text
                    location["address"]["extra"]["iso3166"] = broader.find(self.qname("sameAs")).get("qcode")
                except AttributeError:
                    continue

        try:
            address = location_xml.find(self.qname("POIDetails")).find(self.qname("address"))
        except AttributeError:
            address = None

        if address is not None:
            try:
                location["address"]["line"] = [address.find(self.qname("line")).text]
            except AttributeError:
                pass

            try:
                location["address"]["postal_code"] = address.find(self.qname("postalCode")).text
            except AttributeError:
                pass

        item["location"] = [location]


register_feed_parser(STTEventsMLParser.NAME, STTEventsMLParser())
