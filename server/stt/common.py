from typing import Dict, Any

from xml.etree.ElementTree import Element
from eve.utils import config

from superdesk import get_resource_service
from superdesk.metadata.item import ITEM_TYPE, ITEM_STATE
from planning.common import WORKFLOW_STATE, POST_STATE, update_post_item


def planning_xml_contains_remove_signal(xml: Element) -> bool:
    """Returns ``True`` if the ``sttinstruct:remove`` signal is included, ``False`` otherwise"""

    namespaces = {"iptc": "http://iptc.org/std/nar/2006-10-01/"}
    if xml.xpath("//iptc:itemMeta/iptc:signal[@qcode='sttinstruct:remove']", namespaces=namespaces):
        return True
    return False


def unpost_or_spike_event_or_planning(item: Dict[str, Any]):
    item_resource = "events" if item.get(ITEM_TYPE) == "event" else "planning"
    original: Dict[str, Any] = get_resource_service(item_resource).find_one(req=None, _id=item["guid"]) or {}

    if not original.get("pubstatus") and original.get(ITEM_STATE) in [
        WORKFLOW_STATE.INGESTED,
        WORKFLOW_STATE.DRAFT,
        WORKFLOW_STATE.POSTPONED,
        WORKFLOW_STATE.CANCELLED,
    ]:
        get_resource_service(item_resource + "_spike").patch(original[config.ID_FIELD], original)
    elif original.get("pubstatus") != POST_STATE.CANCELLED:
        update_post_item({"pubstatus": POST_STATE.CANCELLED, "_etag": original["_etag"]}, original)


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
