Feature: Ingest STT Planning items
    Background: Initial Setup
        Given empty "archive"
        And empty "ingest"
        And "desks"
        """
        [{
            "name": "Sports",
            "members": [{"user": "#CONTEXT_USER_ID#"}]
        }]
        """
        When we post to "/filter_conditions"
        """
        [{
            "name": "source-stt",
            "field": "source",
            "operator": "eq",
            "value": "stt"
        }]
        """
        Then we get OK response
        When we post to "/content_filters"
        """
        [{
            "name": "text-source-stt",
            "content_filter": [{"expression": {"fc": ["#filter_conditions._id#"]}}]
        }]
        """
        Then we get OK response
        When we post to "/routing_schemes"
        """
        [{
            "name": "publish content",
            "rules": [{
                "name": "STT Content",
                "handler": "desk_fetch_publish",
                "filter": "#content_filters._id#",
                "actions": {
                    "fetch": [],
                    "publish": [{
                        "desk": "#desks._id#",
                        "stage": "#desks.incoming_stage#"
                    }],
                    "exit": false
                }
            }]
        }]
        """
        Then we get OK response

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Ingest STT Planning item
        Given empty "ingest"
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:437036",
            "ednote": "Miten taistelut etenev\u00e4t? Millaisia kansainv\u00e4lisi\u00e4 reaktioita syntyy? Ent\u00e4 miten tilanne Ven\u00e4j\u00e4ll\u00e4 el\u00e4\u00e4? Seuraamme p\u00e4iv\u00e4n tapahtumia ja tarkennamme paketointia.",
            "ingest_provider": "#providers.sttplanningml#",
            "slugline": "Miten tilanne Ukrainan sodan ymp\u00e4rill\u00e4 ja Ukrainassa kehittyy?",
            "name": "Miten tilanne Ukrainan sodan ymp\u00e4rill\u00e4 ja Ukrainassa kehittyy?",
            "planning_date": "2022-03-30T00:00:00+0000",
            "source": "stt",
            "state": "ingested",
            "subject": [{
                "qcode": "14",
                "name": "Ulkomaat",
                "scheme": "sttdepartment"
            }],
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": "__empty__",
                "workflow_status": "draft",
                "news_coverage_status": {
                    "qcode": "ncostat:int",
                    "label": "Planned",
                    "name": "coverage intended"
                },
                "planning": {
                    "g2_content_type": "text",
                    "slugline": "UKRAINA // Y\u00f6n seurantaa",
                    "scheduled": "2022-03-30T00:00:00+0000",
                    "genre": [{
                        "qcode": "sttgenre:1",
                        "name": "P\u00e4\u00e4juttu"
                    }]
                }
            }, {
                "coverage_id": "ID_WORKREQUEST_159700",
                "assigned_to": "__empty__",
                "workflow_status": "draft",
                "news_coverage_status": {
                    "qcode": "ncostat:int",
                    "label": "Planned",
                    "name": "coverage intended"
                },
                "planning": {
                    "g2_content_type": "picture",
                    "slugline": "Miten tilanne Ukrainan sodan ymp\u00e4rill\u00e4 ja Ukrainassa kehittyy?",
                    "scheduled": "2022-03-30T00:00:00+0000",
                    "genre": [{
                        "qcode": "sttimage:27",
                        "name": "Kv. kuvaa"
                    }]
                }
            }]
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Link ingested coverages to content
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we get "/published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "__no_value__",
            "priority": 6,
            "task": {
                "desk": "#desks._id#",
                "stage": "#desks.incoming_stage#",
                "user": null
            }
        }]}
        """
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/assignments"
        Then we get list with 1 items
        """
        {"_items": [{
            "planning_item": "urn:newsml:stt.fi:437036",
            "coverage_item": "ID_TEXT_120123822",
            "priority": 6,
            "assigned_to": {
                "desk": "#desks._id#",
                "state": "completed"
            }
        }]}
        """
        Then we store "assignment" with first item
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": {
                    "assignment_id": "#assignment._id#",
                    "desk": "#desks._id#",
                    "user": null,
                    "state": "completed",
                    "priority": 6
                }
            }],
            "extra": {
                "stt_topics": "437036"
            }
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Link content to coverages on publish
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/assignments"
        Then we get list with 0 items
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": "__empty__"
            }],
            "extra": {
                "stt_topics": "437036"
            }
        }]}
        """
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we get "/assignments"
        Then we get list with 1 items
        """
        {"_items": [{
            "planning_item": "urn:newsml:stt.fi:437036",
            "coverage_item": "ID_TEXT_120123822",
            "priority": 6,
            "assigned_to": {
                "desk": "#desks._id#",
                "state": "completed"
            }
        }]}
        """
        Then we store "assignment" with first item
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": {
                    "assignment_id": "#assignment._id#",
                    "desk": "#desks._id#",
                    "user": null,
                    "state": "completed",
                    "priority": 6
                }
            }],
            "extra": {
                "stt_topics": "437036"
            }
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Spikes draft ingested planning on remove instruction
        When we fetch from "STTPlanningML" ingest "planning_ml_584717.xml"
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:584717",
            "state": "ingested"
        }]}
        """
        When we fetch from "STTPlanningML" ingest "planning_ml_584717_delete.xml"
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:584717",
            "state": "spiked"
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Unposts published ingested planning on remove instruction
        When we fetch from "STTPlanningML" ingest "planning_ml_584717.xml"
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:584717",
            "state": "ingested"
        }]}
        """
        When we post to "/planning/post"
        """
        {
            "planning": "urn:newsml:stt.fi:584717",
            "etag": "#planning._etag#",
            "pubstatus": "usable"
        }
        """
        Then we get OK response
        When we get "/published_planning?where={"item_id":"urn:newsml:stt.fi:584717"}"
        Then we get list with 1 items
        """
        {"_items": [{
            "published_item": {
                "state": "scheduled",
                "pubstatus": "usable"
            }
        }]}
        """
        When we fetch from "STTPlanningML" ingest "planning_ml_584717_delete.xml"
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "guid": "urn:newsml:stt.fi:584717",
            "state": "killed"
        }]}
        """
        When we get "/published_planning?where={"item_id":"urn:newsml:stt.fi:584717"}"
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

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Creates new coverage on content ingest
        # Ingest Planning with 0 coverages (1 placeholder)
        When we fetch from "STTPlanningML" ingest "planning_ml_before_link_content.xml"
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "assigned_to": "__empty__",
                "flags": {"placeholder": true}
            }]
        }]}
        """
        When we get "/assignments"
        Then we get list with 0 items
        # Ingest content
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content_with_topic_id.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we get "/assignments"
        Then we get list with 1 items
        """
        {"_items": [{
            "planning_item": "urn:newsml:stt.fi:437036",
            "coverage_item": "ID_TEXT_120123822",
            "priority": 6,
            "assigned_to": {
                "desk": "#desks._id#",
                "state": "completed"
            }
        }]}
        """
        Then we store "assignment" with first item
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": {
                    "assignment_id": "#assignment._id#",
                    "desk": "#desks._id#",
                    "user": null,
                    "state": "completed",
                    "priority": 6
                },
                "news_coverage_status": {"qcode": "ncostat:int", "name": "coverage intended"},
                "workflow_status": "active",
                "flags": {"placeholder": "__no_value__"},
                "planning": {
                    "g2_content_type": "text",
                    "scheduled": "2017-12-25T09:16:43+0000",
                    "slugline": "Parliament passed the Alcohol Act and the government gained confidence*** TRANSLATED ***",
                    "genre": [{"name": "P\u00e4\u00e4juttu", "qcode": "1"}],
                    "subject": [
                        {"name": "Politics", "qcode": "9", "scheme": "sttdepartment"},
                        {"name": "Pika+", "qcode": "1", "scheme": "sttversion"},
                        {"name": "Suomi", "qcode": "1", "scheme": "country"},
                        {"name": "Eurooppa", "qcode": "150", "scheme": "world_region"}
                    ]
                }
            }],
            "extra": {
                "stt_topics": "437036"
            }
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Groups content to a single coverage based on STT Article ID
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/assignments"
        Then we get list with 0 items
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{"coverage_id": "ID_TEXT_120123822"}]
        }]}
        """
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we get "/assignments"
        Then we get list with 1 items
        """
        {"_items": [{
            "planning_item": "urn:newsml:stt.fi:437036",
            "coverage_item": "ID_TEXT_120123822"
        }]}
        """
        Then we store "assignment_1" with first item
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": {"assignment_id": "#assignment_1._id#"}
            }]
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "#assignment_1._id#"
        }]}
        """
        And we store "content_1" with first item
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content_2.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we get "published"
        Then we get list with 2 items
        And we store "content_1" with 1 item
        And we store "content_2" with 2 item
        When we get "/assignments"
        Then we get list with 2 items
        """
        {"_items": [
            {
                "planning_item": "urn:newsml:stt.fi:437036",
                "coverage_item": "ID_TEXT_120123822",
                "item_ids": ["#content_1.guid#"]
            },
            {
                "planning_item": "urn:newsml:stt.fi:437036",
                "coverage_item": "ID_TEXT_120123822",
                "item_ids": ["#content_2.guid#"]
            }
        ]}
        """
        And we store "assignment_1" with 1 item
        And we store "assignment_2" with 2 item
        When we get "published"
        Then we get list with 2 items
        """
        {"_items": [
            {
                "uri": "urn:newsml:stt.fi:101801633",
                "assignment_id": "#assignment_1._id#"
            },
            {
                "uri": "urn:newsml:stt.fi:101801733",
                "assignment_id": "#assignment_2._id#"
            }
        ]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Unlinks content from planning on remove signal
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/assignments"
        Then we get list with 1 items
        Then we store "assignment" with first item
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "workflow_status": "active",
                "assigned_to": {
                    "assignment_id": "#assignment._id#",
                    "desk": "#desks._id#",
                    "user": null,
                    "state": "completed",
                    "priority": 6
                }
            }]
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content_delete.xml"
        When we get "/assignments"
        Then we get list with 0 items
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": "__empty__",
                "workflow_status": "draft"
            }]
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": null
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers
    Scenario: Unlinks content from event on remove signal
        When we fetch from "STTNewsML" ingest "stt_newsml_link_content.xml" using routing_scheme
        """
        #routing_schemes._id#
        """
        When we fetch from "STTEventsML" ingest "events_ml_259431.xml"
        When we fetch from "STTPlanningML" ingest "planning_ml_437036_link_content_and_event.xml"
        When we get "/assignments"
        Then we get list with 1 items
        Then we store "assignment" with first item
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "workflow_status": "active",
                "assigned_to": {
                    "assignment_id": "#assignment._id#",
                    "desk": "#desks._id#",
                    "user": null,
                    "state": "completed",
                    "priority": 6
                }
            }]
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """
        When we fetch from "STTEventsML" ingest "events_ml_259431_delete.xml"
        When we get "/assignments"
        Then we get list with 0 items
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:437036",
            "coverages": [{
                "coverage_id": "ID_TEXT_120123822",
                "assigned_to": "__empty__",
                "workflow_status": "draft"
            }]
        }]}
        """
        When we get "published"
        Then we get list with 1 items
        """
        {"_items": [{
            "uri": "urn:newsml:stt.fi:101801633",
            "assignment_id": null
        }]}
        """
