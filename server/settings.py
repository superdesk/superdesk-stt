#!/usr/bin/env python
# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014, 2015 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import os
from pathlib import Path


def env(variable, fallback_value=None):
    env_value = os.environ.get(variable, "")
    if len(env_value) == 0:
        return fallback_value
    else:
        if env_value == "__EMPTY__":
            return ""
        else:
            return env_value


ABS_PATH = str(Path(__file__).resolve().parent)

init_data = Path(ABS_PATH) / "data"
if init_data.exists():
    INIT_DATA_PATH = init_data

LOCATORS_DATA_FILE = os.path.join(ABS_PATH, "data", "locators.json")


RENDITIONS = {
    "picture": {
        "thumbnail": {"width": 220, "height": 120},
        "viewImage": {"width": 640, "height": 640},
        "baseImage": {"width": 1400, "height": 1400},
    },
    "avatar": {
        "thumbnail": {"width": 60, "height": 60},
        "viewImage": {"width": 200, "height": 200},
    },
}

WS_HOST = env("WSHOST", "0.0.0.0")
WS_PORT = env("WSPORT", "5100")

LOG_CONFIG_FILE = env("LOG_CONFIG_FILE", "logging_config.yml")

REDIS_URL = env("REDIS_URL", "redis://localhost:6379")
if env("REDIS_PORT"):
    REDIS_URL = env("REDIS_PORT").replace("tcp:", "redis:")
BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)

SECRET_KEY = env("SECRET_KEY", "")

STT_FIN_API_KEY = env("STT_FIN_API_KEY", "")
STT_FIN_API_URL = env("STT_FIN_API_URL", "")
GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON = env(
    "GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON", ""
)
GOOGLE_CLOUD_TRANSLATE_PROJECT_ID = env("GOOGLE_CLOUD_TRANSLATE_PROJECT_ID", "")
STT_AI_URL = env("STT_AI_URL", "")

# disable takes
NO_TAKES = True

# default timezone
DEFAULT_TIMEZONE = "Europe/Helsinki"

# which day is start of week
START_OF_WEEK = 1

# pagination
PAGINATION_LIMIT = 500
PAGINATION_DEFAULT = PAGINATION_LIMIT

# default language
DEFAULT_LANGUAGE = "fi"

# Default value for Source for manually created items
DEFAULT_SOURCE_VALUE_FOR_MANUAL_ARTICLES = "STT"

# default urgency for ingested content
INGEST_DEFAULT_URGENCY = 3

# enable high priority queue
HIGH_PRIORITY_QUEUE_ENABLED = True

# Generating short GUID for items
GENERATE_SHORT_GUID = True

# This value gets injected into NewsML 1.2 and G2 output documents.
NEWSML_PROVIDER_ID = "STT"
ORGANIZATION_NAME = env("ORGANIZATION_NAME", "STT")
ORGANIZATION_NAME_ABBREVIATION = env("ORGANIZATION_NAME_ABBREVIATION", "STT")

SCHEMA = {
    "text": {
        "slugline": {},
        "headline": {},
        "language": {},
        "genre": {},
        "urgency": {},
        "priority": {},
        "anpa_category": {},
        "subject": {},
        "ednote": {},
        "abstract": {},
        "byline": {},
        "dateline": {},
        "body_html": {},
        "sign_off": {},
        "authors": {},
        "place": {},
        "usageterms": {},
        "keywords": {},
    }
}  # type: dict[str, dict]

# add missing item in CVs on ingest
QCODE_MISSING_VOC = "create"

INSTALLED_APPS = [
    "stt.parser",
    "stt.parser_bns",
    "stt.parser_afp",
    "stt.parser_hippos",
    "stt.stt_tt_ninjs",
    "stt.stt_events_ml",
    "stt.stt_planning_ml",
    "stt.stt_info_porssi",
    "stt.stt_parse_lottery_veikkaus",
    "stt.signal_hooks",
    "stt.stt_parse_businesswire",
    "planning",
    "analytics",
    "apps.languages",
    "stt.spellcheckers.stt_fin",
    "stt.macros",
    "stt.search_providers.newshub",
    "stt.ai_proxy",
    "stt.stt_ntb_ninjs_parse",
    "stt.template_filters",
    "stt.paivalista_export",
    "stt.lupaus_export",
    "stt.io.feed_parsers.stt_events_csv_parse",
]

# enable legal archive is enabled
LEGAL_ARCHIVE = True

# EXPIRY

# expiry of content in production
CONTENT_EXPIRY_MINUTES = 43200

