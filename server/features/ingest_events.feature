Feature: Ingest STT Event Items
    @auth
    @stt_cvs
    @stt_providers
    Scenario: Spikes draft ingested event on remove instruction
        When we fetch from "STTEventsML" ingest "events_ml_259431.xml"
        When we get "/events"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:259431",
            "state": "ingested"
        }]}
        """
        When we fetch from "STTEventsML" ingest "events_ml_259431_delete.xml"
        When we get "/events"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:259431",
            "state": "spiked"
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Unposts published ingested event on remove instruction
        When we fetch from "STTEventsML" ingest "events_ml_259431.xml"
        When we get "/events"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:259431",
            "state": "ingested"
        }]}
        """
        When we post to "/events/post"
        """
        {
            "event": "urn:newsml:stt.fi:259431",
            "etag": "#events._etag#",
            "pubstatus": "usable"
        }
        """
        Then we get OK response
        When we get "/published_planning?where={"item_id":"urn:newsml:stt.fi:259431"}"
        Then we get list with 1 items
        """
        {"_items": [{
            "published_item": {
                "state": "scheduled",
                "pubstatus": "usable"
            }
        }]}
        """
        When we fetch from "STTEventsML" ingest "events_ml_259431_delete.xml"
        When we get "/events"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:259431",
            "state": "killed"
        }]}
        """
        When we get "/published_planning?where={"item_id":"urn:newsml:stt.fi:259431"}"
        Then we get list with 2 items
        """
        {"_items": [{
            "published_item": {
                "state": "scheduled",
                "pubstatus": "usable"
            }
        }, {
            "published_item": {
                "state": "killed",
                "pubstatus": "cancelled"
            }
        }]}
        """
