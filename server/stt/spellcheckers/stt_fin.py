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
import requests
from superdesk.errors import SuperdeskApiError
from superdesk.text_checkers.spellcheckers import CAP_SPELLING
from superdesk.text_checkers.spellcheckers.base import SpellcheckerBase

logger = logging.getLogger(__name__)
OPT_API_KEY = "STT_FIN_API_KEY"
API_URL = "https://api.lingsoft.fi/lmc/{method}/"


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

    def check(self, text, language=None):
        try:
            check_url = API_URL.format(method="proof")
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
            r = requests.post(
                check_url, json=data, headers=headers, timeout=self.CHECK_TIMEOUT
            )
            if r.status_code != 200:
                logger.error("STT check failed status code: {}".format(r.status_code))
                # get the error message from the response
                try:
                    error_message = r.json().get("message")
                except Exception:
                    error_message = r.text
                logger.error("STT check failed: {}".format(error_message))
                raise SuperdeskApiError.internalError(
                    "Unexpected return code from {}: {}".format(
                        self.name, error_message
                    )
                )

            data = r.json()
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

            err_list = []
            for err in data.get("errors", []):
                ercorr_data = {
                    "startOffset": err.get("start"),
                    "text": err.get("range"),
                    "type": "spelling",
                    "explanation": err.get("explanation"),
                    "suggestions": err.get("suggestions", []),
                }
                err_list.append(ercorr_data)

            return {"errors": err_list}
        except Exception as e:
            logger.error("STT check failed: {}".format(e))
            return {"errors": []}

    def suggest(self, text, language=None):
        try:
            check_url = API_URL.format(method="proof")
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
            r = requests.post(
                check_url, json=data, headers=headers, timeout=self.CHECK_TIMEOUT
            )
            if r.status_code != 200:
                raise SuperdeskApiError.internalError(
                    "Unexpected return code from {}".format(self.name)
                )
            data = r.json()
            suggestions = []
            for err in data.get("errors", []):
                suggestions.extend(
                    [{"text": s["userText"]} for s in err.get("suggestions", [])]
                )

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
        return True


def init_app(app):
    SttFin(app)
