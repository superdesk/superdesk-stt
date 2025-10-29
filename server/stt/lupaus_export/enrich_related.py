from typing import Dict, List, Any, Set
import logging

from stt.helpers.mongo_helpers import (
    find_many,
    get_published_items_with_sttnewsroomnote_by_planning_id,
)
from stt.helpers.template_helpers import exclude_drafts

logger = logging.getLogger(__name__)


def _collect_event_ids(agendas: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique related event identifiers from a collection of agendas.

    This function walks through each agenda's "items" and each item's
    "related_events", collecting the first available identifier from the keys
    "_id", "event", "event_id", or "guid". Collected identifiers are coerced to
    strings and deduplicated.

    - Accepts `agendas` as None or an empty list.
    - Silently tolerates missing or malformed structures.
    - The order of returned IDs is undefined.

    Args:
        agendas: A list of agenda dictionaries. Each agenda may include an "items"
            list; each item may include a "related_events" list of mappings.

    Returns:
        A list of unique event identifier strings extracted from related events.

    Example:
        >>> agendas = [
        ...     {"items": [{"related_events": [{"_id": 1}, {"event": "a"}]}]},
        ...     {"items": [{"related_events": [{"event_id": 1}, {"guid": "b"}]}]},
        ... ]
        >>> sorted(_collect_event_ids(agendas))
        ['1', 'a', 'b']
    """
    ids: Set[str] = set()
    for ag in agendas or []:
        for pl in ag.get("items") or []:
            for rel_event in pl.get("related_events") or []:
                # tolerate various shapes
                for key in ("_id", "event", "event_id", "guid"):
                    val = rel_event.get(key)
                    if val:
                        ids.add(str(val))
                        break
    return list(ids)


def _get_planning_coverages_metadata(
    pl: Dict[str, Any],
    item_type: str,
    imagetypes: bool = False,
) -> Dict[str, Any]:
    """Return coverage metadata for a planning item, fetching from Mongo if needed.

    When ``imagetypes`` is ``False`` (default) this
    returns the first available ``news_coverage_status`` mapping from the item's
    coverages. When ``imagetypes`` is ``True`` the function instead collects all
    ``sttimagetype`` subject ``name`` values from the coverages and returns them as
    ``{"imagetypes": [...]}``.

    The function first inspects the in-memory planning item and only falls back to a
    Mongo query when the desired information is missing locally.
    """

    if not pl:
        return {}

    coverages = [cov for cov in pl.get("coverages") or [] if isinstance(cov, dict)]

    imagetypes_local: List[str] = []
    if imagetypes:
        imagetypes_local = _collect_imagetypes_from_coverages(coverages)
        if imagetypes_local:
            return {"imagetypes": imagetypes_local}
    else:
        status = _extract_news_coverage_status(coverages)
        if status:
            return status

    pl_id = pl.get("_id")
    if not pl_id:
        return {"imagetypes": imagetypes_local} if imagetypes else {}

    coverages_from_db = _load_coverages_from_mongo(pl_id, item_type)
    if not coverages_from_db:
        return {"imagetypes": imagetypes_local} if imagetypes else {}

    if imagetypes:
        image_coverage_types = _collect_imagetypes_from_coverages(coverages_from_db)
        return {"imagetypes": image_coverage_types}

    return _extract_news_coverage_status(coverages_from_db)


def _extract_news_coverage_status(coverages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the first non-empty ``news_coverage_status`` mapping from coverages."""

    for cov in coverages:
        status = cov.get("news_coverage_status")
        if status:
            return status
    return {}


def _collect_imagetypes_from_coverages(coverages: List[Dict[str, Any]]) -> List[str]:
    """Collect unique ``sttimagetype`` subject names from coverage planning data."""

    seen: Set[str] = set()
    imagetypes: List[str] = []
    for cov in coverages:
        planning = cov.get("planning")
        if not isinstance(planning, dict):
            continue
        subjects = planning.get("subject")
        if not isinstance(subjects, list):
            continue
        for sub in subjects:
            if not isinstance(sub, dict) or sub.get("scheme") != "sttimagetype":
                continue
            name = sub.get("name") or sub.get("qcode")
            if name and name not in seen:
                seen.add(name)
                imagetypes.append(name)
    return imagetypes


def _load_coverages_from_mongo(pl_id: str, item_type: str) -> List[Dict[str, Any]]:
    """Fetch coverages for a planning item directly from Mongo using ``find_many``."""

    if not pl_id:
        return []

    if item_type == "kuva":
        lookup = {
            "_id": pl_id,
            "coverages.planning.g2_content_type": {"$in": ["graphic", "picture"]},
        }
    else:
        lookup = {
            "_id": pl_id,
            "coverages.planning.g2_content_type": "text",
        }

    docs = find_many("planning", lookup, projection={"coverages": 1, "_id": 0})
    if not docs:
        return []

    coverages = docs[0].get("coverages") if isinstance(docs[0], dict) else None
    if not isinstance(coverages, list):
        return []

    return [cov for cov in coverages if isinstance(cov, dict)]


def get_priority_from_agenda_item(item: Dict[str, Any]) -> str:
    """
    Extracts the 'priority' value from an agenda item.

    The function looks for the 'priority' in the 'subject' field of the item,
    which is expected to be a list of dictionaries. Each dictionary may contain
    a 'scheme' key. If a dictionary with 'scheme' equal to 'priority' is found,
    the corresponding 'name' value is returned.

    Or it looks in 'priority' field as a numeric value and maps it to a string.

    If 'priority' is not found, an empty string is returned.

    Args:
        item: A dictionary representing an agenda item.
    Returns:
        The value of 'priority' if found, otherwise an empty string.
    """
    # priority is stored in subject like:
    # subject: [{'scheme': 'priority', 'name': 'Perus (2 700)', 'qcode': '2'}]
    if not item:
        return ""
    if "subject" in item:
        for sub in item["subject"]:
            if sub.get("scheme") == "priority":
                return sub.get("name", "")
    if "priority" in item:
        numeric_priority = item.get("priority", "")
        # if numeric_priority is > 0, return customized priority with synthetic 'name'-field
        if numeric_priority and numeric_priority > 0:
            # 1 = Pääaihe (3300), 2 = Perus (2000), 3 = Perus+ (2700), 4 = Lyhyt (800), 5 = Vain tulokset
            priority_map = {
                1: "Pääaihe (3 300)",
                2: "Perus (2 000)",
                3: "Perus+ (2 700)",
                4: "Lyhyt (800)",
                5: "Vain tulokset",
                6: "Vain tsekkaus",
            }
            return priority_map.get(numeric_priority, "")

    return ""


def get_category_from_agenda_item(item: Dict[str, Any]) -> str:
    """
    Extracts the "scheme": "categories" value from an agenda item subjects or anpa_category.

    The function looks for the 'categories' in the 'subject' field of the item,
    which is expected to be a list of dictionaries. Each dictionary may containa 'scheme' key. If a dictionary with 'scheme' equal to 'categories' is found,
    a 'scheme' key. If a dictionary with 'scheme' equal to 'categories' is found,
    the corresponding 'name' value is returned.

    Or it looks in 'anpa_category' field.

    If 'categories' is not found, an empty string is returned.

    Args:
        item: A dictionary representing an agenda item.
    Returns:
        The name of 'categories' if found, otherwise an empty string.
    """
    # categories is stored in subject like:
    # subject: [{'scheme': 'categories', 'name': 'Kulttuuri', 'qcode': '4'}]
    # or in anpa_category like:
    # 'anpa_category': [{'name': 'Kulttuuri', 'qcode': '4'}]
    if not item:
        return ""
    if "subject" in item:
        for sub in item["subject"]:
            if sub.get("scheme") == "categories":
                return sub.get("name", "")
    if "anpa_category" in item:
        for sub in item["anpa_category"]:
            if sub:
                return sub.get("name", "")
    return ""


def get_numeric_value_from_priority(priority: str) -> str:
    """
    Extracts the numeric value from a priority string.

    The function assumes that the priority string is formatted as
    'Some text (number)', where 'number' is the numeric
    value to be extracted. It looks for the last pair of parentheses
    in the string and extracts the content within them. If the content
    can be converted to an integer, it is returned (as a string). If not, or if the
    expected format is not found, the function returns an empty string.

    There's one exception: "Vain tulokset" and in that case we return "Vain tulokset"

    Args:
        priority: A string representing the priority.
    Returns:
        The numeric value extracted from the priority string, or an empty string if not found or not convertible.
    """

    if not priority:
        return ""
    if priority == "Vain tulokset":
        return priority
    try:
        # Find the last '(' and ')' and extract the content between them
        start = priority.rindex("(") + 1
        end = priority.rindex(")")
        number_str = priority[start:end].strip()
        return str(number_str.replace(" ", ""))
    except (ValueError, IndexError):
        logger.error("Could not extract numeric value from priority: '%s'", priority)
        return ""


def _set_priority_fields(pl: Dict[str, Any]) -> None:
    """Compute and set priority fields on a planning item in a single place."""
    priority = get_priority_from_agenda_item(pl)
    priority_numeric = get_numeric_value_from_priority(priority)
    pl["stt_priority"] = priority
    pl["stt_priority_numeric"] = priority_numeric


def _get_latest_published_item(
    published_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns the latest published item from a list based on 'versioncreated'.
    If the list is empty, returns an empty dictionary.
    Args:
        published_items: A list of published item dictionaries.
    Returns:
        The latest published item dictionary, or an empty dictionary if the list is empty.
    """
    if not published_items:
        return {}
    # first filter out items that do not have subject with scheme 'sttnewsroomnote' and qcode "nootherversions", "printformat" or "validforprint"
    filtered_items = [
        item
        for item in published_items
        if any(
            sub.get("scheme") == "sttnewsroomnote"
            and sub.get("qcode") in ["nootherversions", "printformat", "validforprint"]
            for sub in item.get("subject", [])
        )
    ]
    if not filtered_items:
        return {}
    # get latest item from filtered_items by versioncreated (datetime string)
    latest_item = max(
        filtered_items,
        key=lambda item: item.get("versioncreated", ""),
    )
    return latest_item


def _set_stt_fields(
    agendas: List[Dict[str, Any]],
    by_key: Dict[str, Dict[str, Any]],
    events: List[Dict[str, Any]],
    item_type: str,
) -> List[Dict[str, Any]]:
    """
    Sets stt_priority and stt_priority_numeric fields on each planning item.
    Filters out items without a valid stt_priority.
    If events is empty, sets related_events_expanded to [].
    Expands related_events to related_events_expanded using by_key mapping.
    """

    for ag in agendas or []:
        new_items: List[Dict[str, Any]] = []
        for pl in ag.get("items") or []:
            # get news_coverage_status for planning item
            news_coverage_status = _get_planning_coverages_metadata(pl, item_type)
            pl["news_coverage_status"] = news_coverage_status
            # get sttimagetypes for planning item (always use "kuva" as item_type to get image types)
            item_imagetypes = _get_planning_coverages_metadata(
                pl, "kuva", imagetypes=True
            )
            pl["sttimagetypes"] = item_imagetypes.get("imagetypes") or []
            # try to get latest published item with sttnewsroomnote subject
            published_related_items = (
                get_published_items_with_sttnewsroomnote_by_planning_id(pl.get("_id"))
            )
            latest_published_item = _get_latest_published_item(published_related_items)
            # attach latest published item to planning item
            pl["latest_published_item"] = latest_published_item
            _set_priority_fields(pl)
            if not pl.get("stt_priority"):
                continue  # exclude items without priority
            # if events is empty list, related_events_expanded will be empty
            if not events:
                pl["related_events_expanded"] = []
                new_items.append(pl)
                continue
            # Expand related events
            expanded: List[Dict[str, Any]] = []
            for rel_event in pl.get("related_events") or []:
                key = rel_event.get("_id")
                ev = by_key.get(str(key)) if key else None
                if ev:
                    expanded.append(ev)
            pl["related_events_expanded"] = expanded
            new_items.append(pl)
        ag["items"] = new_items
        # group agenda items by category
        grouped_agendas = _group_agenda_items_by_category(ag)
        # and attach to agenda
        ag["grouped_items"] = grouped_agendas
        # get main topic items (highest priority)
        main_topic_items = _get_items_with_highest_priority(ag)
        ag["main_topic_items"] = main_topic_items
    return agendas


def _group_agenda_items_by_category(
    ag: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups agenda items by their category.

    Args:
        agendas: A list of agenda dictionaries. Each agenda may include an "items"
            list; each item may include a "categories" field.

    Returns:
        A dictionary where keys are categories and values are lists of agenda items
        belonging to those categories. Items without a category are grouped under
        the key 'Uncategorized'.
    """
    categorized_items: Dict[str, List[Dict[str, Any]]] = {}
    for pl in ag.get("items") or []:
        category_name = get_category_from_agenda_item(pl) or "Uncategorized"
        if category_name not in categorized_items:
            categorized_items[category_name] = []
        categorized_items[category_name].append(pl)
    # sort categories like: Kotimaa, Politiikka, Talous, Kulttuuri, Ulkomaat, Urheilu
    sorted_categories = [
        "Kotimaa",
        "Politiikka",
        "Talous",
        "Kulttuuri",
        "Ulkomaat",
        "Urheilu",
    ]
    categorized_items = {
        k: categorized_items[k] for k in sorted_categories if k in categorized_items
    }
    return categorized_items


def _get_items_with_highest_priority(
    ag: Dict[str, Any],
) -> List[Dict[str, Any]]:
    # if stt_priority_numeric is 3300, it is the highest priority
    highest_priority = 3300
    main_topic_items = []
    for pl in ag.get("items") or []:
        try:
            priority_numeric = int(pl.get("stt_priority_numeric", "0"))
            if priority_numeric == highest_priority:
                main_topic_items.append(pl)
        except ValueError:
            continue
    return main_topic_items


def enrich_planning_agendas(
    agendas: List[Dict[str, Any]], item_type: str
) -> List[Dict[str, Any]]:
    """
    Adds item.related_events_expanded = [event, ...]
    Each event has at least: _id, name, dates, location (resolved if IDs).
    Also adds item.stt_priority and item.stt_priority_numeric fields.
    Args:
        agendas: A list of agenda dictionaries. Each agenda may include an "items"
            list; each item may include a "related_events" list of mappings.
        item_type: The type of the planning item, 'teksti' / 'kuva'.
    Returns:
        The input list of agendas, with each planning item enriched with
        'related_events_expanded', 'stt_priority', and 'stt_priority_numeric' fields.
        Items without a valid 'stt_priority' are excluded from the agendas.
    """
    for ag in agendas:
        # Exclude draft items
        items = exclude_drafts(ag.get("items") or [])
        ag["items"] = items

    # Collect unique event IDs from all agendas
    ev_ids = _collect_event_ids(agendas)
    logger.info(f"Enriching agendas: found {len(ev_ids)} unique related event IDs")
    logger.info(f"Enriching agendas: event IDs: {ev_ids}")
    if not ev_ids:
        _set_stt_fields(agendas, {}, [], item_type)
        return agendas

    # Search events by _ids
    events = find_many(
        "events",
        {"_id": {"$in": ev_ids}},
        projection={
            "_id": 1,
            "name": 1,
            "dates": 1,
            "location": 1,
            "subject": 1,
        },
    )
    if not events:
        _set_stt_fields(agendas, {}, [], item_type)
        return agendas

    # Map by both _id and guid for resilience
    by_key: Dict[str, Dict[str, Any]] = {}
    for e in events:
        if "_id" in e:
            by_key[str(e["_id"])] = e
    # Attach to each planning item
    _set_stt_fields(agendas, by_key, events, item_type)

    # Sort related_events_expanded by start date
    for ag in agendas or []:
        for pl in ag.get("items") or []:
            pl["related_events_expanded"].sort(
                key=lambda e: e.get("dates", {}).get("start")
                or e.get("dates", {}).get("end")
                or ""
            )

    return agendas
