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
            "guid": "urn:newsml:stt.fi:20220330:437036",
            "ednote": "Miten taistelut etenev\u00e4t? Millaisia kansainv\u00e4lisi\u00e4 reaktioita syntyy? Ent\u00e4 miten tilanne Ven\u00e4j\u00e4ll\u00e4 el\u00e4\u00e4? Seuraamme p\u00e4iv\u00e4n tapahtumia ja tarkennamme paketointia.",
            "ingest_provider": "#providers.sttplanningml#",
            "slugline": "Miten tilanne Ukrainan sodan ymp\u00e4rill\u00e4 ja Ukrainassa kehittyy?",
            "name": "Miten tilanne Ukrainan sodan ymp\u00e4rill\u00e4 ja Ukrainassa kehittyy?",
            "planning_date": "2022-03-29T21:00:00+0000",
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
                    "scheduled": "2022-03-29T21:00:00+0000",
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
                    "scheduled": "2022-03-29T21:00:00+0000",
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
            "uri": "urn:newsml:stt.fi:20171219:101801633",
            "assignment_id": "__no_value__",
            "priority": 6,
            "task": {
                "desk": "#desks._id#",
                "stage": "#desks.incoming_stage#",
                "user": null
            },
            "extra": {
                "stt_topics": "437036"
            }
        }]}
        """
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/assignments"
        Then we get list with 1 items
        """
        {"_items": [{
            "planning_item": "urn:newsml:stt.fi:20220330:437036",
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
            "_id": "urn:newsml:stt.fi:20220330:437036",
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
            "uri": "urn:newsml:stt.fi:20171219:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """

    @auth
    @stt_cvs
    @stt_providers @wip
    Scenario: Link content to coverages on publish
        When we fetch from "STTPlanningML" ingest "planning_ml_link_content.xml"
        When we get "/assignments"
        Then we get list with 0 items
        When we get "/planning"
        Then we get list with 1 items
        """
        {"_items": [{
            "_id": "urn:newsml:stt.fi:20220330:437036",
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
            "planning_item": "urn:newsml:stt.fi:20220330:437036",
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
            "_id": "urn:newsml:stt.fi:20220330:437036",
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
            "uri": "urn:newsml:stt.fi:20171219:101801633",
            "assignment_id": "#assignment._id#"
        }]}
        """
