# -*- coding: utf-8 -*-
#
# This file is part of Superdesk.
#
# Copyright 2013,2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import logging
import os
import json
from pathlib import Path
from google.oauth2 import service_account
from google.cloud import translate_v3 as translate

logger = logging.getLogger(__name__)


class AutoTranslateItem:
    """
    AutoTranslateItem wraps Google Translate V3 calls.
    It loads service account JSON credentials from the env var
    GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON and initializes the client.
    """

    def __init__(self):
        credentials_path = os.getenv("GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_PATH")
        credentials_json = os.getenv("GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON")

        if credentials_path:
            try:
                with Path(credentials_path).open("r") as f:
                    info = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.error(
                    "Invalid credentials file in GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_PATH: %s",
                    e,
                )
                raise ValueError(
                    "Invalid credentials file in GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_PATH"
                ) from e
        elif credentials_json:
            try:
                info = json.loads(credentials_json)
            except json.JSONDecodeError as e:
                logger.error(
                    "Invalid JSON in GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON: %s", e
                )
                raise ValueError(
                    "Invalid JSON in GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON"
                ) from e
        else:
            logger.error(
                "Neither GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_PATH nor GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON is set"
            )
            raise EnvironmentError(
                "GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_PATH or GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_JSON is required"
            )
        credentials = service_account.Credentials.from_service_account_info(info)
        self.client = translate.TranslationServiceAsyncClient(credentials=credentials)

        project_id = os.getenv("GOOGLE_CLOUD_TRANSLATE_PROJECT_ID")
        if not project_id:
            logger.error("Env var GOOGLE_CLOUD_TRANSLATE_PROJECT_ID not set")
            raise EnvironmentError("GOOGLE_CLOUD_TRANSLATE_PROJECT_ID is required")
        self.parent = f"projects/{project_id}/locations/global"
        self.logger = logger

    async def translate_text(self, text, target_language="en-US"):
        """
        Translates text (string or list) into the target language.
        Returns the translated string.
        """
        if isinstance(text, str):
            text = [text]
        result = await self.client.translate_text(
            request={
                "parent": self.parent,
                "contents": text,
                "target_language_code": target_language,
            }
        )
        return result.translations[0].translated_text

    async def auto_translate_item(self, item, **kwargs):
        """
        Auto translate an item dict by extracting body_html and headline,
        removing HTML tags, calling translate_text, and returning a summary dict.
        """
        try:
            text_to_translate = item.get("body_html", "")
            headline = item.get("headline", "")
            translated_headline_en = await self.translate_text(headline, "en-US")
            translated_text_en = await self.translate_text(text_to_translate, "en-US")
            translated_text_sv = await self.translate_text(text_to_translate, "sv")

            translated_item = {
                "original_headline": headline,
                "original_text": text_to_translate,
                "translated_headline_en": translated_headline_en,
                "translated_text_en": translated_text_en,
                "translated_text_sv": translated_text_sv,
                "error": False,
            }
            return translated_item
        except Exception as e:
            self.logger.error("Error during translation: %s", e)
            return {"error": True, "message": str(e)}
