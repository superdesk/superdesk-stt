from typing import Dict, Any

from xml.etree.ElementTree import Element
from eve.utils import config

from superdesk import get_resource_service
from superdesk.metadata.item import ITEM_TYPE, ITEM_STATE
from planning.common import WORKFLOW_STATE, POST_STATE, update_post_item
import re


def planning_xml_contains_remove_signal(xml: Element) -> bool:
    """Returns ``True`` if the ``sttinstruct:remove`` signal is included, ``False`` otherwise"""

    namespaces = {"iptc": "http://iptc.org/std/nar/2006-10-01/"}
    if xml.xpath(
        "//iptc:itemMeta/iptc:signal[@qcode='sttinstruct:remove']",
        namespaces=namespaces,
    ):
        return True
    return False


def unpost_or_spike_event_or_planning(item: Dict[str, Any]):
    item_resource = "events" if item.get(ITEM_TYPE) == "event" else "planning"
    original: Dict[str, Any] = (
        get_resource_service(item_resource).find_one(req=None, _id=item["guid"]) or {}
    )

    if not original.get("pubstatus") and original.get(ITEM_STATE) in [
        WORKFLOW_STATE.INGESTED,
        WORKFLOW_STATE.DRAFT,
        WORKFLOW_STATE.POSTPONED,
        WORKFLOW_STATE.CANCELLED,
    ]:
        get_resource_service(item_resource + "_spike").patch(
            original[config.ID_FIELD], original
        )
    elif original.get("pubstatus") != POST_STATE.CANCELLED:
        update_post_item(
            {"pubstatus": POST_STATE.CANCELLED, "_etag": original["_etag"]}, original
        )


def transform_link_from_text(item, fields):
    for field in fields:
        if item.get(field):
            url_pattern = re.compile(r"(https?://\S+|www\.\S+|\S+\.\S+)")

            # Replace URLs with anchor tags and update the href attribute
            def replace(match):
                url = match.group(0)
                if url.startswith("www."):
                    url_with_https = "https://" + url
                    return f'<a href="{url_with_https}">{url}</a>'
                elif not url.startswith(("http://", "https://")):
                    url_with_https = "https://" + url
                    return f'<a href="{url_with_https}">{url}</a>'
                else:
                    return f'<a href="{url}">{url}</a>'

            item[field] = url_pattern.sub(replace, item[field])
