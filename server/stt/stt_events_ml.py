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

        # Add ``stt-topics``, if one found
        try:
            for subject in concept.find(self.qname("eventDetails")).findall(self.qname("subject")):
                values = subject.get("qcode", "").split(":")
                if values and values[0] == "stt-topics":
                    item.setdefault("extra", {})["stt_topics"] = values[1]
        except AttributeError:
            pass


register_feed_parser(STTEventsMLParser.NAME, STTEventsMLParser())
