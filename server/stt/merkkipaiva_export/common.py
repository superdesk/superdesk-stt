from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Formatted:
    rows: List[Dict[str, Any]]


def format_merkkipaiva_for_export(items):
    rows = items or []
    # TODO: sorting etc. if needed

    return {"rows": rows}
