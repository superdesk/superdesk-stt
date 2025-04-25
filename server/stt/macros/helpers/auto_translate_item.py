# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013,2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information,please see the
# AUTHORS and LICENSE files distributed with this source code,or
# at https://www.sourcefabric.org/superdesk/license

import logging
import re
import os
from pathlib import Path
from google.oauth2 import service_account
from google.cloud import translate_v3 as translate

logger = logging.getLogger(__name__)


def translate_text(text, target_language="en-US"):
    """
    Translates text into the target language.

    Args:
        text (str): The text to be translated.
        target_language (str): The language code to translate the text into (e.g., 'es' for Spanish).

    Returns:
        str: The translated text.
    """
    # Initialize the translation client.
    service_account_path = Path(__file__).parent / "service-account.json"
    # check that the service account file exists
    if not service_account_path.exists():
        logger.error("Service account file not found: %s", service_account_path)
        raise FileNotFoundError(
            f"Service account file not found: {service_account_path}"
        )
    credentials = service_account.Credentials.from_service_account_file(
        str(service_account_path)
    )
    # Set up the translation client with credentials
    client = translate.TranslationServiceClient(credentials=credentials)
    parent = (
        f"projects/{os.getenv('GOOGLE_CLOUD_TRANSLATE_PROJECT_ID')}/locations/global"
    )
    # Translate the text.
    # text should be list of strings
    if isinstance(text, str):
        text = [text]
    result = client.translate_text(
        request={
            "parent": parent,
            "contents": text,  # Note: "contents" is the correct argument name for a list of strings.
            "target_language_code": target_language,
        }
    )

    # The API returns a dictionary; the translated text is stored under the key 'translatedText'.
    return result.translations[0].translated_text


def auto_translate_item(item, **kwargs):
    """Auto translate item using Google Translate API.
    Args:
        item (dict): The item to be translated.
        **kwargs: Additional arguments.
    Returns:
        dict: The translated item.
    """

    try:
        # merge     'body_html' and 'headline' to translated text
        body_without_html = item.get("body_html", "")
        # Remove all HTML tags from body_html (h1, h2, h3, p, etc.)
        text_to_translate = re.sub(r"<[^>]+>", "", body_without_html)
        logger.info("Auto translating item: %s", text_to_translate)

        headline_to_translate = item.get("headline", "")
        translated_headline_en = translate_text(
            headline_to_translate, target_language="en-US"
        )
        # translated_headline_sv = translate_text(
        #     headline_to_translate, target_language="sv"
        # )
        translated_headline = {
            "translated_headline_en": translated_headline_en,
            "original_headline": headline_to_translate,
        }
        logger.info("Translated headline: %s", translated_headline)
        translated_text_en = translate_text(text_to_translate, target_language="en-US")
        translated_text_sv = translate_text(text_to_translate, target_language="sv")
        translated_item = {
            "original_headline": headline_to_translate,
            "original_text": text_to_translate,
            "translated_headline_en": translated_headline_en,
            "translated_text_en": translated_text_en,
            "translated_text_sv": translated_text_sv,
            "error": False,
        }
        logger.info("Translated item: %s", translated_item)
        return translated_item
    except Exception as e:
        logger.error("Error during translation: %s", str(e))
        return {
            "error": True,
            "message": str(e),
        }


# name = "Auto Translate Item"
# label = name
# callback = auto_translate_item
# access_type = "backend"
# action_type = "direct"
