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
