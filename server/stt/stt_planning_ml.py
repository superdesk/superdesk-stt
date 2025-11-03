import pytz
import logging
import re

from typing import Dict, Any, Optional, Set
from xml.etree.ElementTree import Element
from eve.utils import config
from datetime import datetime

from superdesk import get_resource_service
from superdesk.utc import local_to_utc
from superdesk.io.registry import register_feed_parser

from planning.types import Planning
from planning.feed_parsers.superdesk_planning_xml import PlanningMLParser
from planning.common import get_coverage_from_planning

from .common import (
    STTParserMixin,
    planning_xml_contains_remove_signal,
    unpost_or_spike_event_or_planning,
    remove_date_portion_from_id,
    original_item_exists,
)

TIMEZONE = "Europe/Helsinki"

logger = logging.getLogger(__name__)


class EventNotFound(Exception):
    pass


class STTPlanningMLParser(STTParserMixin, PlanningMLParser):
    NAME = "sttplanningml"
    label = "STT Planning ML"

    SUBJ_QCODE_PREFIXES = {
        "stt-subj": None,
        "sttdepartment": "sttdepartment",
        "sttsubj": "sttsubj",
    }

    async def get_item_id(self, tree: Element) -> str:
        item_id = await super(STTPlanningMLParser, self).get_item_id(tree)
        return (
            item_id
            if await original_item_exists("planning", item_id)
            else remove_date_portion_from_id(item_id)
        )

    async def parse_item(
        self, tree: Element, original: Optional[Planning]
    ) -> Optional[Planning]:
        if original is not None and planning_xml_contains_remove_signal(tree):
            await unpost_or_spike_event_or_planning(original)
            # If the item contains the ``sttinstruct:remove`` signal, no need to ingest this one
            return None

        item = await super(STTPlanningMLParser, self).parse_item(tree, original)
        if item is None:
            return None

        (
            self.check_coverage(item, original, tree)
            if original
            else self.set_placeholder_coverage(item, tree)
        )
        await self.set_extra_fields(tree, item, original)
        return item

    def datetime(self, value: str):
        """When there is no timezone info, assume it's Helsinki timezone."""

        # First check if the value provided is a date only
        # And store the date/time as midnight in UTC
        try:
            date_value = datetime.strptime(value, "%Y-%m-%d")
            return date_value.replace(tzinfo=pytz.utc)
        except ValueError:
            pass

        # Value provides more than date, try other formats
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

    async def set_extra_fields(
        self, tree: Element, item: Dict[str, Any], original: Optional[Planning]
    ):
        """Adds extra fields"""

        item.setdefault("extra", {})["stt_topics"] = item["guid"].split(":")[-1]

        # Parse planning item internal note
        self.parse_planning_internal_note(tree, item)

        news_coverage_set = tree.find(self.qname("newsCoverageSet"))
        if news_coverage_set is not None:
            await self._create_temp_assignment_deliveries(
                news_coverage_set, item, original
            )
        content_meta = tree.find(self.qname("contentMeta"))
        if content_meta is not None:
            self.set_urgency(content_meta, item)

        meta = tree.find(self.qname("contentMeta"))
        if meta is not None:
            subjects = meta.findall(self.qname("subject"))
            self.parse_subjects(item, subjects)

    def parse_planning_internal_note(self, tree: Element, item: Dict[str, Any]):
        """Parse internal note for planning item from edNote with role sttdescription:private"""
        ed_note = tree.find(
            f'.//{self.qname("edNote")}[@role="sttdescription:private"]'
        )
        if ed_note is not None and ed_note.text:
            item["internal_note"] = ed_note.text

    async def get_coverage_details(
        self, news_coverage_elt: Element, item: Planning, original: Optional[Planning]
    ):
        try:
            event_id = await self._get_linked_event_id(news_coverage_elt)
        except EventNotFound:
            return None
        if event_id is not None:
            # This entry is an Event and not an actual coverage
            if not item.get("event_item"):
                # If this is the first event found, then link this Planning item to it
                item["event_item"] = event_id
                item.setdefault("extra", {})["stt_events"] = event_id.split(":")[-1]

            # Return ``None`` so this coverage isn't added to the Planning item
            return None

        coverage = await super().get_coverage_details(news_coverage_elt, item, original)
        if coverage is not None:
            # Only parse STT-specific fields for new coverages or when we have the specific STT data
            self.parse_stt_coverage_fields(news_coverage_elt, coverage)
        return coverage

    def parse_stt_coverage_fields(
        self, news_coverage_elt: Element, coverage: Dict[str, Any]
    ):
        """Parse STT-specific coverage fields from XML - only for internal planning items"""
        planning_elt = news_coverage_elt.find(self.qname("planning"))
        if planning_elt is None:
            return

        has_stt_fields = False

        # Check for STT-specific namespaces and qcodes
        for subj in planning_elt.findall(self.qname("subject")):
            qcode = subj.get("qcode", "")
            if any(
                [
                    qcode == "sttinternaltext",
                    qcode == "sttentryinfo",
                    qcode.startswith("sttworkstatus:"),
                    qcode.startswith("sttphotoaware:"),
                    qcode.startswith("sttimagetypename:"),
                ]
            ):
                has_stt_fields = True
                break

        # Check for internal description fields
        if not has_stt_fields:
            for defn in planning_elt.findall(self.qname("definition")):
                role = defn.get("role", "")
                if role in ("sttdescription:imagetype", "sttdescription:imagetarget"):
                    has_stt_fields = True
                    break

        if not has_stt_fields:
            if (
                planning_elt.find(".//{http://www.stt.fi/internal}workstartdate")
                is not None
            ):
                has_stt_fields = True

        if not has_stt_fields:
            return

        # Parse headline
        headline_elt = planning_elt.find(self.qname("headline"))
        if headline_elt is not None and headline_elt.text:
            coverage.setdefault("planning", {})["headline"] = headline_elt.text.strip()

        # Parse scheduled/due date
        workstartdate_elt = planning_elt.find(
            ".//{http://www.stt.fi/internal}workstartdate"
        )
        if (
            workstartdate_elt is not None
            and workstartdate_elt.text
            and not coverage.get("planning", {}).get("scheduled")
        ):
            try:
                coverage.setdefault("planning", {})["scheduled"] = self.datetime(
                    workstartdate_elt.text
                )
            except (ValueError, TypeError):
                logger.warning(
                    f"Failed to parse workstartdate: {workstartdate_elt.text}"
                )

        # Parse other STT-specific fields
        self.parse_coverage_status(planning_elt, coverage)
        self.parse_coverage_internal_note(planning_elt, coverage)
        self.parse_picture_type(planning_elt, coverage)
        self.parse_photographer_awareness(planning_elt, coverage)
        self.parse_finnish_text_fields(planning_elt, coverage)
        self.parse_registration_info(planning_elt, coverage)

    def parse_coverage_status(self, planning_elt: Element, coverage: Dict[str, Any]):
        """Parse coverage status from sttworkstatus subject"""
        for subject_elt in planning_elt.findall(self.qname("subject")):
            qcode = subject_elt.get("qcode", "")
            if qcode.startswith("sttworkstatus:"):
                # Map STT internal workstatus values to Superdesk coverage status
                status_mapping = {
                    "sttworkstatus:1": "ncostat:int",
                    "sttworkstatus:2": "ncostat:int",
                    "sttworkstatus:3": "ncostat:int",
                    "sttworkstatus:4": "ncostat:notint",
                    "sttworkstatus:5": "ncostat:notdec",
                }

                mapped_status = status_mapping.get(qcode)
                if mapped_status:
                    coverage["news_coverage_status"] = {
                        "qcode": mapped_status,
                        "name": self.get_coverage_status_name(mapped_status),
                        "label": self.get_coverage_status_label(mapped_status),
                    }
                break

    def get_coverage_status_name(self, qcode):
        """Get coverage status name from qcode"""
        names = {
            "ncostat:int": "coverage intended",
            "ncostat:notint": "coverage not intended",
            "ncostat:notdec": "coverage not decided yet",
        }
        return names.get(qcode, "")

    def get_coverage_status_label(self, qcode):
        """Get localized Finnish label for coverage status"""
        labels = {
            "ncostat:int": "Kyllä",
            "ncostat:notint": "Ei",
            "ncostat:notdec": "Ei",
        }
        return labels.get(qcode, "")

    def parse_coverage_internal_note(
        self, planning_elt: Element, coverage: Dict[str, Any]
    ):
        """Parse internal note for coverage from sttinternaltext subject"""
        # Find subject with qcode sttinternaltext
        for subject_elt in planning_elt.findall(self.qname("subject")):
            if subject_elt.get("qcode") == "sttinternaltext":
                value_elt = subject_elt.find(self.qname("value"))
                if value_elt is not None and value_elt.text:
                    coverage["internal_note"] = value_elt.text
                break

    def parse_picture_type(self, planning_elt: Element, coverage: Dict[str, Any]):
        """Parse picture type from genre and sttimagetypename subject"""
        # First try genre element
        genre_elt = planning_elt.find(self.qname("genre"))
        if genre_elt is not None:
            qcode = genre_elt.get("qcode")
            if qcode and qcode.startswith("sttimage:"):
                coverage.setdefault("planning", {})["sttimagetype"] = qcode
                return

        # Fallback to sttimagetypename subject
        for subject_elt in planning_elt.findall(self.qname("subject")):
            qcode = subject_elt.get("qcode", "")
            if qcode.startswith("sttimagetypename:"):
                qcode = qcode.replace("sttimagetypename:", "sttimage:")
                coverage.setdefault("planning", {})["sttimagetype"] = qcode
                break

    def parse_photographer_awareness(
        self, planning_elt: Element, coverage: Dict[str, Any]
    ):
        """Parse photographer awareness from sttphotoaware subject"""
        for subject_elt in planning_elt.findall(self.qname("subject")):
            qcode = subject_elt.get("qcode", "")
            if qcode.startswith("sttphotoaware:"):
                awareness_mapping = {
                    "sttphotoaware:2": "yes",
                    "sttphotoaware:1": "no",
                    "sttphotoaware:0": None,
                }
                coverage.setdefault("planning", {})["sttdoesphotographerknow"] = (
                    awareness_mapping.get(qcode)
                )
                break

    def parse_finnish_text_fields(self, planning_elt, coverage):
        """Parse Finnish text fields from <definition> or fallback from internal note."""
        definitions = planning_elt.findall(".//" + self.qname("definition"))

        picture_what_about = None
        picture_what_is_photographed = None

        for definition_elt in definitions:
            role = definition_elt.get("role")
            text = "".join(definition_elt.itertext()).strip()

            if not text or not role:
                continue

            role = role.split(":")[-1].lower()
            if role == "imagetype":
                picture_what_about = text
            elif role == "imagetarget":
                picture_what_is_photographed = text

        # Fallback: extract from internal_note if imagetype missing
        if not picture_what_about:
            internal_note = coverage.get("internal_note", "")
            match = re.search(r"Kuvitus[:\-]?\s*(.+)", internal_note)
            if match:
                picture_what_about = match.group(1).strip()

        if picture_what_about:
            coverage.setdefault("planning", {})[
                "sttpicturewhatabout"
            ] = picture_what_about

        if picture_what_is_photographed:
            coverage.setdefault("planning", {})[
                "sttpicturewhatisphotographed"
            ] = picture_what_is_photographed

    def parse_registration_info(self, planning_elt: Element, coverage: Dict[str, Any]):
        """Parse registration info from sttentryinfo subject"""
        for subject_elt in planning_elt.findall(self.qname("subject")):
            if subject_elt.get("qcode") == "sttentryinfo":
                value_elt = subject_elt.find(self.qname("value"))
                if value_elt is not None and value_elt.text:
                    coverage.setdefault("planning", {})[
                        "sttregistrationinfo"
                    ] = value_elt.text
                break

    async def _get_linked_event_id(self, news_coverage_item: Element) -> Optional[str]:
        planning = news_coverage_item.find(self.qname("planning"))
        if planning is None:
            return None
        for subject_item in planning.findall(self.qname("subject")):
            qcode = subject_item.get("qcode")
            if qcode and subject_item.get("type") == "cpnat:event":
                if await original_item_exists("events", qcode):
                    return qcode
                short_qcode = remove_date_portion_from_id(qcode)
                if await original_item_exists("events", short_qcode):
                    return short_qcode
                logger.warning("Linked event not found", extra={"event": qcode})
                raise EventNotFound()
        return None

    async def _create_temp_assignment_deliveries(
        self, news_coverage_set: Element, item: Planning, original: Optional[Planning]
    ):
        """Create temporary delivery records for later mapping content to coverages"""

        delivery_service = get_resource_service("delivery")
        planning_id = item[config.ID_FIELD]
        content_uris_processed: Set[str] = set()
        deliveries = []

        existing_deliveries: Dict[str, Set[str]] = {}
        if original is not None:
            async for entry in await delivery_service.get_from_mongo_async(
                req=None, lookup={"planning_id": planning_id}
            ):
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
            original_coverage = (
                get_coverage_from_planning(original, coverage_id) if original else None
            )

            try:
                if (
                    original_coverage
                    and original_coverage["assigned_to"]["assignment_id"] is not None
                ):
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
                    if coverage_id and content_uri in existing_deliveries.get(
                        coverage_id, set()
                    ):
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
                        "assignment_id": None,
                    }
                )

        if len(deliveries):
            await delivery_service.post_async(deliveries)

    def set_urgency(self, content_meta, item):
        urgency_elt = content_meta.find(self.qname("urgency"))
        if urgency_elt is not None and urgency_elt.text:
            try:
                item["priority"] = int(urgency_elt.text)
            except ValueError:
                pass

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
        if not any(
            True
            for coverage in item["coverages"]
            if get_coverage_type(coverage) == "text"
        ):
            # There are no text coverages for this item. Add a placeholder one now
            placeholder_coverage = {
                "coverage_id": f"placeholder_{item.get('guid')}",
                "workflow_status": "draft",
                "firstcreated": item.get("firstcreated"),
                "planning": {
                    "slugline": "",
                    "g2_content_type": "text",
                    "scheduled": item.get("planning_date"),
                },
                "flags": {"placeholder": True},
            }

            # Set default coverage status for placeholder
            placeholder_coverage["news_coverage_status"] = {
                "qcode": "ncostat:notint",
                "name": "coverage not intended",
                "label": "Ei",
            }

            item["coverages"].append(placeholder_coverage)

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
