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

from google.cloud import translate_v3 as translate

logger = logging.getLogger(__name__)


def translate_text(text, target_language="es"):
    """
    Translates text into the target language.

    Args:
        text (str): The text to be translated.
        target_language (str): The language code to translate the text into (e.g., 'es' for Spanish).

    Returns:
        str: The translated text.
    """
    # Initialize the translation client.
    client = translate.Client()

    # Translate the text.
    result = client.translate(text, target_language=target_language)

    # The API returns a dictionary; the translated text is stored under the key 'translatedText'.
    return result.get("translatedText")


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
            headline_to_translate, target_language="en"
        )
        translated_headline_sv = translate_text(
            headline_to_translate, target_language="sv"
        )
        translated_headline = {
            "translated_headline_en": translated_headline_en,
            "translated_headline_sv": translated_headline_sv,
            "original_headline": headline_to_translate,
        }
        logger.info("Translated headline: %s", translated_headline)
        translated_text_en = translate_text(text_to_translate, target_language="en")
        translated_text_sv = translate_text(text_to_translate, target_language="sv")
        translated_item = {
            "original_headline": headline_to_translate,
            "original_text": text_to_translate,
            "translated_headline_en": translated_headline_en,
            "translated_headline_sv": translated_headline_sv,
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


name = "Auto Translate Item"
label = name
callback = auto_translate_item
access_type = "backend"
action_type = "direct"
