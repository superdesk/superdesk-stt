from superdesk.editor_utils import generate_fields
from .helpers.auto_translate_item import AutoTranslateItem
from .helpers.getters import get_headline_for_item, get_body_html_for_item

import logging

logger = logging.getLogger(__name__)

FIELDS = ("headline", "body_html")


def auto_translate(item, **kwargs):

    try:
        translate = AutoTranslateItem()
        translated_item = translate.auto_translate_item(item, **kwargs)
        # translated_item includes:
        #   original_headline
        #   original_text
        #   translated_headline_en
        #   translated_text_en
        #   translated_text_sv
        #   error
        #   message
        if translated_item.get("error"):
            # translation was not successful
            logger.error("Translation error: %s", translated_item.get("message"))
            return item
        item["language"] = "en"
        item["headline"] = get_headline_for_item(translated_item)
        html = get_body_html_for_item(translated_item, item)
        item["body_html"] = html
        generate_fields(item, FIELDS, force=True, reload=True)
        return item
    except Exception as e:
        logger.error("Error during Auto Translate macro: %s", str(e))
        return item


name = "auto_translate_macro"
label = "Auto Translate"
callback = auto_translate
access_type = "frontend"
action_type = "direct"
replace_type = "editor_state"