# expiry of spiked content. If unspecified, Desk expiry value is used
SPIKE_EXPIRY_MINUTES = int(env("SPIKE_EXPIRY_MINUTES", 3 * 24 * 60))

# Expire items 3 days after their scheduled date. Defaults to 0 = disabled
PLANNING_EXPIRY_MINUTES = int(env("PLANNING_EXPIRY_MINUTES", 4320))

# Delete spiked events/plannings after their scheduled date. Defaults to 0 = disabled
PLANNING_DELETE_SPIKED_MINUTES = int(env("PLANNING_DELETE_SPIKED_MINUTES", 1440))

#: The number of minutes before Publish Queue is purged
PUBLISH_QUEUE_EXPIRY_MINUTES = int(env("PUBLISH_QUEUE_EXPIRY_MINUTES", 3 * 24 * 60))

#: The number of minutes since the last update of the Mongo auth object after which it will be deleted
SESSION_EXPIRY_MINUTES = int(env("SESSION_EXPIRY_MINUTES", 740))

#: The number of minutes before ingest items are purged (3 days)
INGEST_EXPIRY_MINUTES = int(env("INGEST_EXPIRY_MINUTES", 3 * 24 * 60))

#: The number of minutes before audit content is purged
AUDIT_EXPIRY_MINUTES = int(env("AUDIT_EXPIRY_MINUTES", 43200))

#: The number records to be fetched for expiry.
MAX_EXPIRY_QUERY_LIMIT = int(env("MAX_EXPIRY_QUERY_LIMIT", 1000))

# HTML_TAGS_WHITELIST = ('h1', 'h2', 'h3', 'h4', 'h6', 'blockquote', 'figure', 'ul', 'ol', 'li', 'div', 'p', 'em', 'strong', 'i', 'b', 'a', 'pre')

# Disallowed characters for text fields (validation needs to be enabled in content profile)
# DISALLOWED_CHARACTERS = ['!', '#', '$', '%', '&', '"', '(', ')', '*', '+', ',', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', ']', '\\', '^', '_', '`', '{', '|', '}', '~']

# AUTHORING CONFIG

# allow non-desk members to duplicate content
WORKFLOW_ALLOW_DUPLICATE_TO_NON_MEMBERS = True

# enable slugline autocompletion
ARCHIVE_AUTOCOMPLETE = True
# display published slugs from the last X days
ARCHIVE_AUTOCOMPLETE_DAYS = 7
# max number of autocomplete items
ARCHIVE_AUTOCOMPLETE_LIMIT = 1000

# enable adding new keywords to a keywords CV on publishing
KEYWORDS_ADD_MISSING_ON_PUBLISH = True

# enable updating of an unpublished update
WORKFLOW_ALLOW_MULTIPLE_UPDATES = True

# enable automatic publishing of associated items (images, videos, audios) with a story
PUBLISH_ASSOCIATED_ITEMS = False

# enable corrections workflow = corrections can be sent to desks before "send correction"/publish action
CORRECTIONS_WORKFLOW = True

# PLANNING CONFIG

# fields to be inherited between events and planning
SYNC_EVENT_FIELDS_TO_PLANNING = [
    "slugline",
    "name",
    "ednote",
    "internal_note",
    "language",
    "definition_short",
]

# enable closing popup editor after clicking on "create" button / Defaults to true
PLANNING_AUTO_CLOSE_POPUP_EDITOR = True

# ???
DEFAULT_CREATE_PLANNING_SERIES_WITH_EVENT_SERIES = True

# allow scheduled updates in planning
PLANNING_ALLOW_SCHEDULED_UPDATES = env("PLANNING_ALLOW_SCHEDULED_UPDATES", "false")

# max number of events created in a recurring series / default = 200
MAX_RECURRENT_EVENTS = 200

# base URL for map link from planning / Defaults to https://www.google.com.au/maps/?q=
STREET_MAP_URL = "https://www.google.fi/maps/?q="

# maximum number of days a single event can span.
# MAX_MULTI_DAY_EVENT_DURATION = int(env('MAX_MULTI_DAY_EVENT_DURATION', 7))

# enable event templates
PLANNING_EVENT_TEMPLATES_ENABLED = env("PLANNING_EVENT_TEMPLATES_ENABLED", "true")

# Template for export events as articles that overwrites default template
# default: https://github.com/superdesk/superdesk-planning/blob/develop/server/planning/planning_export_templates.py
# EVENT_EXPORT_BODY_TEMPLATE

# Template for export plannings as articles that overwrites default template
# PLANNING_EXPORT_BODY_TEMPLATE

