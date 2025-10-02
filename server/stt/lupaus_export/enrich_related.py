from typing import Dict, List, Any, Set
from flask import current_app
from superdesk import get_resource_service
import logging

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
            for re in pl.get("related_events") or []:
                # tolerate various shapes
                for key in ("_id", "event", "event_id", "guid"):
                    val = re.get(key)
                    if val:
                        ids.add(str(val))
                        break
    return list(ids)


def _apply_projection_locally(
    docs: List[Dict[str, Any]], projection: Dict[str, int] | None
) -> List[Dict[str, Any]]:
    """
    Apply a MongoDB-like inclusion projection to a list of documents.

    Given a list of dictionaries, return a new list where each document
    contains only the fields whose entry in `projection` is truthy (e.g., 1 or True).
    If `projection` is None or empty, the original list is returned unchanged.

    Notes:
    - Only inclusion projections are supported. Setting a field to 0/False has no effect
        (the field is simply not included in the result).
    - If '_id' is present in `projection` with a truthy value, it will be included;
        otherwise it is omitted even if present in the input documents.
    - Fields requested in `projection` that do not exist in a document are ignored.
    - Input documents are not mutated; new, shallow dictionaries are created.

    Parameters:
            docs: List of input documents (dicts).
            projection: Mapping of field names to inclusion flags (1/True to include, 0/False/absent to omit).

    Returns:
            A list of new documents containing only the projected fields. If `projection` is falsy,
            the original `docs` list is returned as-is.

    Examples:
            >>> docs = [{'a': 1, 'b': 2, '_id': 'x'}, {'a': 3, 'c': 4}]
            >>> _apply_projection_locally(docs, {'a': 1})
            [{'a': 1}, {'a': 3}]
            >>> _apply_projection_locally(docs, {'a': 1, '_id': 1})
            [{'a': 1, '_id': 'x'}, {'a': 3}]
            >>> _apply_projection_locally(docs, None) is docs
            True
    """
    if not projection:
        return docs
    keep = {k for k, v in projection.items() if v}
    # Always keep _id if requested implicitly
    if "_id" in projection and projection["_id"]:
        keep.add("_id")
    return [{k: d.get(k) for k in keep if k in d} for d in docs]


def _find_many(
    resource: str, lookup: Dict[str, Any], projection: Dict[str, int] | None = None
) -> List[Dict[str, Any]]:
    """
    Try service.get_from_mongo with various signatures; fall back to service.get;
    and only if that fails, go to data layer without projection. If we can't push
    'projection' to the DB, we'll trim the fields locally.
    """
    # Prefer resource service
    try:
        svc = get_resource_service(resource)
    except Exception as e:
        logger.exception(
            "Error using service for %s (%s: %s).",
            resource,
            e.__class__.__name__,
            e,
        )
        svc = None

    # 1) service.get_from_mongo with (req=None, ...)
    if svc and hasattr(svc, "get_from_mongo"):
        try:
            docs = list(svc.get_from_mongo(None, lookup=lookup, projection=projection))
            if docs is not None:
                return _apply_projection_locally(docs, projection)
        except TypeError:
            # Signature mismatch; fall through to other strategies
            pass
        except Exception as e:
            logger.exception(
                "Error in _find_many service.get_from_mongo with (req=None, ...) using service for %s (%s: %s).",
                resource,
                e.__class__.__name__,
                e,
            )
            # Fall through to other strategies
            pass

    # 2) service.get (no projection)
    if svc and hasattr(svc, "get"):
        try:
            docs = list(svc.get(None, lookup))
            return _apply_projection_locally(docs, projection)
        except Exception as e:
            logger.exception(
                "Error in _find_many service.get (no projection) using service for %s (%s: %s).",
                resource,
                e.__class__.__name__,
                e,
            )
            pass

    # 3) Eve data layer (no projection kwarg supported in your build)
    try:
        cursor = current_app.data.find(resource, req=None, lookup=lookup)
        docs = list(cursor)
        logger.info("Using Eve data layer (no projection)")
        return _apply_projection_locally(docs, projection)
    except Exception as e:
        logger.exception(
            "Error in _find_many Eve data layer (no projection) using service for %s (%s: %s).",
            resource,
            e.__class__.__name__,
            e,
        )
        return []


def get_priority_from_agenda_item(item: Dict[str, Any]) -> str:
    """
    Extracts the 'priority' value from an agenda item.

    The function looks for the 'priority' in the 'subject' field of the item,
    which is expected to be a list of dictionaries. Each dictionary may contain
    a 'scheme' key. If a dictionary with 'scheme' equal to 'priority' is found,
    the corresponding 'name' value is returned.

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
    return ""


def get_category_from_agenda_item(item: Dict[str, Any]) -> str:
    """
    Extracts the "scheme": "categories" value from an agenda item subjects.

    The function looks for the 'categories' in the 'subject' field of the item,
    which is expected to be a list of dictionaries. Each dictionary may contain
    a 'scheme' key. If a dictionary with 'scheme' equal to 'categories' is found,
    the corresponding 'name' value is returned.

    If 'categories' is not found, an empty string is returned.

    Args:
        item: A dictionary representing an agenda item.
    Returns:
        The name of 'categories' if found, otherwise an empty string.
    """
    # categories is stored in subject like:
    # subject: [{'scheme': 'categories', 'name': 'Kulttuuri', 'qcode': '4'}]
    if not item:
        return ""
    if "subject" in item:
        for sub in item["subject"]:
            if sub.get("scheme") == "categories":
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


def _set_stt_fields(
    agendas: List[Dict[str, Any]],
    by_key: Dict[str, Dict[str, Any]],
    events: List[Dict[str, Any]],
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
            for re in pl.get("related_events") or []:
                key = re.get("_id")
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


def enrich_planning_agendas(agendas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Adds item.related_events_expanded = [event, ...]
    Each event has at least: _id, name, dates, location (resolved if IDs).
    """
    ev_ids = _collect_event_ids(agendas)
    logger.info(f"Enriching agendas: found {len(ev_ids)} unique related event IDs")
    logger.info(f"Enriching agendas: event IDs: {ev_ids}")
    if not ev_ids:
        _set_stt_fields(agendas, {}, [])
        return agendas

    # Search events by _ids
    events = _find_many(
        "events",
        {"_id": {"$in": ev_ids}},
        projection={
            "_id": 1,
            "name": 1,
            "dates": 1,
            "location": 1,
            "language": 1,
        },
    )
    if not events:
        _set_stt_fields(agendas, {}, [])
        return agendas

    # Map by both _id and guid for resilience
    by_key: Dict[str, Dict[str, Any]] = {}
    for e in events:
        if "_id" in e:
            by_key[str(e["_id"])] = e
    # Attach to each planning item
    _set_stt_fields(agendas, by_key, events)

    # Sort related_events_expanded by start date
    for ag in agendas or []:
        for pl in ag.get("items") or []:
            pl["related_events_expanded"].sort(
                key=lambda e: e.get("dates", {}).get("start")
                or e.get("dates", {}).get("end")
                or ""
            )

    return agendas
