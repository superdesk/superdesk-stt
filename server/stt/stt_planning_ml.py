from typing import Dict, Any, Optional
from xml.etree.ElementTree import Element
from eve.utils import config

from superdesk import get_resource_service
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

    def datetime(self, value: str):
        """When there is no timezone info, assume it's Helsinki timezone."""
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

    def set_extra_fields(self, item: Dict[str, Any], tree: Element):
        """Adds extra fields"""

        item.setdefault("extra", {})["stt_topics"] = item["guid"].split(":")[-1]

        news_coverage_set = tree.find(self.qname("newsCoverageSet"))
        if news_coverage_set is not None:
            self._create_temp_assignment_deliveries(item, news_coverage_set)

    def get_coverage_details(self, news_coverage_item: Element, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_id = self._get_linked_event_id(news_coverage_item)
        if event_id is not None:
            # This entry is an Event and not an actual coverage
            if not item.get("event_item"):
                # If this is the first event found, then link this Planning item to it
                item["event_item"] = event_id
                item.setdefault("extra", {})["stt_events"] = event_id.split(":")[-1]

            # Return ``None`` so this coverage isn't added to the Planning item
            return None

        return super().get_coverage_details(news_coverage_item, item)

    def _get_linked_event_id(self, news_coverage_item: Element) -> Optional[str]:
        planning = news_coverage_item.find(self.qname("planning"))
        if planning is None:
            return None
        for subject_item in planning.findall(self.qname("subject")):
            qcode = subject_item.get("qcode")
            if qcode and subject_item.get("type") == "cpnat:event":
                return qcode

        return None

    def _create_temp_assignment_deliveries(self, item: Dict[str, Any], news_coverage_set: Element):
        """Create temporary delivery records for later mapping content to coverages"""

        delivery_service = get_resource_service("delivery")
        planning_id = item[config.ID_FIELD]
        guids_processed = []
        deliveries = []

        for news_coverage_item in news_coverage_set.findall(self.qname("newsCoverage")):
            coverage_id = news_coverage_item.get("id")
            delivery = news_coverage_item.find(self.qname("delivery"))

            if delivery is None:
                continue

            for delivery_item in delivery.findall(self.qname("deliveredItemRef")):
                content_guid = delivery_item.get("guidref")
                if content_guid is None or content_guid in guids_processed:
                    continue

                # Create temporary ``delivery`` item for this ``coverage`` (without ``assignment_id``)
                # This will be used later to lookup when:
                # * this Planning item has been created (if content already exists), or
                # * the content for this ``coverage`` is published
                deliveries.append({
                    "planning_id": planning_id,
                    "coverage_id": coverage_id,
                    "item_id": content_guid
                })

        if len(deliveries):
            delivery_service.post(deliveries)


stt_planning_ml_parser = STTPlanningMLParser()
register_feed_parser(STTPlanningMLParser.NAME, stt_planning_ml_parser)