# duration of of long event ??? Defaults to -1 = disabled
# LONG_EVENT_DURATION_THRESHOLD

# ASSIGNMENTS CONFIG

# Enable or disable the fulfill assignments task
ENABLE_FULFILL_ASSIGNMENTS = env("ENABLE_FULFILL_ASSIGNMENTS", "true")

# automatically add coverage assignments to workflow
PLANNING_AUTO_ASSIGN_TO_WORKFLOW = env("PLANNING_AUTO_ASSIGN_TO_WORKFLOW", "true")

# check for unfulfilled assignments when publishing a story (based on slugline)
PLANNING_CHECK_FOR_ASSIGNMENT_ON_PUBLISH = env(
    "PLANNING_CHECK_FOR_ASSIGNMENT_ON_PUBLISH", "false"
)

# check for unfulfilled assignments when sending a story from an authoring to production desk (based on slugline)
PLANNING_CHECK_FOR_ASSIGNMENT_ON_SEND = env(
    "PLANNING_CHECK_FOR_ASSIGNMENT_ON_SEND", "true"
)

# link updates to coverages
PLANNING_LINK_UPDATES_TO_COVERAGES = env("PLANNING_LINK_UPDATES_TO_COVERAGES", "false")

# Desk IDs to display fulfil challenge on publish (requires PLANNING_CHECK_FOR_ASSIGNMENT_ON_PUBLISH=true)
PLANNING_FULFIL_ON_PUBLISH_FOR_DESKS = env(
    "PLANNING_FULFIL_ON_PUBLISH_FOR_DESKS",
    "54e68fcd1024542de76d6643,"  # News
    "54e691ca1024542de640fef1,"  # Finance
    "54e6928d1024542de640fef5,"  # Sport
    "5768dd55a5398f5efb985e19,"  # World News
    "5768ddc2a5398f5efa2cda65,"  # News Extra
    "57b0f07ea5398f41862b951e",  # Court Production
)

# XMP

# use XMP for picture assignments
PLANNING_USE_XMP_FOR_PIC_ASSIGNMENTS = env(
    "PLANNING_USE_XMP_FOR_PIC_ASSIGNMENTS", "true"
)

# use XMP for picture slugline
PLANNING_USE_XMP_FOR_PIC_SLUGLINE = env("PLANNING_USE_XMP_FOR_PIC_SLUGLINE", "true")

# XMP slugline mapping ???
PLANNING_XMP_SLUGLINE_MAPPING = {
    "xpath": "//x:xmpmeta/rdf:RDF/rdf:Description/dc:title/rdf:Alt/rdf:li",
    "namespaces": {
        "x": "adobe:ns:meta/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "photoshop": "http://ns.adobe.com/photoshop/1.0/",
        "dc": "http://purl.org/dc/elements/1.1/",
    },
}

# XMP assignment mapping ???
PLANNING_XMP_ASSIGNMENT_MAPPING = {
    "xpath": "//x:xmpmeta/rdf:RDF/rdf:Description",
    "namespaces": {
        "x": "adobe:ns:meta/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    },
    "atribute_key": "{http://ns.adobe.com/photoshop/1.0/}TransmissionReference",
}

# ANALYTICS MODULE

# Highcharts Export Server - default settings
ANALYTICS_ENABLE_SCHEDULED_REPORTS = env("ANALYTICS_ENABLE_SCHEDULED_REPORTS", "true")

ANALYTICS_ENABLE_ARCHIVE_STATS = env("ANALYTICS_ENABLE_ARCHIVE_STATS", "true")

HIGHCHARTS_SERVER_HOST = env("HIGHCHARTS_SERVER_HOST", "localhost")
HIGHCHARTS_SERVER_PORT = env("HIGHCHARTS_SERVER_PORT", "6060")
HIGHCHARTS_SERVER_WORKERS = env("HIGHCHARTS_SERVER_WORKERS", None)
HIGHCHARTS_SERVER_WORK_LIMIT = env("HIGHCHARTS_SERVER_WORK_LIMIT", None)
HIGHCHARTS_SERVER_LOG_LEVEL = env("HIGHCHARTS_SERVER_LOG_LEVEL", None)
HIGHCHARTS_SERVER_QUEUE_SIZE = env("HIGHCHARTS_SERVER_QUEUE_SIZE", None)
HIGHCHARTS_SERVER_RATE_LIMIT = env("HIGHCHARTS_SERVER_RATE_LIMIT", None)

PLANNING_EVENT_LINK_METHOD = "many_secondary"

PLANNING_PLANNING_ALL_DAY = True
