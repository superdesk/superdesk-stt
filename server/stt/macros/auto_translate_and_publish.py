# from superdesk import get_resource_service
from apps.publish.content.common import ITEM_PUBLISH
from superdesk.editor_utils import generate_fields
from .helpers.auto_translate_item import AutoTranslateItem
import logging

logger = logging.getLogger(__name__)

FIELDS = ("headline", "body_html")


def get_headline_for_item(translated_item):
    # headline should be english version like
    """
    Sebastian Aho scored half of the Ottawa Senators' goals against the Carolina Hurricanes*** TRANSLATED ***
    """
    headline = translated_item.get("translated_headline_en", "")
    # add "*** TRANSLATED ***" to the end of the headline
    if headline and not headline.endswith("*** TRANSLATED ***"):
        headline += " *** TRANSLATED ***"
    return headline


def get_body_html_for_item(translated_item, item):
    # body html needs to start like this:
    """
    <h2>AUTOMATED TRANSLATION FROM FINNISH NEWS FEED</h2>

    *** DISCLAIMER: THIS IS AN AUTOMATED TRANSLATION FROM FINNISH ***
    """
    body_html = "<h2>AUTOMATED TRANSLATION FROM FINNISH NEWS FEED</h2>"
    body_html += "<p><b>*** DISCLAIMER: THIS IS AN AUTOMATED TRANSLATION FROM FINNISH ***</b></p>"
    # then add english version of the text
    body_html += f"{translated_item.get('translated_text_en', '')}"
    # then add this text:
    """
    *** ANSVARSFRISKRIVNING: DETTA ÄR EN AUTOMATISK ÖVERSÄTTNING FRÅN FINSKA ***
    """
    body_html += "<p><b>*** ANSVARSFRISKRIVNING: DETTA ÄR EN AUTOMATISK ÖVERSÄTTNING FRÅN FINSKA ***</b></p>"
    # and then add swedish version of the text
    body_html += f"{translated_item.get('translated_text_sv', '')}"
    # then add:
    """
    *** ORIGINAL TEXT ***
    """
    body_html += "<p><b>*** ORIGINAL TEXT ***</b></p>"
    # and then add the original text
    body_html += f"{item.get('body_html', '')}"
    # and return the body html
    return body_html


def auto_translate_and_publish(item, **kwargs):
    """This macro runs two macros auto_translate_item and desk_routing."""

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
        item["operation"] = ITEM_PUBLISH
        item["language"] = "en"
        item["headline"] = get_headline_for_item(translated_item)
        html = get_body_html_for_item(translated_item, item)
        logger.info("Generated body_html: %s", html)
        item["body_html"] = html
        generate_fields(item, FIELDS, force=True, reload=True)
        return item
    except Exception as e:
        logger.error("Error during Auto Translate and Publish macro: %s", str(e))
        return item


name = "auto_translate_and_publish_macro"
label = "Auto Translate and Publish"
callback = auto_translate_and_publish
access_type = "frontend"
action_type = "direct"
replace_type = "editor_state"
