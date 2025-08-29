from typing import Dict, Any, TypedDict
import logging
from copy import deepcopy

from lxml.etree import Element

from superdesk import get_resource_service
from superdesk.metadata.item import ITEM_TYPE, ITEM_STATE
from planning.common import (
    WORKFLOW_STATE,
    POST_STATE,
    update_post_item,
    update_assignment_on_link_unlink,
)
from planning.events.events_spike import process_spike_event
from planning.planning.planning_spike import process_spike_planning_item


logger = logging.getLogger(__name__)


class Item(TypedDict):
    _id: str
    guid: str
    coverages: list[Any]
    ingest_provider: str
    subject: list[dict[str, str]]
    extra: dict[str, str]
    headline: str
    slugline: str
    task: dict[str, str]
    assignment_id: str
    genre: str
    language: str


def planning_xml_contains_remove_signal(xml: Element) -> bool:
    """Returns ``True`` if the ``sttinstruct:remove`` signal is included, ``False`` otherwise"""

    namespaces = {"iptc": "http://iptc.org/std/nar/2006-10-01/"}
    if xml.xpath(
        "//iptc:itemMeta/iptc:signal[@qcode='sttinstruct:remove']",
        namespaces=namespaces,
    ):
        return True
    return False


async def unpost_or_spike_event_or_planning(item: Dict[str, Any]) -> None:
    item_resource = "events" if item.get(ITEM_TYPE) == "event" else "planning"
    original: dict | None = await get_resource_service(item_resource).find_one_async(
        req=None, _id=item["guid"]
    )

    if not original:
        logger.error(
            "Failed to spike/cancel ingested item: item not found",
            extra={"item_id": item["guid"]},
        )
        return

    # Wrap ``unlink_item_from_all_content`` in a try...except, so if it fails the item is still spiked/cancelled
    try:
        await unlink_item_from_all_content(original)
    except Exception:
        logger.exception(
            "Failed to unlink content from item", extra={"item_id": item["guid"]}
        )

    if not original.get("pubstatus") and original.get(ITEM_STATE) in [
        WORKFLOW_STATE.INGESTED,
        WORKFLOW_STATE.DRAFT,
        WORKFLOW_STATE.POSTPONED,
        WORKFLOW_STATE.CANCELLED,
    ]:
        if item_resource == "events":
            await process_spike_event({}, original)
        else:
            await process_spike_planning_item({}, original)
    elif original.get("pubstatus") != POST_STATE.CANCELLED:
        await update_post_item(
            {"pubstatus": POST_STATE.CANCELLED, "_etag": original["_etag"]}, original
        )


async def unlink_item_from_all_content(item: Dict[str, Any]) -> None:
    """Attempts to unlink all content/assignments from the provided item

    Performs the following actions:
    * If this is an Event, re-runs this function with any linked Planning items
    * Removes ``assignment_id`` from content linked to this item, using 'archived', 'published' or 'archive' collection
    * Deletes all items in ``delivery`` collection, that match any coverage in the Planning item
    * Deletes all items in ``assignments`` collection, that match the Planning item's ID
    * Updates the Planning item's coverages, to remove ``assigned_to`` field and set ``workflow_status`` to ``DRAFT``

    The above actions are performed directly to avoid validation logic in the Planning module. As some of the services,
    such as Assignments service, assumes an unlink is being performed from the front-end and not via ingest.
    So instead we directly delete the items from their respective collections.
    """

    item_id = item["_id"]
    planning_service = get_resource_service("planning")
    if item.get(ITEM_TYPE) == "event":
        async for planning_item in await planning_service.find_async(
            where={"event_item": item_id}
        ):
            await unlink_item_from_all_content(planning_item)
    else:
        delivery_service = get_resource_service("delivery")
        archive_service = get_resource_service("search")

        coverages = deepcopy(item.get("coverages") or [])
        if not len(coverages):
            # No coverages on this Planning item, no need to continue
            return

        for coverage in coverages:
            # Remove assignee information and set state to DRAFT
            coverage.pop("assigned_to", None)
            coverage["workflow_status"] = WORKFLOW_STATE.DRAFT

            async for content_link in await delivery_service.find_async(
                where={"coverage_id": coverage["coverage_id"]}
            ):
                content_id = content_link.get("item_id")
                if not content_id:
                    # Content ID not on this delivery, no need to unlink
                    continue

                content_item = await archive_service.find_one_async(
                    req=None, _id=content_id
                )
                if not content_item or not content_item.get("assignment_id"):
                    # Either content not found, or does not contain the ``assignment_id``
                    # Nothing to do for this one
                    continue

                # Update the content item to remove the ``assignment_id``
                await update_assignment_on_link_unlink(None, content_item)

        # Delete all delivery entries for this Planning item
        await delivery_service.delete_action_async(lookup={"planning_id": item_id})

        # Delete all assignments for this Planning item directly
        # Note: skips ``on_delete`` and ``on_deleted`` hooks, due to validation issues
        await get_resource_service("assignments").delete_async(
            lookup={"planning_item": item_id}
        )

        # Update the Planning item, to update its coverage assignee and workflow_status
        await planning_service.system_update_async(
            item_id, {"coverages": coverages}, item
        )


def remove_date_portion_from_id(item_id: str) -> str:
    """Removes the date portion from an ingested Event or Planning ID

    Example Original: urn:newsml:stt.fi:20230317:276671
    Example Response: urn:newsml:stt.fi:276671
    """

    id_parts = item_id.split(":")
    if len(id_parts) == 5:
        # Correct format to split, Remove the date portion of the ID
        del id_parts[3]
    elif len(id_parts) == 6:
        # ID includes version, remove the date and version portions of the ID
        del id_parts[5]
        del id_parts[3]

    return ":".join(id_parts)


async def original_item_exists(resource: str, item_id: str) -> bool:
    return (
        await get_resource_service(resource).find_one_async(req=None, _id=item_id)
    ) is not None


def is_online_version(item: Item) -> bool:
    return (
        next(
            (
                subject
                for subject in (item.get("subject") or [])
                if subject.get("scheme") == "sttversion" and subject.get("qcode") == "6"
            ),
            None,
        )
        is not None
    )


class STTParserMixin:

    async def parse(self, xml, provider=None):
        items = await super().parse(xml, provider)
        for item in items:
            department = [
                s for s in item.get("subject", []) if s.get("scheme") == "sttdepartment"
            ]
            if department:
                item["anpa_category"] = [
                    {"name": d["name"], "qcode": d["qcode"]} for d in department
                ]
            if item.get("headline") and "TRANSLATED" in item["headline"]:
                item["language"] = "en"
            else:
                item["language"] = "fi"
        return items

    def get_topics_lookup(self):
        topics = self.get_cv_items("topics")
        return {int(t["iptc_subject"], 10): t for t in topics if t.get("iptc_subject")}

    def get_cv_items(self, _id):
        return get_resource_service("vocabularies").get_items(_id)

    def parse_subjects(self, item, subjects):
        topics_lookup = self.get_topics_lookup()
        for subject in subjects:
            qcode = subject.attrib.get("qcode", "")
            if qcode.startswith("sttsubj:"):
                code = qcode.split(":")[1]
                topic = topics_lookup.get(int(code, 10))
                if topic:
                    item.setdefault("subject", []).append(topic)
            if qcode.startswith("stt-topics:"):
                item.setdefault("extra", {})["stt_topics"] = qcode.split(":")[1]
            if qcode.startswith("stt-events:"):
                item.setdefault("extra", {})["stt_events"] = qcode.split(":")[1]
