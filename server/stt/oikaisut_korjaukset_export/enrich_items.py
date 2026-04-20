from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
import logging
from zoneinfo import ZoneInfo

from stt.constants import STT_TIMEZONE
from stt.helpers.mongo_helpers import (
    find_many,
    get_planning_items_with_published_corrections_between,
)
from stt.helpers.template_helpers import exclude_drafts

logger = logging.getLogger(__name__)

_HELSINKI = ZoneInfo(STT_TIMEZONE)


def _get_previous_day_evening_window_utc(
    now: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """Return the previous day's 20:00-00:00 Helsinki window in UTC."""

    current_time = now
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    elif current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)

    now_local = current_time.astimezone(_HELSINKI)
    today_local = now_local.date()
    previous_day_local = today_local - timedelta(days=1)

    start_local = datetime.combine(
        previous_day_local,
        time(20, 0),
        tzinfo=_HELSINKI,
    )
    end_local = datetime.combine(today_local, time.min, tzinfo=_HELSINKI)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _merge_unique_items_by_id(
    items: List[Dict[str, Any]],
    extra_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Append extra planning items while preserving order and uniqueness."""

    merged = list(items or [])
    seen_ids = {
        str(item.get("_id"))
        for item in merged
        if isinstance(item, dict) and item.get("_id")
    }

    for item in extra_items or []:
        if not isinstance(item, dict):
            continue
        item_id = item.get("_id")
        if not item_id:
            merged.append(item)
            continue
        normalized_item_id = str(item_id)
        if normalized_item_id in seen_ids:
            continue
        seen_ids.add(normalized_item_id)
        merged.append(item)

    return merged


def _get_previous_day_evening_items() -> List[Dict[str, Any]]:
    start_dt, end_dt = _get_previous_day_evening_window_utc()
    return get_planning_items_with_published_corrections_between(
        start_dt,
        end_dt,
        projection={
            "_id": 1,
            "anpa_category": 1,
            "internal_coverages": 1,
            "planning_date": 1,
            "priority": 1,
            "slugline": 1,
            "state": 1,
        },
    )


def _is_oikaisu(item: Dict[str, Any]) -> bool:
    """
    Determine whether the provided item represents an "oikaisu" correction.

    An item is considered an oikaisu if its "genre" field (which may be a dict
    or a list of dicts) contains an entry with the qcode "sttgenre:11".

    Args:
        item: A dictionary representing the item metadata.

    Returns:
        True if the item is classified as an oikaisu; otherwise, False.
    """
    genre = item.get("genre")
    if isinstance(genre, dict):
        return genre.get("qcode") == "sttgenre:11"
    if isinstance(genre, list):
        return any(
            isinstance(entry, dict) and entry.get("qcode") == "sttgenre:11"
            for entry in genre
        )
    return False


def _get_related_corrected_published_items(planning_id: str) -> List[Dict[str, Any]]:
    # first search from "delivery" collection by planning_id
    deliveries = find_many(
        "delivery",
        {"planning_id": planning_id, "item_state": "published"},
        projection={"item_id": 1, "_id": 0},
    )
    # then loop through delivery results and get full items from
    # "published" collection by matching item_id
    published_items = []
    for delivery in deliveries:
        item_id = delivery.get("item_id")
        if item_id:
            # include only items that have state "corrected" (Korjaus) or
            # genre.qcode "sttgenre:11" (Oikaisu)
            items = find_many(
                "published",
                {
                    "item_id": item_id,
                    "$or": [
                        {"state": "corrected"},  # Korjaus
                        {"genre.qcode": "sttgenre:11"},  # Oikaisu
                    ],
                    # Ignore all items with profile "nettiuutinen"
                    "profile": {"$ne": "nettiuutinen"},
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
                },
            )
            if items:
                # add all found items to published_items
                published_items.extend(items)

    # If there is at least one oikaisu for this planning_id,
    # ignore korjaus items.
    if any(_is_oikaisu(item) for item in published_items):
        published_items = [
            item for item in published_items if item.get("state") != "corrected"
        ]

    return published_items


def _enrich_item(item: Dict[str, Any]) -> Dict[str, Any]:
    # find related corrected published items
    planning_id = item.get("_id")
    if not planning_id:
        return item
    related_items = _get_related_corrected_published_items(planning_id)
    if related_items:
        item["related_corrected_published_items"] = related_items
        # if item has "internal_coverages" field,
        # we can remove it to reduce output size
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
        # enrich item so we can check if it has
        # related corrected published items
        item = _enrich_item(item)
        # loop item.related_corrected_published_items and check for "state"
        # if state is "corrected" then it should be put to "korjaukset" array
        # if state is not "corrected", then it should be put
        # to "oikaisut" array
        related_items = item.get("related_corrected_published_items", [])
        item_without_related_corrected_published_items = {
            k: v for k, v in item.items() if k != "related_corrected_published_items"
        }
        for related_item in related_items:
            state = related_item.get("state")
            if state == "corrected":
                # add item_without_related_corrected_published_items to
                # corrected_item and then add related_item to it
                corrected_item = {
                    **item_without_related_corrected_published_items,
                    "corrected_published_item": related_item,
                }
                korjaukset.append(corrected_item)
            else:
                # add item_without_related_corrected_published_items to
                # corrected_item and then add related_item to it
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
    Enrich and filter oikaisut_korjaukset items for export.
    Always returns oikaisut and korjaukset arrays even if they are empty.
    Items include all planning items from certain time range.
    We need to put them into two separate arrays: oikaisut and korjaukset based on item meta data.
    Args:
        items (List[Dict[str, Any]]): List of planning items.
    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary with two keys: oikaisut and korjaukset.
    """
    rows = items or []
    rows = _merge_unique_items_by_id(rows, _get_previous_day_evening_items())
    if not rows:
        return {"oikaisut": [], "korjaukset": []}
    rows_grouped = _group_items_by_type(rows)
    return rows_grouped
