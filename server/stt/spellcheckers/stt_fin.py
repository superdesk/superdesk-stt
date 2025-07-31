# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013-2019 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import os
import logging

import aiohttp

from superdesk.errors import SuperdeskApiError
from superdesk.text_checkers.spellcheckers import CAP_SPELLING
from superdesk.text_checkers.spellcheckers.base import SpellcheckerBase

logger = logging.getLogger(__name__)
OPT_API_KEY = "STT_FIN_API_KEY"
OPT_API_URL_KEY = "STT_FIN_API_URL"

CHECK_TIMEOUT = aiohttp.ClientTimeout(total=5, connect=3)
SUGGEST_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=3)


class SttFin(SpellcheckerBase):
    """STT grammar/spellchecker integration

    The STT_FIN_API_KEY setting (or environment variable) must be set to the API key
    """

    name = "stt_fin"
    label = "STT Spellchecker"
    capacities = (CAP_SPELLING,)
    languages = ["fi"]

    def __init__(self, app):
        super().__init__(app)
        self.api_key = self.config.get(OPT_API_KEY, os.environ.get(OPT_API_KEY))
        self.api_url = self.config.get(OPT_API_URL_KEY, os.environ.get(OPT_API_URL_KEY))

    async def check(self, text: str, language: str | None = None) -> dict:
        async with aiohttp.ClientSession() as session:
            return await self.perform_check(session, text, language)

    async def perform_check(
        self, session: aiohttp.ClientSession, text: str, language: str | None = None
    ) -> dict:
        try:
            check_url = self.api_url.format(method="proof")
            data = {
                "text": text,
                "language": "fi",
                "domain": "Standard",
                "options": {
                    "Format": "json",
                },
            }
            # Add API key to header "apiKey"
            headers = {"apiKey": self.api_key, "Content-Type": "application/json"}
            async with session.post(
                check_url, json=data, headers=headers, timeout=CHECK_TIMEOUT
            ) as r:
                data = await r.json()
                if r.status != 200:
                    logger.error("STT check failed status code: {}".format(r.status))
                    # get the error message from the response
                    try:
                        error_message = data.get("message")
                    except Exception:
                        error_message = r.text
                    logger.error("STT check failed: {}".format(error_message))
                    raise SuperdeskApiError.internalError(
                        "Unexpected return code from {}: {}".format(
                            self.name, error_message
                        )
                    )

            # response json should be like
            """
            {
                "errors": [
                    {
                    "title": "Tuntematon sana",
                    "explanation": "Sana vriheitä on korjausluvulle tuntematon. Tarkista, että sana on\n kirjoitettu oikein.",
                    "start": 10,
                    "length": 8,
                    "status": "UnknownWord",
                    "rule": 0,
                    "range": "vriheitä",
                    "suggestions": [
                        {
                        "action": "Replace",
                        "userText": "virheitä",
                        "words": [
                            {
                            "start": 10,
                            "length": 8,
                            "word": "virheitä"
                            }
                        ]
                        }
                    ]
                    }
                ]
            }
            """
            err_list: list[dict] = []
            check_data = {"errors": err_list}
            for err in data.get("errors", []):
                ercorr_data = {
                    "startOffset": err.get("start"),
                    "text": err.get("range"),
                    "type": "spelling",
                    "explanation": err.get("explanation"),
                    "suggestions": [
                        {"text": s["userText"]} for s in err.get("suggestions", [])
                    ],
                }
                err_list.append(ercorr_data)

            return check_data
        except Exception as e:
            logger.error("STT check failed: {}".format(e))
            return {"errors": []}

    async def suggest(self, text: str, language: str | None = None) -> dict:
        async with aiohttp.ClientSession() as session:
            return await self.perform_suggest(session, text, language)

    async def perform_suggest(
        self, session: aiohttp.ClientSession, text: str, language: str | None = None
    ) -> dict:
        try:
            check_url = self.api_url.format(method="proof")
            data = {
                "text": text,
                "language": "fi",
                "domain": "Standard",
                "options": {
                    "Format": "json",
                },
            }
            # Add API key to header "apiKey"
            headers = {"apiKey": self.api_key, "Content-Type": "application/json"}
            async with session.post(
                check_url, json=data, headers=headers, timeout=SUGGEST_TIMEOUT
            ) as r:
                if r.status != 200:
                    raise SuperdeskApiError.internalError(
                        "Unexpected return code from {}".format(self.name)
                    )
                data = await r.json()

            suggestions = []
            # NOTE: "errors" is a list of errors, each error has a list of suggestions
            for err in data.get("errors", []):
                # suggestions should be like list of strings
                suggestions.extend([s["userText"] for s in err.get("suggestions", [])])
            return {"suggestions": self.list2suggestions(suggestions)}
        except Exception as e:
            logger.error("STT suggest failed: {}".format(e))
            return {"suggestions": []}

    def available(self):
        if not self.api_key:
            logger.warning(
                "API key is not set for {label}, please set {opt} variable to use it".format(
                    label=self.label, opt=OPT_API_KEY
                )
            )
            return False
        if not self.api_url:
            logger.warning(
                "API URL is not set for {label}, please set {opt} variable to use it".format(
                    label=self.label, opt=OPT_API_URL_KEY
                )
            )
            return False
        return True


def init_app(app):
    SttFin(app)
