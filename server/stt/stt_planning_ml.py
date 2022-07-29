from xml.etree.ElementTree import Element

from superdesk.utc import local_to_utc
from superdesk.io.registry import register_feed_parser
from planning.feed_parsers.superdesk_planning_xml import PlanningMLParser

TIMEZONE = "Europe/Helsinki"


class STTPlanningMLParser(PlanningMLParser):
    NAME = "sttplanningml"
    label = "STT Planning ML"

    SUBJ_QCODE_PREFIXES = {
        "stt-subj": None,
        "sttdepartment": "sttdepartment",
        "sttsubj": "sttsubj",
    }

    def parse(self, tree: Element, provider=None):
        items = super(STTPlanningMLParser, self).parse(tree, provider)
        for item in items:
            self.set_extra_fields(item, tree)

        return items

    def datetime(self, value):
        """When there is no timezone info, assume it's Helsinki timezone."""
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

    def set_extra_fields(self, item, tree: Element):
        """Adds extra fields"""

        item.setdefault("extra", {})["stt_topics"] = item["guid"].split(":")[-1]

        news_coverage_set = tree.find(self.qname("newsCoverageSet"))
        if news_coverage_set is not None:
            event_id = self._get_linked_event_id(news_coverage_set)
            if event_id:
                item["event_item"] = event_id
                item["extra"]["stt_events"] = event_id.split(":")[-1]

    def _get_linked_event_id(self, news_coverage_set: Element):
        for news_coverage_item in news_coverage_set.findall(self.qname("newsCoverage")):
            planning = news_coverage_item.find(self.qname("planning"))
            if planning is None:
                continue
            for subject_item in planning.findall(self.qname("subject")):
                qcode = subject_item.get("qcode")
                if qcode and subject_item.get("type") == "cpnat:event":
                    return qcode


register_feed_parser(STTPlanningMLParser.NAME, STTPlanningMLParser())
