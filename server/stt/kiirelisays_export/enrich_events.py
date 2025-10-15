from dataclasses import dataclass
from typing import Any, Dict, List
from stt.helpers.mongo_helpers import find_many

import logging

logger = logging.getLogger(__name__)


@dataclass
class Formatted:
    rows: List[Dict[str, Any]]


def _get_contact_by_id(id):
    contacts = find_many(
        "contacts",
        {"_id": id},
    )
    return contacts[0] if contacts else None


def _find_contacts_for_event(event_id):
    event_from_mongo = find_many(
        "events",
        {
            "_id": event_id,
        },
        projection={"event_contact_info": 1, "_id": 0},
    )
    return event_from_mongo[0]["event_contact_info"] if event_from_mongo else None


def row_has_contacts(row):
    return "contacts" in row and row["contacts"] and len(row["contacts"]) > 0


def format_kiirelisays_for_export(items):
    rows = items or []
    for item in rows:
        # check if item has contacts
        if row_has_contacts(item):
            # return item as is
            continue
        # if not, try to find contacts from event
        event_id = item.get("_id")
        if event_id:
            contacts = _find_contacts_for_event(event_id)
            if contacts:
                enriched_contacts = []
                for contact_id in contacts:
                    if contact_id:
                        full_contact = _get_contact_by_id(contact_id)
                        if full_contact:
                            enriched_contacts.append(full_contact)
                if enriched_contacts:
                    item["contacts"] = enriched_contacts
                    logger.info(
                        f"Enriched item {item.get('_id')} with contacts from event {event_id}"
                    )
                else:
                    logger.warning(
                        f"No full contacts found for item {item.get('_id')} from event {event_id}"
                    )
            else:
                logger.warning(
                    f"No contacts found for event {event_id} for item {item.get('_id')}"
                )

    return {"rows": rows}
