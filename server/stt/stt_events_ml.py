from typing import Optional, Dict, Any, TypedDict

import logging
from xml.etree.ElementTree import Element
from bson import ObjectId

from superdesk import get_resource_service
from superdesk.utc import local_to_utc
from superdesk.io.registry import register_feed_parser
from superdesk.text_utils import plain_text_to_html
from superdesk.errors import SuperdeskApiError
from planning.feed_parsers.events_ml import EventsMLParser

from .common import (
    planning_xml_contains_remove_signal,
    unpost_or_spike_event_or_planning,
    remove_date_portion_from_id,
    original_item_exists,
)

logger = logging.getLogger(__name__)
TIMEZONE = "Europe/Helsinki"

NS = {
    "stt": "http://www.stt-lehtikuva.fi/NewsML",
}


class ContactPhone(TypedDict):
    number: str
    public: bool


class ContactDetails(TypedDict, total=False):
    public: bool
    is_active: bool
    first_name: str
    last_name: str
    job_title: str
    organisation: str
    contact_phone: list[ContactPhone]
    contact_email: list[str]
    website: str


def search_existing_contacts(contact: ContactDetails) -> Optional[Dict[str, Any]]:
    """Attempt to find existing media contact using email, falling back to first_name/last_name combo"""

    contacts_service = get_resource_service("contacts")
    if len(contact.get("contact_email") or []):
        cursor = contacts_service.search(
            {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "contact_email.keyword": contact["contact_email"][0]
                                }
                            }
                        ]
                    }
                }
            }
        )
        if cursor.count():
            return list(cursor)[0]

    if contact.get("first_name") and contact.get("last_name"):
        first_name = contact["first_name"].lower()
        last_name = contact["last_name"].lower()

        cursor = contacts_service.search(
            {
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
                "sort": ["_score"],
            }
        )
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
        return (
            item_id
            if original_item_exists("events", item_id)
            else remove_date_portion_from_id(item_id)
        )

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
                qcode = (
                    f"type{qcode}"  # add prefix to avoid conflict with sttdepartment
                )
                name = self.getVocabulary(
                    "event_type", qcode, related.find(self.qname("name")).text
                )
                item.setdefault("subject", []).append(
                    {
                        "qcode": qcode,
                        "name": name,
                        "scheme": "event_type",
                    }
                )
        except AttributeError:
            pass

        self.set_location_details(
            item, event_details.find(self.qname("location")), location_notes
        )
        self.set_contact_details(item, event_details)

    def _construct_unique_name(self, parts):
        """Helper to construct a unique name from non-empty parts."""
        return ", ".join(part for part in parts if part)

    def set_location_details(self, item, location_xml, notes):
        """Set location details from XML, including name, address title, and a unique_name combining name, city, and country."""
        if location_xml is None:
            return

        location = {"address": {"extra": {}}}

        if notes is not None:
            location["details"] = notes

        try:
            poi_name_el = location_xml.find(self.qname("name"))
            poi_name = poi_name_el.text if poi_name_el is not None else None
            location["name"] = poi_name
            poi_details = location_xml.find(self.qname("POIDetails"))
            address_xml = (
                poi_details.find(self.qname("address"))
                if poi_details is not None
                else None
            )

            city = None
            country = None

            if address_xml is not None:
                locality = address_xml.find(self.qname("locality"))
                if locality is not None:
                    city_name = locality.find(self.qname("name"))
                    city = city_name.text if city_name is not None else None

                country_el = address_xml.find(self.qname("country"))
                if country_el is not None:
                    country_name = country_el.find(self.qname("name"))
                    country = country_name.text if country_name is not None else None
            location["unique_name"] = self._construct_unique_name(
                [poi_name, city, country]
            )
            location["address"]["title"] = poi_name
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
                    location["address"]["country"] = broader.find(
                        self.qname("name")
                    ).text
                    location["address"]["extra"]["iso3166"] = broader.find(
                        self.qname("sameAs")
                    ).get("qcode")
                except AttributeError:
                    continue

        try:
            address = location_xml.find(self.qname("POIDetails")).find(
                self.qname("address")
            )
        except AttributeError:
            address = None

        if address is not None:
            try:
                location["address"]["line"] = [address.find(self.qname("line")).text]
            except AttributeError:
                pass

            try:
                location["address"]["postal_code"] = address.find(
                    self.qname("postalCode")
                ).text
            except AttributeError:
                pass

        # Save location to database if it doesn't exist
        locations_service = get_resource_service("locations")
        if locations_service is not None:
            try:
                stt_id = (
                    location.get("address", {}).get("extra", {}).get("sttlocationalias")
                )

                if stt_id:
                    custom_guid = f"urn:stt:location:{stt_id}"
                    location["qcode"] = custom_guid
                    existing_location = locations_service.find_one(
                        req=None, guid=custom_guid
                    )

                    if existing_location:
                        updated_location = {**existing_location, **location}
                        location_id = existing_location["_id"]
                        locations_service.update(
                            location_id, updated_location, existing_location
                        )
                        saved_location = locations_service.find_one(
                            req=None, _id=location_id
                        )
                        saved_location["qcode"] = custom_guid
                    else:
                        location["guid"] = custom_guid
                        location_ids = locations_service.post([location])
                        saved_location = locations_service.find_one(
                            req=None, _id=location_ids[0]
                        )
                        if saved_location:
                            saved_location["qcode"] = custom_guid
                    item["location"] = [saved_location]
                else:
                    item["location"] = [location]

            except AttributeError:
                pass

    def set_contact_details(self, item: Dict[str, Any], event_details: Element):
        for contact_info in event_details.findall(self.qname("contactInfo")):
            first_name = contact_info.find(self.qname("firstname", ns=NS["stt"]))
            last_name = contact_info.find(self.qname("lastname", ns=NS["stt"]))
            job_title = contact_info.find(self.qname("title", ns=NS["stt"]))
            phone = contact_info.find(self.qname("phone"))
            organization = contact_info.find(self.qname("organization", ns=NS["stt"]))
            email = contact_info.find(self.qname("email"))
            web = contact_info.find(self.qname("web"))

            contact: ContactDetails = {
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
                contact["contact_phone"] = [
                    {
                        "number": phone.text,
                        "public": True,
                    }
                ]
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
