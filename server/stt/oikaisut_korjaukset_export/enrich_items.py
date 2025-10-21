from typing import Dict, List, Any
import logging

from stt.helpers.mongo_helpers import find_many
from stt.helpers.template_helpers import exclude_drafts

logger = logging.getLogger(__name__)


def _get_related_corrected_published_items(planning_id: str) -> List[Dict[str, Any]]:
    # first search from "delivery" collection by planning_id
    deliveries = find_many(
        "delivery",
        {"planning_id": planning_id, "item_state": "published"},
        projection={"item_id": 1, "_id": 0},
    )
    # then loop through delivery results and get full items from "published" collection by matching item_id
    published_items = []
    for delivery in deliveries:
        item_id = delivery.get("item_id")
        if item_id:
            # include only items that have state "corrected" (Korjaus) or genre.qcode "sttgenre:11" (Oikaisu)
            items = find_many(
                "published",
                {
                    "item_id": item_id,
                    "$or": [
                        {"state": "corrected"},  # Korjaus
                        {"genre.qcode": "sttgenre:11"},  # Oikaisu
                    ],
                },
                projection={
                    "anpa_category": 1,
                    "assignment_id": 1,
                    "body_html": 1,
                    "headline": 1,
                    "ednote": 1,
                    "genre": 1,
                    "priority": 1,
                    "profile": 1,
                    "slugline": 1,
                    "state": 1,
                    "subject": 1,
                    "urgency": 1,
                    "operation": 1,
                    "item_id": 1,
                    "firstpublished": 1,
                    "profile": 1,
                },
            )
            if items:
                # add all found items to published_items
                published_items.extend(items)
    return published_items


def _enrich_item(item: Dict[str, Any]) -> Dict[str, Any]:
    # find related corrected published items
    planning_id = item.get("_id")
    if not planning_id:
        return item
    related_items = _get_related_corrected_published_items(planning_id)
    if related_items:
        item["related_corrected_published_items"] = related_items
        # if item has "internal_coverages" field, we can remove it to reduce output size
        if "internal_coverages" in item:
            del item["internal_coverages"]
    return item


def _group_items_by_type(
    items: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    oikaisut = []
    korjaukset = []
    # exclude draft items
    items = exclude_drafts(items)
    for item in items:
        # enrich item so we can check if it has related corrected published items
        item = _enrich_item(item)
        # loop item.related_corrected_published_items and check for "state"
        # if state is "corrected" then it should be put to "korjaukset" array
        # if state is not "corrected", then it should be put to "oikaisut" array
        related_items = item.get("related_corrected_published_items", [])
        item_without_related_corrected_published_items = {
            k: v for k, v in item.items() if k != "related_corrected_published_items"
        }
        for related_item in related_items:
            state = related_item.get("state")
            if state == "corrected":
                # add item_without_related_corrected_published_items to corrected_item and then add related_item to it
                corrected_item = {
                    **item_without_related_corrected_published_items,
                    "corrected_published_item": related_item,
                }
                korjaukset.append(corrected_item)
            else:
                # add item_without_related_corrected_published_items to corrected_item and then add related_item to it
                corrected_item = {
                    **item_without_related_corrected_published_items,
                    "corrected_published_item": related_item,
                }
                oikaisut.append(corrected_item)
    return {"oikaisut": oikaisut, "korjaukset": korjaukset}


def enrich_oikaisut_korjaukset_for_export(
    items: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Enrich and filters oikaisut_korjaukset items for export.
    Always returns oikaisut and korjaukset arrays even if they are empty.
    Items include all planning items from certain time range.
    We need to put them into two separate arrays: oikaisut and korjaukset based on item meta data.
    Args:
        items (List[Dict[str, Any]]): List of planning items.
    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary with two keys: oikaisut and korjaukset.
    """
    rows = items or []
    if not rows:
        return {"oikaisut": [], "korjaukset": []}
    rows_grouped = _group_items_by_type(rows)
    return rows_grouped
