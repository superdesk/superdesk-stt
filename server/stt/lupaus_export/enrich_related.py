import datetime
from typing import Dict, List, Any, Set
import logging

from stt.helpers.mongo_helpers import (
    find_many,
    get_published_items_by_planning_id_and_genre_qcodes,
    get_published_items_with_sttnewsroomnote_by_planning_id,
)
from stt.helpers.template_helpers import (
    exclude_drafts,
    exclude_merkkipaivapalvelu_items,
)

logger = logging.getLogger(__name__)


_EXCLUDED_PICTURESERVICE_SUBJECTS = {
    ("sttpictureservice", "Tilauskuvaus"),
    ("sttpictureservice", "Arkistoon"),
}


def _item_has_genre_qcode(item: Dict[str, Any], qcode: str) -> bool:
    """Return True when item.genre contains a matching qcode.

    Tolerates ``genre`` being either a dict or a list of dicts.
    """

    if not item or not qcode:
        return False
    genre = item.get("genre")
    if isinstance(genre, dict):
        return genre.get("qcode") == qcode
    if isinstance(genre, list):
        return any(isinstance(g, dict) and g.get("qcode") == qcode for g in genre)
    return False


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


def _is_excluded_pictureservice_coverage(cov: Dict[str, Any]) -> bool:
    """Return True when coverage has an excluded picture-service subject."""

    if not isinstance(cov, dict):
        return False

    planning = cov.get("planning")
    if not isinstance(planning, dict):
        return False

    subjects = planning.get("subject")
    if not isinstance(subjects, list):
        return False

    for sub in subjects:
        if not isinstance(sub, dict):
            continue
        if (
            sub.get("scheme"),
            sub.get("qcode"),
        ) in _EXCLUDED_PICTURESERVICE_SUBJECTS:
            return True

    return False


