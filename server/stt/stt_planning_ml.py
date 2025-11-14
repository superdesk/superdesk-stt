import pytz
import logging

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

    # STT namespace for internal fields
    NS = {"stt": "http://www.stt.fi/internal"}

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
            item["internal_note"] = ed_note.text.strip()

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
            # Parse STT-specific fields for all coverages
            self.parse_stt_coverage_fields(news_coverage_elt, coverage)
        return coverage

    def parse_stt_coverage_fields(
        self, news_coverage_elt: Element, coverage: Dict[str, Any]
    ):
        """Parse STT-specific coverage fields from XML"""
        planning_elt = news_coverage_elt.find(self.qname("planning"))
        if planning_elt is None:
            return

        # Initialize coverage structure with proper fields
        coverage.setdefault("planning", {})
        coverage["planning"].setdefault("fields", [])
        coverage["planning"].setdefault("subject", [])

        # Parse all fields efficiently in single iterations
        self.parse_all_subject_fields(planning_elt, coverage)
        self.parse_non_subject_fields(planning_elt, coverage)

    def parse_all_subject_fields(self, planning_elt: Element, coverage: Dict[str, Any]):
        """Parse all subject fields in a single iteration"""
        for subject_elt in planning_elt.findall(self.qname("subject")):
            qcode = subject_elt.get("qcode", "")
            value_elt = subject_elt.find(self.qname("value"))
            value_text = (
                value_elt.text.strip()
                if value_elt is not None and value_elt.text is not None
                else ""
            )

            if qcode.startswith("sttworkstatus:"):
                self.parse_coverage_status(subject_elt, coverage)
            elif qcode == "sttinternaltext":
                coverage["planning"]["internal_note"] = value_text
            elif qcode.startswith("sttimagetypename:"):
                self.parse_picture_type(subject_elt, coverage)
            elif qcode.startswith("sttphotoaware:"):
                self.parse_photographer_awareness(subject_elt, coverage)
            elif qcode == "sttentryinfo":
                # Handle Tiedot (ilmoittautuminen) field - map even if empty
                self.add_field_to_coverage(coverage, "sttregistrationinfo", value_text)

    def parse_non_subject_fields(self, planning_elt: Element, coverage: Dict[str, Any]):
        """Parse non-subject fields"""
        # Parse headline
        headline_elt = planning_elt.find(self.qname("headline"))
        if headline_elt is not None and headline_elt.text:
            coverage["planning"]["headline"] = headline_elt.text.strip()

        # Parse scheduled/due date
        workstartdate_elt = planning_elt.find(
            self.qname("workstartdate", ns=self.NS["stt"])
        )
        if workstartdate_elt is not None and workstartdate_elt.text:
            try:
                # Always use STT workstartdate when available
                coverage["planning"]["scheduled"] = self.datetime(
                    workstartdate_elt.text
                )
            except (ValueError, TypeError):
                logger.warning(
                    f"Failed to parse workstartdate: {workstartdate_elt.text}"
                )

        # Parse Finnish text fields
        self.parse_finnish_text_fields(planning_elt, coverage)

    def add_field_to_coverage(
        self, coverage: Dict[str, Any], field_name: str, value: str
    ):
        """Add a field to coverage.planning.fields list"""
        # Always add the field, even if value is empty
        coverage["planning"]["fields"].append(
            {"field": field_name, "value": value or ""}
        )

    def parse_coverage_status(self, subject_elt: Element, coverage: Dict[str, Any]):
        """Parse coverage status from sttworkstatus subject using CV from DB"""
        qcode = subject_elt.get("qcode", "")

        # Map STT internal workstatus to Superdesk coverage status
        status_mapping = {
            "sttworkstatus:1": "ncostat:int",
            "sttworkstatus:2": "ncostat:int",
            "sttworkstatus:3": "ncostat:int",
            "sttworkstatus:4": "ncostat:notint",
            "sttworkstatus:5": "ncostat:notdec",
        }

        mapped_status = status_mapping.get(qcode)
        if mapped_status:
            # Get coverage status from vocabulary
            coverage_status = self.get_coverage_status_from_vocabulary(mapped_status)
            if coverage_status:
                coverage["news_coverage_status"] = coverage_status

    def get_coverage_status_from_vocabulary(
        self, qcode: str
    ) -> Optional[Dict[str, Any]]:
        """Get coverage status from newscoveragestatus vocabulary"""
        try:
            vocab_service = get_resource_service("vocabularies")
            coverage_status_vocab = vocab_service.find_one(
                req=None, _id="newscoveragestatus"
            )

            if coverage_status_vocab and "items" in coverage_status_vocab:
                for item in coverage_status_vocab["items"]:
                    if item.get("qcode") == qcode and item.get("is_active", True):
                        return {
                            "qcode": item["qcode"],
                            "name": item.get("name", ""),
                            "label": item.get("label", ""),  # Use label from vocabulary
                        }
        except Exception as e:
            logger.warning(
                f"Failed to get coverage status from vocabulary for {qcode}: {e}"
            )

        return None

    def parse_picture_type(self, subject_elt: Element, coverage: Dict[str, Any]):
        """Parse picture type from sttimagetypename subject"""
        qcode = subject_elt.get("qcode", "")
        value_elt = subject_elt.find(self.qname("value"))
        value_text = (
            value_elt.text.strip() if value_elt is not None and value_elt.text else ""
        )

        # Direct mapping: sttimagetypename:XX -> sttimage:XX
        if qcode.startswith("sttimagetypename:"):
            numeric_code = qcode.split(":")[1]
            mapped_qcode = f"sttimage:{numeric_code}"

            picture_type = self.get_picture_type_from_vocabulary(mapped_qcode)
            if picture_type:
                picture_type["scheme"] = "sttimagetype"

                coverage["planning"]["subject"].append(picture_type)

                coverage["planning"].setdefault("genre", [])
                coverage["planning"]["genre"].append(
                    {"qcode": picture_type["qcode"], "name": picture_type["name"]}
                )
            else:
                self.add_field_to_coverage(coverage, "sttimagetype", value_text)

    def get_picture_type_from_vocabulary(self, qcode: str) -> Optional[Dict[str, Any]]:
        """Get picture type from sttimagetype vocabulary"""
        try:
            vocab_service = get_resource_service("vocabularies")
            picture_type_vocab = vocab_service.find_one(req=None, _id="sttimagetype")

            if picture_type_vocab and "items" in picture_type_vocab:
                for item in picture_type_vocab["items"]:
                    if item.get("qcode") == qcode and item.get("is_active", True):
                        return {
                            "qcode": item["qcode"],
                            "name": item.get("name", ""),
                            "scheme": "sttimagetype",
                        }
        except Exception as e:
            logger.warning(
                f"Failed to get picture type from vocabulary for {qcode}: {e}"
            )

        return None

    def parse_photographer_awareness(
        self, subject_elt: Element, coverage: Dict[str, Any]
    ):
        """Parse photographer awareness from sttphotoaware subject"""
        qcode = subject_elt.get("qcode", "")

        # Map numeric values to "yes"/"no" qcodes
        awareness_mapping = {
            "sttphotoaware:2": "yes",  # Photographer knows
            "sttphotoaware:1": "no",  # Photographer doesn't know
        }

        mapped_qcode = awareness_mapping.get(qcode)
        if mapped_qcode:
            photographer_awareness = self.get_photographer_awareness_from_vocabulary(
                mapped_qcode
            )
            if photographer_awareness:
                coverage["planning"]["subject"].append(photographer_awareness)

    def get_photographer_awareness_from_vocabulary(
        self, qcode: str
    ) -> Optional[Dict[str, Any]]:
        """Get photographer awareness from sttdoesphotographerknow vocabulary"""
        try:
            vocab_service = get_resource_service("vocabularies")
            awareness_vocab = vocab_service.find_one(
                req=None, _id="sttdoesphotographerknow"
            )

            if awareness_vocab and "items" in awareness_vocab:
                for item in awareness_vocab["items"]:
                    if item.get("qcode") == qcode and item.get("is_active", True):
                        return {
                            "qcode": item["qcode"],
                            "name": item.get("name", ""),
                            "scheme": "sttdoesphotographerknow",
                        }
        except Exception as e:
            logger.warning(
                f"Failed to get photographer awareness from vocabulary for {qcode}: {e}"
            )

        return None

    def parse_finnish_text_fields(
        self, planning_elt: Element, coverage: Dict[str, Any]
    ):
        """Parse Finnish text fields from definition elements"""
        picture_what_about = None
        picture_what_is_photographed = None

        # Look for definition elements with specific roles
        for definition_elt in planning_elt.findall(self.qname("definition")):
            role = definition_elt.get("role", "")
            text = definition_elt.text.strip() if definition_elt.text else ""

            if not text:
                continue

            if role == "sttdescription:imagetype":
                picture_what_about = text
            elif role == "sttdescription:imagetarget":
                picture_what_is_photographed = text

        # Check inside <subject> elements
        for subject_elt in planning_elt.findall(self.qname("subject")):
            for definition_elt in subject_elt.findall(self.qname("definition")):
                role = definition_elt.get("role", "")
                text = definition_elt.text.strip() if definition_elt.text else ""
                if not text:
                    continue

                if role == "sttdescription:imagetype" and not picture_what_about:
                    picture_what_about = text
                elif (
                    role == "sttdescription:imagetarget"
                    and not picture_what_is_photographed
                ):
                    picture_what_is_photographed = text

        # Check inside <genre> elements
        for genre_elt in planning_elt.findall(self.qname("genre")):
            for definition_elt in genre_elt.findall(self.qname("definition")):
                role = definition_elt.get("role", "")
                text = definition_elt.text.strip() if definition_elt.text else ""
                if not text:
                    continue

                if role == "sttdescription:imagetype" and not picture_what_about:
                    picture_what_about = text
                elif (
                    role == "sttdescription:imagetarget"
                    and not picture_what_is_photographed
                ):
                    picture_what_is_photographed = text

        # Map the fields correctly according to the spreadsheet
        if picture_what_about:
            self.add_field_to_coverage(
                coverage, "sttpicturewhatabout", picture_what_about
            )

        if picture_what_is_photographed:
            self.add_field_to_coverage(
                coverage, "sttpicturewhatisphotographed", picture_what_is_photographed
            )

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
                    "fields": [],
                    "subject": [],
                },
                "flags": {"placeholder": True},
            }

            # Set default coverage status for placeholder using vocabulary
            coverage_status = self.get_coverage_status_from_vocabulary("ncostat:notint")
            if coverage_status:
                placeholder_coverage["news_coverage_status"] = coverage_status

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
