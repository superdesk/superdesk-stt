from superdesk import get_resource_service
from superdesk.errors import StopDuplication
from superdesk.resource_fields import ID_FIELD
from superdesk.metadata.item import (
    ITEM_STATE,
    CONTENT_STATE,
    PUBLISH_SCHEDULE,
    SCHEDULE_SETTINGS,
)
from .helpers.auto_translate_item import AutoTranslateItem
from .helpers.getters import get_headline_for_item, get_body_html_for_item

import logging

logger = logging.getLogger(__name__)


async def auto_publish(item, **kwargs):
    """
    Publish the passed item. The macro must be called as an on stage macro as publishing an item that is in transit
    i.e. an incoming or outgoing macro will fail.
    :param item:
    :param kwargs:
    :return:
    """
    await get_resource_service("archive_publish").patch_async(
        id=item[ID_FIELD],
        updates={ITEM_STATE: CONTENT_STATE.PUBLISHED, "auto_publish": True},
    )
    return item


async def auto_translate_and_publish(item, **kwargs):
    """This macro runs two steps: auto_translate_item and archive_publish."""

    try:
        translate = AutoTranslateItem()
        translated_item = await translate.auto_translate_item(item, **kwargs)
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
        internal_destination = kwargs.get("internal_destination")
        if internal_destination:
            archive_service = get_resource_service("archive")
            extra_fields = [PUBLISH_SCHEDULE, SCHEDULE_SETTINGS]
            new_id = await archive_service.duplicate_item(
                item, state="routed", extra_fields=extra_fields
            )
            await get_resource_service("archive_publish").patch_async(
                id=new_id,
                updates={ITEM_STATE: CONTENT_STATE.PUBLISHED, "auto_publish": True},
            )
            raise StopDuplication()
        if item.get(ITEM_STATE) == CONTENT_STATE.PUBLISHED:
            return item
        return await auto_publish(item, **kwargs)
    except StopDuplication:
        raise
    except Exception as e:
        logger.error("Error during Auto Translate and Publish macro: %s", str(e))
        return item


name = "auto_translate_and_publish_macro"
label = "Auto Translate and Publish"
callback = auto_translate_and_publish
access_type = "backend"
action_type = "direct"
