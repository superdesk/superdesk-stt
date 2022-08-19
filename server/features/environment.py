# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from typing import Dict, Any
from os import path

from superdesk import get_resource_service, etree
from superdesk.tests.environment import before_feature, before_step, after_scenario   # noqa
from superdesk.tests.environment import setup_before_all, setup_before_scenario
from superdesk.io.commands.update_ingest import ingest_items
from superdesk.io.feeding_services.file_service import FileFeedingService
from apps.prepopulate.app_populate import AppPopulateCommand

from app import get_app
from settings import INSTALLED_APPS


def before_all(context):
    config = {
        'INSTALLED_APPS': INSTALLED_APPS,
        'ELASTICSEARCH_FORCE_REFRESH': True,
    }
    setup_before_all(context, config, app_factory=get_app)


def before_scenario(context, scenario):
    config = {
        'INSTALLED_APPS': INSTALLED_APPS,
        'ELASTICSEARCH_FORCE_REFRESH': True,
    }
    setup_before_scenario(context, scenario, config, app_factory=get_app)

    if 'stt_providers' in scenario.tags:
        setup_stt_providers(context)

    if 'stt_cvs' in scenario.tags:
        with context.app.app_context():
            cmd = AppPopulateCommand()
            filename = path.join(path.abspath(path.dirname("data/")), "vocabularies.json")
            cmd.run(filename)


def _construct_file_ingest_provider(name: str, parser: str) -> Dict[str, Any]:
    path_to_fixtures = path.join(path.abspath(path.dirname(__file__)), "../tests/fixtures")

    return {
        "name": name,
        "source": "stt",
        "feeding_service": "file",
        "feed_parser": parser,
        "is_closed": False,
        "critical_errors": {"2005": True},
        "config": {"path": path_to_fixtures},
    }


def mock_fetch_ingest(self: FileFeedingService, guid: str):
    path_to_fixtures = path.join(path.abspath(path.dirname(__file__)), "../tests/fixtures")
    file_path = path.join(path_to_fixtures, guid)
    feeding_parser = self.get_feed_parser(self.provider)

    with open(file_path, "rb") as f:
        xml_string = etree.etree.fromstring(f.read())
        return feeding_parser.parse(xml_string, self.provider)


def setup_stt_providers(context):
    app = context.app
    context.providers = {}
    context.ingest_items = ingest_items
    FileFeedingService.fetch_ingest = mock_fetch_ingest
    with app.test_request_context(app.config["URL_PREFIX"]):
        providers = [
            _construct_file_ingest_provider("STTNewsML", "sttnewsmlnewsroom"),
            _construct_file_ingest_provider("STTEventsML", "stteventsml"),
            _construct_file_ingest_provider("STTPlanningML", "sttplanningml"),
        ]

        result = get_resource_service("ingest_providers").post(providers)
        context.providers["sttnewsmlnewsroom"] = result[0]
        context.providers["stteventsml"] = result[1]
        context.providers["sttplanningml"] = result[2]
