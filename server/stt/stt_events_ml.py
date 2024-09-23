from typing import Optional, Dict, Any

import logging
from xml.etree.ElementTree import Element
from bson import ObjectId

from superdesk import get_resource_service
from superdesk.utc import local_to_utc
from superdesk.io.registry import register_feed_parser
from superdesk.text_utils import plain_text_to_html
from superdesk.errors import SuperdeskApiError
from planning.feed_parsers.events_ml import EventsMLParser

from .common import planning_xml_contains_remove_signal, unpost_or_spike_event_or_planning, \
    remove_date_portion_from_id, original_item_exists

logger = logging.getLogger(__name__)
TIMEZONE = "Europe/Helsinki"

NS = {
    "stt": "http://www.stt-lehtikuva.fi/NewsML",
}


def search_existing_contacts(contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Attempt to find existing media contact using email, falling back to first_name/last_name combo"""

    contacts_service = get_resource_service("contacts")
    if len(contact.get("contact_email") or []):
        cursor = contacts_service.search(
            {"query": {"bool": {"must": [{"term": {"contact_email.keyword": contact["contact_email"][0]}}]}}}
        )
        if cursor.count():
            return list(cursor)[0]

    if contact.get("first_name") and contact.get("last_name"):
        first_name = contact["first_name"].lower()
        last_name = contact["last_name"].lower()

        cursor = contacts_service.search({
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "first_name": {
                                    "query": first_name.lower(),
                                    "operator": "AND",
                                },
                            },
                        },
                        {
                            "match": {
                                "last_name": {
                                    "query": last_name.lower(),
                                    "operator": "AND",
                                },
                            },
                        },
                    ],
                },
            },
            "sort": ["_score"]
        })
        if cursor.count():
            return list(cursor)[0]

    return None


class STTEventsMLParser(EventsMLParser):
    NAME = "stteventsml"
    label = "STT Events ML"

    SUBJ_QCODE_PREFIXES = {
        "stt-subj": None,
        "sttdepartment": "sttdepartment",
        "sttsubj": "sttsubj",
    }

    def get_item_id(self, tree: Element) -> str:
        item_id = super(STTEventsMLParser, self).get_item_id(tree)
        return item_id if original_item_exists("events", item_id) else remove_date_portion_from_id(item_id)

    def parse(self, tree: Element, provider=None):
        items = super(STTEventsMLParser, self).parse(tree, provider)
        items_to_ingest = []
        for item in items:
            if planning_xml_contains_remove_signal(tree):
                unpost_or_spike_event_or_planning(item)
                # If the item contains the ``sttinstruct:remove`` signal, no need to ingest this one
                continue
            self.set_extra_fields(item, tree)
            items_to_ingest.append(item)

        return items_to_ingest

    def datetime(self, value):
        """When there is no timezone info, assume it's Helsinki timezone."""
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

    def set_extra_fields(self, item, xml):
        """Adds extra fields"""

        concept = xml.find(self.qname("concept"))

        # Add ``sttevents``, if one found
        try:
            values = concept.find(self.qname("conceptId")).get("qcode", "").split(":")
            if values and values[0] == "sttevents":
                item.setdefault("extra", {})["stt_events"] = values[1]
        except AttributeError:
            pass

        location_notes = None
        for note in concept.findall(self.qname("note")):
            if not note.text:
                continue

            role = note.get("role")
            if role == "sttdescription:eventinv":
                item["invitation_details"] = plain_text_to_html(note.text)
            elif role == "sttdescription:eventloc":
                location_notes = note.text

        event_details = concept.find(self.qname("eventDetails"))

        # Add ``stt-topics``, if one found
        try:
            for subject in event_details.findall(self.qname("subject")):
                values = subject.get("qcode", "").split(":")
                if values and values[0] == "stt-topics":
                    item.setdefault("extra", {})["stt_topics"] = values[1]
        except AttributeError:
            pass

        # Add `sttEventType` if found to subject[scheme=event_type]
        try:
            related = concept.find(self.qname("related"))

            if related is not None and related.get("rel", "") == "sttnat:sttEventType":
                qcode_parts = related.get("qcode", "").split(":")
                qcode = qcode_parts[1] if len(qcode_parts) == 2 else qcode_parts
                qcode = f"type{qcode}"  # add prefix to avoid conflict with sttdepartment
                name = self.getVocabulary("event_type", qcode, related.find(self.qname("name")).text)
                item.setdefault("subject", []).append({
                    "qcode": qcode,
                    "name": name,
                    "scheme": "event_type",
                })
        except AttributeError:
            pass

        self.set_location_details(item, event_details.find(self.qname("location")), location_notes)
        self.set_contact_details(item, event_details)

    def set_location_details(self, item, location_xml, notes):
        """Add Location information, if found"""
        if location_xml is None:
            return

        location = {"address": {"extra": {}}}

        if notes is not None:
            location["details"] = [notes]

        try:
            name = location_xml.find(self.qname("name")).text
            location["name"] = name
            location["address"]["title"] = name
        except AttributeError:
            pass

        try:
            sttlocationalias = location_xml.get("qcode").split("sttlocationalias:")[1]
            location["address"]["extra"]["sttlocationalias"] = sttlocationalias
        except AttributeError:
            pass

        for broader in location_xml.findall(self.qname("broader")):
            values = broader.get("qcode", "").split(":")
            if len(values) != 2 or not values[0].startswith("stt"):
                continue
            elif values[0] == "sttcity":
                location["address"]["extra"]["sttcity"] = values[1]

                try:
                    location["address"]["city"] = broader.find(self.qname("name")).text
                except AttributeError:
                    continue
            elif values[0] == "sttstate":
                location["address"]["extra"]["sttstate"] = values[1]
                try:
                    location["address"]["state"] = broader.find(self.qname("name")).text
                except AttributeError:
                    continue
            elif values[0] == "sttcountry":
                location["address"]["extra"]["sttcountry"] = values[1]
                try:
                    location["address"]["country"] = broader.find(self.qname("name")).text
                    location["address"]["extra"]["iso3166"] = broader.find(self.qname("sameAs")).get("qcode")
                except AttributeError:
                    continue

        try:
            address = location_xml.find(self.qname("POIDetails")).find(self.qname("address"))
        except AttributeError:
            address = None

        if address is not None:
            try:
                location["address"]["line"] = [address.find(self.qname("line")).text]
            except AttributeError:
                pass

            try:
                location["address"]["postal_code"] = address.find(self.qname("postalCode")).text
            except AttributeError:
                pass

        item["location"] = [location]

    def set_contact_details(self, item: Dict[str, Any], event_details: Element):
        for contact_info in event_details.findall(self.qname("contactInfo")):
            first_name = contact_info.find(self.qname("firstname", ns=NS["stt"]))
            last_name = contact_info.find(self.qname("lastname", ns=NS["stt"]))
            job_title = contact_info.find(self.qname("title", ns=NS["stt"]))
            phone = contact_info.find(self.qname("phone"))
            organization = contact_info.find(self.qname("organization", ns=NS["stt"])) 
            email = contact_info.find(self.qname("email"))
            web = contact_info.find(self.qname("web"))

            contact = {
                "is_active": True,
                "public": True,
            }

            if first_name is not None and first_name.text:
                contact["first_name"] = first_name.text
            if last_name is not None and last_name.text:
                contact["last_name"] = last_name.text
            if job_title is not None and job_title.text:
                contact["job_title"] = job_title.text
            if organization is not None and organization.text: 
                contact["organisation"] = organization.text    
            if phone is not None and phone.text:
                contact["contact_phone"] = [{
                    "number": phone.text,
                    "public": True,
                }]
            if email is not None and email.text:
                contact["contact_email"] = [email.text.lower()]
            if web is not None and web.text:
                contact["website"] = web.text

            try:
                existing_contact = search_existing_contacts(contact)
                item.setdefault("event_contact_info", [])
                if existing_contact is not None:
                    item["event_contact_info"].append(ObjectId(existing_contact["_id"]))
                else:
                    new_contact_id = get_resource_service("contacts").post([contact])[0]
                    item["event_contact_info"].append(new_contact_id)
            except SuperdeskApiError:
                logger.exception("Skip linking contact to ingested Event, as it failed")


register_feed_parser(STTEventsMLParser.NAME, STTEventsMLParser())
