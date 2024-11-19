from typing import Dict, Any, Union
import logging
from copy import deepcopy

from xml.etree.ElementTree import Element
from eve.utils import config

from superdesk import get_resource_service
from superdesk.metadata.item import ITEM_TYPE, ITEM_STATE
from planning.common import WORKFLOW_STATE, POST_STATE, update_post_item, update_assignment_on_link_unlink


logger = logging.getLogger(__name__)


def planning_xml_contains_remove_signal(xml: Element) -> bool:
    """Returns ``True`` if the ``sttinstruct:remove`` signal is included, ``False`` otherwise"""

    namespaces = {"iptc": "http://iptc.org/std/nar/2006-10-01/"}
    if xml.xpath("//iptc:itemMeta/iptc:signal[@qcode='sttinstruct:remove']", namespaces=namespaces):
        return True
    return False


def unpost_or_spike_event_or_planning(item: Dict[str, Any]) -> None:
    item_resource = "events" if item.get(ITEM_TYPE) == "event" else "planning"
    original: Union[Dict[str, Any], None] = get_resource_service(item_resource).find_one(req=None, _id=item["guid"])

    if not original:
        logger.error("Failed to spike/cancel ingested item: item not found", extra={"item_id": item["guid"]})
        return

    # Wrap ``unlink_item_from_all_content`` in a try...except, so if it fails the item is still spiked/cancelled
    try:
        unlink_item_from_all_content(original)
    except Exception:
        logger.exception("Failed to unlink content from item", extra={"item_id": item["guid"]})

    if not original.get("pubstatus") and original.get(ITEM_STATE) in [
        WORKFLOW_STATE.INGESTED,
        WORKFLOW_STATE.DRAFT,
        WORKFLOW_STATE.POSTPONED,
        WORKFLOW_STATE.CANCELLED,
    ]:
        get_resource_service(item_resource + "_spike").patch(original[config.ID_FIELD], original)
    elif original.get("pubstatus") != POST_STATE.CANCELLED:
        update_post_item({"pubstatus": POST_STATE.CANCELLED, "_etag": original["_etag"]}, original)


def unlink_item_from_all_content(item: Dict[str, Any]) -> None:
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
        for planning_item in planning_service.find(where={"event_item": item_id}):
            unlink_item_from_all_content(planning_item)
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

            for content_link in delivery_service.find(where={"coverage_id": coverage["coverage_id"]}):
                content_id = content_link.get("item_id")
                if not content_id:
                    # Content ID not on this delivery, no need to unlink
                    continue

                content_item = archive_service.find_one(req=None, _id=content_id)
                if not content_item or not content_item.get("assignment_id"):
                    # Either content not found, or does not contain the ``assignment_id``
                    # Nothing to do for this one
                    continue

                # Update the content item to remove the ``assignment_id``
                update_assignment_on_link_unlink(None, content_item)

        # Delete all delivery entries for this Planning item
        delivery_service.delete_action(lookup={"planning_id": item_id})

        # Delete all assignments for this Planning item directly
        # Note: skips ``on_delete`` and ``on_deleted`` hooks, due to validation issues
        get_resource_service("assignments").delete(lookup={"planning_item": item_id})

        # Update the Planning item, to update its coverage assignee and workflow_status
        planning_service.system_update(item_id, {"coverages": coverages}, item)


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


def original_item_exists(resource: str, item_id: str) -> bool:
    return get_resource_service(resource).find_one(req=None, _id=item_id) is not None


def is_online_version(item: Dict[str, Any]) -> bool:
    return next(
        (
            subject for subject in (item.get("subject") or [])
            if subject.get("scheme") == "sttversion" and subject.get("qcode") == "6"
        ),
        None
    ) is not None
