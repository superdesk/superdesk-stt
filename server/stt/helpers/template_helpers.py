"""Shared template helper functions for STT."""

from typing import Dict, List, Any


def exclude_drafts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out dictionaries representing draft items.

    Args:
        items: A list of dictionaries where each dictionary describes an item and may contain a ``"state"`` key.

    Returns:
        A new list containing only the items whose ``"state"`` is not set to ``"draft"``.
    """
    filtered_items = [item for item in items if item.get("state") != "draft"]
    return filtered_items


def exclude_merkkipaivapalvelu_items(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Exclude items belonging to category qcode "5" (Merkkipäiväpalvelu).

    The function inspects the ``anpa_category`` field which is expected to be a list
    of dicts like ``{"qcode": "5", "name": "Merkkipäiväpalvelu"}``.

    Args:
        items: A list of item dictionaries.

    Returns:
        A new list excluding items where any ``anpa_category`` entry has
        ``qcode == "5"``.
    """

    filtered_items: List[Dict[str, Any]] = []
    for item in items:
        categories = item.get("anpa_category")
        if isinstance(categories, list) and any(
            isinstance(cat, dict) and cat.get("qcode") == "5" for cat in categories
        ):
            continue
        filtered_items.append(item)
    return filtered_items