def _filter_coverages(coverages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove coverages excluded by STT picture-service subject markers."""

    return [cov for cov in coverages if not _is_excluded_pictureservice_coverage(cov)]


def _get_planning_coverages_metadata(
    pl: Dict[str, Any],
    item_type: str,
    imagetypes: bool = False,
    sttpicturewhatabout: bool = False,
) -> Dict[str, Any]:
    """Return coverage metadata for a planning item, fetching from Mongo if needed.

    When ``imagetypes`` is ``False`` (default) this
    returns the first available ``news_coverage_status`` mapping from the item's
    coverages. When ``imagetypes`` is ``True`` the function instead collects all
    ``sttimagetype`` subject ``name`` values from the coverages and returns them as
    ``{"imagetypes": [...]}``.
    If ``sttpicturewhatabout`` is ``True``, the function returns the values from the
    ``sttpicturewhatabout`` fields from coverages planning fields.

    The function first inspects the in-memory planning item and only falls back to a
    Mongo query when the desired information is missing locally.
    """

    if not pl:
        return {}

    coverages = _filter_coverages(
        [cov for cov in pl.get("coverages") or [] if isinstance(cov, dict)]
    )

    imagetypes_local: List[str] = []
    sttpicturewhatabouts_local: List[str] = []

    if sttpicturewhatabout:
        sttpicturewhatabouts_local = _get_sttpicturewhatabouts_from_coverages(coverages)
        if sttpicturewhatabouts_local:
            return {"sttpicturewhatabout": sttpicturewhatabouts_local}

    elif imagetypes:
        imagetypes_local = _collect_imagetypes_from_coverages(coverages)
        if imagetypes_local:
            return {"imagetypes": imagetypes_local}
    elif not imagetypes and not sttpicturewhatabout:
        status = _extract_news_coverage_status(coverages, item_type)
        if status:
            return status

    pl_id = pl.get("_id")
    if not pl_id:
        if sttpicturewhatabout:
            return (
                {"sttpicturewhatabout": sttpicturewhatabouts_local}
                if sttpicturewhatabouts_local
                else {}
            )
        elif imagetypes:
            return {"imagetypes": imagetypes_local} if imagetypes_local else {}
        return {}

    coverages_from_db = _load_coverages_from_mongo(pl_id, item_type)
    if not coverages_from_db:
        return {"imagetypes": imagetypes_local} if imagetypes else {}

    if sttpicturewhatabout:
        sttpicturewhatabouts_db = _get_sttpicturewhatabouts_from_coverages(
            coverages_from_db
        )
        return {"sttpicturewhatabout": sttpicturewhatabouts_db}
    if imagetypes:
        image_coverage_types = _collect_imagetypes_from_coverages(coverages_from_db)
        return {"imagetypes": image_coverage_types}

    return _extract_news_coverage_status(coverages_from_db, item_type)


def _extract_news_coverage_status(
    coverages: List[Dict[str, Any]], item_type: str
) -> Dict[str, Any]:
    """
    Return the first non-empty ``news_coverage_status`` mapping from coverages.
    Double check that g2_content_type matches item_type => 'teksti' == 'text'.
    With 'kuva' (kuvalupaus) it does not matter because we include only items with "Tehdään" ("ncostat:int") status.
    """

    for cov in coverages:
        status = cov.get("news_coverage_status")
        planning = cov.get("planning")
        if planning and isinstance(planning, dict):
            g2_content_type = planning.get("g2_content_type")
            if item_type == "teksti" and g2_content_type != "text":
                continue
        if status:
            """status is a dict like:
                {
                "label": "Ehkä",
                "name": "coverage not decided yet",
                "qcode": "ncostat:notdec"
            }"""
            return status
    return {}


def _collect_imagetypes_from_coverages(
    coverages: List[Dict[str, Any]],
) -> List[str]:
    """
    Collect unique ``sttimagetype`` subject names from coverage planning data.
    Exclude if news_coverage_status qcode is not "ncostat:int"
    """

    seen: Set[str] = set()
    imagetypes: List[str] = []
    for cov in coverages:
        planning = cov.get("planning")
        if not isinstance(planning, dict):
            continue
        subjects = planning.get("subject")
        if not isinstance(subjects, list):
            continue
        status = cov.get("news_coverage_status")
        # exclude if news_coverage_status qcode is not "ncostat:int" ("Tehdään")
        if status and status.get("qcode") != "ncostat:int":
            continue
        for sub in subjects:
            if not isinstance(sub, dict) or sub.get("scheme") != "sttimagetype":
                continue
            name = sub.get("name") or sub.get("qcode")
            if name and name not in seen:
                seen.add(name)
                imagetypes.append(name)
    return imagetypes


def _get_sttpicturewhatabouts_from_coverages(
    coverages: List[Dict[str, Any]],
) -> List[str]:
    """sttpicturewhatabout is stored in coverage.planning.fields with field "sttpicturewhatabout" => get the value field value"""
    sttpicturewhatabouts: List[str] = []
    for cov in coverages:
        planning = cov.get("planning")
        if not isinstance(planning, dict):
            continue
        fields = planning.get("fields", [])
        for field in fields:
            field_name = field.get("field")
            if field_name == "sttpicturewhatabout" and field.get("value"):
                sttpicturewhatabouts.append(field.get("value", ""))
    return sttpicturewhatabouts


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

    return _filter_coverages([cov for cov in coverages if isinstance(cov, dict)])


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
            # 1 = Pääaihe (3300), 2 = Perus+ (2700), 3 = Perus (2000), 4 = Lyhyt (800), 5 = Vain tulokset, 6 = Vain tsekkaus
            priority_map = {
                1: "Pääaihe (3 300)",
                2: "Perus+ (2 700)",
                3: "Perus (2 000)",
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

    There's two exceptions: "Vain tulokset" / "Vain tsekkaus" and in that case we return the priority string as is.

    Args:
        priority: A string representing the priority.
    Returns:
        The numeric value extracted from the priority string, or an empty string if not found or not convertible.
    """

    if not priority:
        return ""
    if priority == "Vain tulokset" or priority == "Vain tsekkaus":
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


def _set_priority_fields(pl: Dict[str, Any], item_type: str) -> None:
    """Compute and set priority fields on a planning item in a single place."""
    priority = get_priority_from_agenda_item(pl)
    priority_numeric = get_numeric_value_from_priority(priority)
    # if priority is "Vain tsekkaus", do not set the fields (so the item gets excluded)
    if priority == "Vain tsekkaus":
        return
    # if item_type is "teksti" ("basic" lupaus) and priority is "Vain tulokset", do not set the fields (so the item gets excluded)
    if item_type == "teksti" and priority == "Vain tulokset":
        return
    sort_value = -1
    if isinstance(priority_numeric, str):
        numeric_str = priority_numeric.replace(" ", "")
        if numeric_str.isdigit():
            sort_value = int(numeric_str)
    elif isinstance(priority_numeric, (int, float)):
        sort_value = int(priority_numeric)
    pl["stt_priority"] = priority
    pl["stt_priority_numeric"] = priority_numeric
    # add also a sortable numeric field
    pl["stt_priority_numeric_sort"] = sort_value


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
    # first filter out items that do not have subject with scheme 'sttnewsroomnote' and qcode "nootherversions" or "printformat"
    filtered_items = [
        item
        for item in published_items
        if any(
            sub.get("scheme") == "sttnewsroomnote"
            and sub.get("qcode") in ["nootherversions", "printformat"]
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
    Enrich agendas with the metadata required by the Lupaus/Kuvalupaus exports.

    For each planning item the function:
    - attaches coverage metadata (``news_coverage_status``, ``sttimagetypes``,
        ``sttpicturewhatabouts``) and the latest published item when available
    - skips items that lack the coverage information or priority expected for
        the given ``item_type``
    - sets ``stt_priority``, ``stt_priority_numeric`` and
        ``stt_priority_numeric_sort``
        - expands related events into a chronologically sorted
            ``related_events_expanded`` when event lookups are supplied

    After processing, each agenda contains:
    - ``grouped_items``: mapping planning dates to categories and their items
    - ``has_multiple_dates``: flag indicating several planning dates are present
    - ``main_topic_items``: items whose priority numeric equals the highest
        configured value (3300)

    Returns the filtered/enriched agendas list.
    """

    genre_cache: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for ag in agendas or []:
        new_items: List[Dict[str, Any]] = []
        for pl in ag.get("items") or []:
            # get news_coverage_status for planning item
            news_coverage_status = _get_planning_coverages_metadata(pl, item_type)
            if item_type == "teksti" and not news_coverage_status:
                continue  # exclude items without news_coverage_status for 'teksti' items
            pl["news_coverage_status"] = news_coverage_status
            # get sttimagetypes for planning item (always use "kuva" as item_type to get image types from coverages)
            item_imagetypes = _get_planning_coverages_metadata(
                pl, "kuva", imagetypes=True
            )
            pl["sttimagetypes"] = item_imagetypes.get("imagetypes") or []
            if item_type == "kuva":
                # if this is an "kuvalupaus" and sttimagetypes is empty, exclude the item
                if not pl["sttimagetypes"]:
                    continue
            # get sttpicturewhatabouts for planning item
            item_sttpicturewhatabouts = _get_planning_coverages_metadata(
                pl, item_type, sttpicturewhatabout=True
            )
            pl["sttpicturewhatabouts"] = (
                item_sttpicturewhatabouts.get("sttpicturewhatabout") or []
            )
            # try to get latest published item with sttnewsroomnote subject
            published_related_items = (
                get_published_items_with_sttnewsroomnote_by_planning_id(pl.get("_id"))
            )
            latest_published_item = _get_latest_published_item(published_related_items)
            # attach latest published item to planning item
            pl["latest_published_item"] = latest_published_item

            planning_id = pl.get("_id")
            planning_id_str = str(planning_id) if planning_id else ""
            cached = genre_cache.get(planning_id_str) if planning_id_str else None
            if cached is None and planning_id_str:
                genre_items = get_published_items_by_planning_id_and_genre_qcodes(
                    planning_id_str, ["sttgenre:23", "sttgenre:2"]
                )
                cached = {
                    "fact_box_items": [
                        item
                        for item in genre_items
                        if _item_has_genre_qcode(item, "sttgenre:23")
                    ],
                    "armpit_items": [
                        item
                        for item in genre_items
                        if _item_has_genre_qcode(item, "sttgenre:2")
                    ],
                }
                genre_cache[planning_id_str] = cached

            pl["fact_box_items"] = (
                cached.get("fact_box_items", []) if cached is not None else []
            )
            pl["armpit_items"] = (
                cached.get("armpit_items", []) if cached is not None else []
            )
            _set_priority_fields(pl, item_type)
            if "stt_priority" not in pl:
                continue  # exclude items without "stt_priority" key set (eg. "Vain tsekkaus" items)
            # if events is empty list, related_events_expanded will be empty
            if not events:
                pl["related_events_expanded"] = []
                new_items.append(pl)
                continue
            # Expand related events and sort by start date (with fallback to end)
            expanded: List[Dict[str, Any]] = []
            for rel_event in pl.get("related_events") or []:
                key = rel_event.get("_id")
                ev = by_key.get(str(key)) if key else None
                if ev:
                    expanded.append(ev)
            expanded.sort(
                key=lambda e: e.get("dates", {}).get("start")
                or e.get("dates", {}).get("end")
                or ""
            )
            pl["related_events_expanded"] = expanded
            new_items.append(pl)
        ag["items"] = new_items
        # group agenda items
        grouped_agendas = _group_agenda_items(ag, item_type)
        ag["has_multiple_dates"] = len(grouped_agendas) > 1
        # and attach to agenda
        ag["grouped_items"] = grouped_agendas
    return agendas


def _group_agenda_items_by_planning_date(
    ag: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups agenda items by their planning date.

    Args:
        agendas: A list of agenda dictionaries. Each agenda may include an "items"
            list; each item may include a "planning_date" field.

    Returns:
        A dictionary where keys are planning dates and values are lists of agenda items
        belonging to those planning dates. Items without a planning date are grouped under
        the key 'Undated'.
    """
    dated_items: Dict[str, List[Dict[str, Any]]] = {}
    for pl in ag.get("items") or []:
        planning_date_value = pl.get("planning_date")
        planning_date = "Undated"

        if isinstance(planning_date_value, datetime.datetime):
            planning_date = planning_date_value.date().isoformat()
        elif isinstance(planning_date_value, datetime.date):
            planning_date = planning_date_value.isoformat()
        elif isinstance(planning_date_value, str):
            planning_date = planning_date_value
            if "T" in planning_date:
                planning_date = planning_date.split("T")[0]
        # tolerate falsy values after normalization
        if not planning_date:
            planning_date = "Undated"
        if planning_date not in dated_items:
            dated_items[planning_date] = []
        dated_items[planning_date].append(pl)
    return dated_items


def _select_main_topic_items_for_date(
    date_items: List[Dict[str, Any]],
    main_topic_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return main-topic items that belong to the supplied date bucket.

    Falls back to comparing ``_id`` values in case the objects referenced by
    ``main_topic_items`` differ from the entries stored in ``date_items``.
    """

    if not main_topic_items or not date_items:
        return []

    selected: List[Dict[str, Any]] = []
    date_item_ids = {
        item.get("_id")
        for item in date_items
        if isinstance(item, dict) and item.get("_id")
    }

    for candidate in main_topic_items:
        if candidate in date_items:
            selected.append(candidate)
            continue
        candidate_id = candidate.get("_id") if isinstance(candidate, dict) else None
        if candidate_id and candidate_id in date_item_ids:
            selected.append(candidate)

    return selected


def _group_agenda_items(
    ag: Dict[str, Any], item_type: str
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Groups agenda items first by planning date and then by category.
    Add main_topic_items key for highest-priority items for each date if item_type is "teksti".

    Args:
        ag: A single agenda dictionary that already contains an "items" list.

    Returns:
        A nested dictionary of the form ``{date: {"Kotimaa": [items...]}, "Politiikka": [items...]}, main_topic_items: [items...]}``. Items without a
        category are grouped under the key ``"Uncategorized"`` inside their respective date.
    """
    main_topic_items = _get_items_with_highest_priority(ag)
    grouped_by_date: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for date, items in _group_agenda_items_by_planning_date(ag).items():
        logger.info(f"Grouping agenda items for date: {date}")
        categories_for_date: Dict[str, List[Dict[str, Any]]] = {}
        # Add main_topic_items key if item_type is "teksti" (kuvalupaus does not have main topics)
        if item_type == "teksti":
            # Check if the highest-priority items fall into this date bucket.
            main_topic_items_for_date = _select_main_topic_items_for_date(
                items, main_topic_items
            )
            if main_topic_items_for_date:
                categories_for_date["main_topic_items"] = main_topic_items_for_date
        for pl in items:
            category_name = get_category_from_agenda_item(pl) or "Uncategorized"
            categories_for_date.setdefault(category_name, []).append(pl)

        # Preferred category ordering
        preferred_order = [
            "Kotimaa",
            "Politiikka",
            "Talous",
            "Kulttuuri",
            "Ulkomaat",
            "Urheilu",
        ]
        ordered_categories: Dict[str, List[Dict[str, Any]]] = {}
        remaining = dict(categories_for_date)
        if "main_topic_items" in remaining:
            ordered_categories["main_topic_items"] = remaining.pop("main_topic_items")
        for category in preferred_order:
            if category in remaining:
                ordered_categories[category] = remaining.pop(category)
        for category in sorted(remaining.keys()):
            ordered_categories[category] = remaining[category]

        grouped_by_date[date] = ordered_categories
    # sort dates chronologically

    def _sort_key(key: str) -> datetime.datetime:
        try:
            return datetime.datetime.fromisoformat(key)
        except (ValueError, TypeError):
            # place undated entries at the end while keeping sort stable
            return datetime.datetime.max

    grouped_by_date = dict(
        sorted(
            grouped_by_date.items(),
            key=lambda item: _sort_key(item[0]),
        )
    )
    return grouped_by_date


def _get_items_with_highest_priority(
    ag: Dict[str, Any],
) -> List[Dict[str, Any]]:
    # if stt_priority_numeric is 3300, it is the highest priority
    highest_priority = 3300
    main_topic_items = []
    for pl in ag.get("items") or []:
        sort_value = pl.get("stt_priority_numeric_sort")
        if sort_value == highest_priority:
            main_topic_items.append(pl)
    return main_topic_items


def enrich_planning_agendas(
    agendas: List[Dict[str, Any]], item_type: str
) -> List[Dict[str, Any]]:
    """
    Enrich every planning agenda with the data required by the Lupaus / Kuvalupaus exports.

    The function:
    - drops draft agenda items
    - looks up related events in bulk (when IDs are present)
    - delegates to :func:`_set_stt_fields` to attach coverage metadata, priorities,
      chronologically sorted ``related_events_expanded`` values, grouped items,
      and main-topic selections

    Args:
        agendas: Source agendas that may contain ``items`` and related event
            references.
        item_type: The Lupaus flavour (``"teksti"`` or ``"kuva"``) which
            influences filtering rules.

    Returns:
        The same agenda list with each entry enriched in-place. Items that do
        not meet the Lupaus requirements are filtered out of their agendas.
    """
    for ag in agendas:
        # Exclude draft items
        items = exclude_drafts(ag.get("items") or [])
        # Exclude Merkkipäiväpalvelu items (anpa_category.qcode == "5")
        items = exclude_merkkipaivapalvelu_items(items)
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

    return agendas
