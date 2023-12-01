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

from pathlib import Path


ABS_PATH = str(Path(__file__).resolve().parent)

init_data = Path(ABS_PATH) / 'data'
if init_data.exists():
    INIT_DATA_PATH = init_data


RENDITIONS = {
    'picture': {
        'thumbnail': {'width': 220, 'height': 120},
        'viewImage': {'width': 640, 'height': 640},
        'baseImage': {'width': 1400, 'height': 1400},
    },
    'avatar': {
        'thumbnail': {'width': 60, 'height': 60},
        'viewImage': {'width': 200, 'height': 200},
    }
}

NO_TAKES = True

DEFAULT_TIMEZONE = "Europe/Helsinki"

SCHEMA = {
    'text': {
        'slugline': {},
        'headline': {},
        'language': {},
        'genre': {},
        'urgency': {},
        'priority': {},
        'anpa_category': {},
        'subject': {},
        'ednote': {},
        'abstract': {},
        'byline': {},
        'dateline': {},
        'body_html': {},
        'sign_off': {},
        'authors': {},
        'place': {},
        'usageterms': {},
        'keywords': {},
    }
}
QCODE_MISSING_VOC = "create"

INSTALLED_APPS = [
    'stt.parser',
    'stt.stt_events_ml',
    'stt.stt_planning_ml',
    'stt.signal_hooks',
    'planning',
    'apps.languages',
]

HTML_TAGS_WHITELIST = ('h1', 'h2', 'h3', 'h4', 'h6', 'blockquote', 'figure', 'ul', 'ol', 'li', 'div', 'p', 'em',
                       'strong', 'i', 'b', 'a', 'pre')
