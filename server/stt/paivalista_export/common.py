from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Formatted:
    rows: List[Dict[str, Any]]


def include_only_mediatilaisuudet_items(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # include only items that have subject with "scheme": "event_type" and "qcode": "type21" ("Mediatilaisuudet")
    filtered_items = []
    for item in items:
        subjects = item.get("subject", [])
        for subject in subjects:
            if (
                subject.get("scheme") == "event_type"
                and subject.get("qcode") == "type21"
            ):
                filtered_items.append(item)
                break
    return filtered_items


def include_only_published_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # include only items in states that represent published events
    return [item for item in items if item.get("state") in ("scheduled", "rescheduled")]


def format_paivalista_for_export(items):
    rows = items or []
    rows = include_only_published_items(rows)
    rows = include_only_mediatilaisuudet_items(rows)

    return {"rows": rows}
