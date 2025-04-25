# from superdesk import get_resource_service
from apps.publish.content.common import ITEM_PUBLISH
from .helpers.auto_translate_item import AutoTranslateItem
import logging

logger = logging.getLogger(__name__)


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


def get_body_html_for_item(translated_item):
    # body html needs to start like this:
    """
    <h2>AUTOMATED TRANSLATION FROM FINNISH NEWS FEED</h2>

    *** DISCLAIMER: THIS IS AN AUTOMATED TRANSLATION FROM FINNISH ***
    """
    body_html = "<h2>AUTOMATED TRANSLATION FROM FINNISH NEWS FEED</h2>\n\n*** DISCLAIMER: THIS IS AN AUTOMATED TRANSLATION FROM FINNISH ***"
    # then add english version of the text
    body_html += f"{translated_item.get('translated_text_en', '')}"
    # then add this text:
    """
    *** ANSVARSFRISKRIVNING: DETTA ÄR EN AUTOMATISK ÖVERSÄTTNING FRÅN FINSKA ***
    """
    body_html += "\n\n*** ANSVARSFRISKRIVNING: DETTA ÄR EN AUTOMATISK ÖVERSÄTTNING FRÅN FINSKA ***"
    # and then add swedish version of the text
    body_html += f"\n\n{translated_item.get('translated_text_sv', '')}"
    # then add:
    """
    *** ORIGINAL TEXT ***
    """
    body_html += "\n\n*** ORIGINAL TEXT ***"
    # and then add the original text
    body_html += f"\n\n{translated_item.get('original_text', '')}"
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
        html = get_body_html_for_item(translated_item)

        # 1) replace the stored HTML
        item["body_html"] = html
        # 2) manually construct a minimal DraftJS state
        #    (this will display raw HTML tags as text, or you can strip tags if you need)
        draft_state = {
            "blocks": [
                {
                    "key": "auto",
                    "text": html,
                    "type": "unstyled",
                    "depth": 0,
                    "inlineStyleRanges": [],
                    "entityRanges": [],
                    "data": {},
                }
            ],
            "entityMap": {},
        }

        item.setdefault("fields_meta", {}).setdefault("body_html", {})[
            "draftjsState"
        ] = [draft_state]
        logger.info("New item: %s", item)
        return item
    except Exception as e:
        logger.error("Error during Auto Translate and Publish macro: %s", str(e))
        return item


name = "auto_translate_and_publish_macro"
label = "Auto Translate and Publish"
callback = auto_translate_and_publish
access_type = "frontend"
action_type = "direct"
