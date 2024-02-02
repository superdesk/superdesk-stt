from typing import Dict, Any, Optional, Set
from xml.etree.ElementTree import Element
from eve.utils import config

from superdesk import get_resource_service
from superdesk.utc import local_to_utc
from superdesk.io.registry import register_feed_parser

from planning.types import Planning
from planning.feed_parsers.superdesk_planning_xml import PlanningMLParser
from planning.common import get_coverage_from_planning

from .common import planning_xml_contains_remove_signal, unpost_or_spike_event_or_planning, \
    remove_date_portion_from_id, original_item_exists

TIMEZONE = "Europe/Helsinki"


class STTPlanningMLParser(PlanningMLParser):
    NAME = "sttplanningml"
    label = "STT Planning ML"

    SUBJ_QCODE_PREFIXES = {
        "stt-subj": None,
        "sttdepartment": "sttdepartment",
        "sttsubj": "sttsubj",
    }

    def get_item_id(self, tree: Element) -> str:
        item_id = super(STTPlanningMLParser, self).get_item_id(tree)
        return item_id if original_item_exists("planning", item_id) else remove_date_portion_from_id(item_id)

    def parse_item(self, tree: Element, original: Optional[Planning]) -> Optional[Planning]:
        if original is not None and planning_xml_contains_remove_signal(tree):
            unpost_or_spike_event_or_planning(original)
            # If the item contains the ``sttinstruct:remove`` signal, no need to ingest this one
            return None

        item = super(STTPlanningMLParser, self).parse_item(tree, original)
        if item is None:
            return None

        self.check_coverage(item, original, tree) if original else self.set_placeholder_coverage(item, tree)
        self.set_extra_fields(tree, item, original)
        return item

    def datetime(self, value: str):
        """When there is no timezone info, assume it's Helsinki timezone."""
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

    def set_extra_fields(self, tree: Element, item: Dict[str, Any], original: Optional[Planning]):
        """Adds extra fields"""

        item.setdefault("extra", {})["stt_topics"] = item["guid"].split(":")[-1]

        news_coverage_set = tree.find(self.qname("newsCoverageSet"))
        if news_coverage_set is not None:
            self._create_temp_assignment_deliveries(news_coverage_set, item, original)
        content_meta = tree.find(self.qname("contentMeta"))
        if content_meta is not None:
            self.set_urgency(content_meta, item)

    def get_coverage_details(self, news_coverage_elt: Element, item: Planning, original: Optional[Planning]):
        event_id = self._get_linked_event_id(news_coverage_elt)
        if event_id is not None:
            # This entry is an Event and not an actual coverage
            if not item.get("event_item"):
                # If this is the first event found, then link this Planning item to it
                item["event_item"] = event_id
                item.setdefault("extra", {})["stt_events"] = event_id.split(":")[-1]

            # Return ``None`` so this coverage isn't added to the Planning item
            return None

        return super().get_coverage_details(news_coverage_elt, item, original)

    def _get_linked_event_id(self, news_coverage_item: Element) -> Optional[str]:
        planning = news_coverage_item.find(self.qname("planning"))
        if planning is None:
            return None
        for subject_item in planning.findall(self.qname("subject")):
            qcode = subject_item.get("qcode")
            if qcode and subject_item.get("type") == "cpnat:event":
                return qcode if original_item_exists("events", qcode) else remove_date_portion_from_id(qcode)

        return None

    def _create_temp_assignment_deliveries(
        self,
        news_coverage_set: Element,
        item: Planning,
        original: Optional[Planning]
    ):
        """Create temporary delivery records for later mapping content to coverages"""

        delivery_service = get_resource_service("delivery")
        planning_id = item[config.ID_FIELD]
        content_uris_processed: Set[str] = set()
        deliveries = []

        existing_deliveries: Dict[str, Set[str]] = {}
        if original is not None:
            for entry in delivery_service.get_from_mongo(req=None, lookup={"planning_id": planning_id}):
                try:
                    existing_deliveries.setdefault(entry["coverage_id"], set())
                    existing_deliveries[entry["coverage_id"]].add(entry["item_id"])
                except (KeyError, TypeError):
                    # ``coverage_id`` or ``item_id`` not defined for this entry for some reason
                    pass

        for news_coverage_item in news_coverage_set.findall(self.qname("newsCoverage")):
            delivery = news_coverage_item.find(self.qname("delivery"))
            if delivery is None:
                continue

            coverage_id = news_coverage_item.get("id")
            original_coverage = get_coverage_from_planning(original, coverage_id) if original else None

            try:
                if original_coverage["assigned_to"]["assignment_id"] is not None:
                    # This coverage is already linked to an Assignment
                    # No need to create a temporary delivery record
                    continue
            except (KeyError, TypeError):
                pass

            for delivery_item in delivery.findall(self.qname("deliveredItemRef")):
                content_guid = delivery_item.get("guidref")

                if content_guid is None:
                    # Skip this entry, as no ``guidref`` found
                    continue

                content_uri = remove_date_portion_from_id(content_guid)
                if content_uri in content_uris_processed:
                    # Skip this entry, as we have already processed content with this ``uri``
                    continue
                content_uris_processed.add(content_uri)

                try:
                    if content_uri in existing_deliveries[coverage_id]:
                        # A delivery entry already exists for this content's ``uri``
                        # No need to create another one
                        continue
                except (KeyError, TypeError):
                    # No existing delivery entry for this coverage
                    pass

                # Create temporary ``delivery`` item for this ``coverage`` (without ``assignment_id``)
                # This will be used later to lookup when:
                # * this Planning item has been created (if content already exists), or
                # * the content for this ``coverage`` is published
                deliveries.append(
                    {
                        "planning_id": planning_id,
                        "coverage_id": coverage_id,
                        "item_id": content_uri,
                    }
                )

        if len(deliveries):
            delivery_service.post(deliveries)

    def set_urgency(self, content_meta, item):
        """set importance cv data in the subjects based on <urgency> tag [STTNHUB-200]"""

        urgency_elt = content_meta.find(self.qname("urgency"))
        if urgency_elt is not None and urgency_elt.text:
            importance_list_items = (
                get_resource_service("vocabularies")
                .find_one(req=None, _id="stturgency")
                .get("items", [])
            )
            matching_items = [
                importance_item
                for importance_item in importance_list_items
                if f"stturgency-{'2' if urgency_elt.text == '3' else urgency_elt.text}"
                == importance_item["qcode"]
            ]
            if matching_items:
                item.get("subject").append(
                    {
                        "name": matching_items[0].get("name"),
                        "qcode": f"stturgency-{urgency_elt.text}",
                        "scheme": matching_items[0].get("scheme"),
                    }
                )

        return item

    def set_placeholder_coverage(self, item, tree):
        """
        Set a Placeholder Coverage if no coverages are provided in the parsed item
        """

        def get_coverage_type(coverage):
            try:
                return coverage["planning"]["g2_content_type"]
            except (KeyError, TypeError):
                return ""

        item.setdefault("coverages", [])
        if not any(True for coverage in item["coverages"] if get_coverage_type(coverage) == "text"):
            # There are no text coverages for this item. Add a placeholder one now
            item["coverages"].append({
                "coverage_id": f"placeholder_{item.get('guid')}",
                "workflow_status": "draft",
                "firstcreated": item.get("firstcreated"),
                "planning": {
                    "slugline": "",
                    "g2_content_type": "text",
                    "scheduled": item.get("planning_date"),
                },
                "flags": {"placeholder": True},
            })

        self.parse_news_coverage_status(tree, item)

    def check_coverage(self, item, planning_item, tree):
        # if existing item is found in the db update coverage details of that item based on new item.
        if not planning_item.get("coverages"):
            # Existing: No Coverages | Ingest: No Coverages
            self.set_placeholder_coverage(item, tree)
        elif not item.get("coverages"):
            # Existing: Coverages | Ingest: No Coverages
            self.set_placeholder_coverage(item, tree)
        else:
            # Existing: Coverages | Ingest: Coverages
            # Filter out any placeholder coverage
            def is_placeholder_coverage(coverage):
                try:
                    return coverage["flags"]["placeholder"] is True
                except (KeyError, TypeError):
                    return False

            planning_item["coverages"] = [
                coverage
                for coverage in planning_item["coverages"]
                if not is_placeholder_coverage(coverage)
            ]

            # Update news_coverage_status for provided coverages
            self.parse_news_coverage_status(tree, item)


stt_planning_ml_parser = STTPlanningMLParser()
register_feed_parser(STTPlanningMLParser.NAME, stt_planning_ml_parser)
