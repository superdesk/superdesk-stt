# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with the source code, or
# at https://www.sourcefabric.org/superdesk/license

from datetime import datetime
import mimetypes
import logging
import os.path
import arrow

from superdesk.core import get_current_app
from superdesk.resource_fields import VERSION, ITEM_TYPE
from superdesk.io.feed_parsers import FileFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.errors import ParserError
from superdesk.media.media_operations import process_file_from_stream
from PIL import Image, IptcImagePlugin

from superdesk.media.iim_codes import TAG, iim_codes
from superdesk.metadata.item import GUID_TAG, CONTENT_TYPE
from superdesk.metadata import utils
from superdesk.media.renditions import generate_renditions, get_renditions_spec
from superdesk.upload import url_for_media
from superdesk.utc import utcnow
from superdesk import filemeta


logger = logging.getLogger(__name__)


class SttImageIPTCFeedParser(FileFeedParser):
    """
    Feed Parser which can parse images using IPTC metadata
    """

    NAME = "stt_image_iptc"
    label = "STT Image (IPTC metadata)"
    ALLOWED_EXT = mimetypes.guess_all_extensions("image/jpeg")

    DATETIME_FORMAT = "%Y%m%dT%H%M%S%z"

    IPTC_MAPPING = {
        TAG.HEADLINE: "headline",
        TAG.BY_LINE: "byline",
        TAG.OBJECT_NAME: "slugline",
        TAG.CAPTION_ABSTRACT: "description_text",
        TAG.KEYWORDS: "keywords",
        TAG.SPECIAL_INSTRUCTIONS: "ednote",
        TAG.COPYRIGHT_NOTICE: "copyrightnotice",
        # TAG.ORIGINAL_TRANSMISSION_REFERENCE: "assignment_id",
    }

    def can_parse(self, image_path):
        if not isinstance(image_path, str):
            return False
        return mimetypes.guess_type(image_path)[0] == "image/jpeg"

    async def parse(self, image_path, provider=None):
        try:
            item = self.parse_item(image_path)
            return item
        except Exception as ex:
            logger.exception(ex)
            raise await ParserError.parseFileError(
                exception=ex, provider=provider
            ).send_notifications()

    def parse_item(self, image_path):
        filename = os.path.basename(image_path)
        content_type = mimetypes.guess_type(image_path)[0]
        guid = utils.generate_guid(type=GUID_TAG)
        item = {
            "guid": guid,
            "uri": guid,
            VERSION: 1,
            ITEM_TYPE: CONTENT_TYPE.PICTURE,
            "mimetype": content_type,
            "versioncreated": utcnow(),
        }
        with open(image_path, "rb") as f:
            _, content_type, file_metadata = process_file_from_stream(
                f, content_type=content_type
            )
            f.seek(0)
            app = get_current_app()
            file_id = app.media.put(
                f, filename=filename, content_type=content_type, metadata=file_metadata
            )
            filemeta.set_filemeta(item, file_metadata)
            f.seek(0)

            metadata = self._get_iptc_metadata(f)
            f.seek(0)
            self.parse_meta(item, metadata)

            rendition_spec = get_renditions_spec(no_custom_crops=True)
            renditions = generate_renditions(
                f,
                file_id,
                [file_id],
                "image",
                content_type,
                rendition_spec,
                url_for_media,
            )
            item["renditions"] = renditions
        return item

    # ESC % G: ISO 2022 escape sequence signalling UTF-8 in IPTC record 1 tag 90
    _IPTC_UTF8_MARKER = b"\x1b%G"

    def _get_iptc_metadata(self, f):
        """Read IPTC metadata with correct encoding.

        Checks IPTC Record 1, Tag 90 (Coded Character Set) for an explicit
        UTF-8 declaration (ESC % G).  When absent — the common case for legacy
        Finnish/Nordic news-agency images written by Photoshop or similar tools
        — falls back to Windows-1252 (CP1252).  CP1252 is a superset of
        Latin-1: Nordic characters (ä, ö, å …) are identical, but CP1252 also
        correctly maps the 0x80-0x9F range to printable typographic characters
        (en/em dashes, curly quotes, ellipsis …) that Latin-1 leaves as
        invisible C1 control codes.
        """
        f.seek(0)
        img = Image.open(f)
        iptc_raw = IptcImagePlugin.getiptcinfo(img)

        if not iptc_raw:
            return {}

        charset_value = iptc_raw.get((1, 90), b"")
        encoding = "utf-8" if self._IPTC_UTF8_MARKER in charset_value else "cp1252"

        metadata = {}
        for code, value in iptc_raw.items():
            try:
                tag = iim_codes[code]
            except KeyError:
                continue
            if isinstance(value, list):
                metadata[tag] = [
                    v.decode(encoding, errors="replace") if isinstance(v, bytes) else v
                    for v in value
                ]
            elif isinstance(value, bytes):
                metadata[tag] = value.decode(encoding, errors="replace")
        return metadata

    def parse_date_time(self, date, time):
        if not date or not time:
            return

        datetime_string = "{}T{}".format(date, time)
        try:
            return datetime.strptime(datetime_string, self.DATETIME_FORMAT)
        except ValueError:
            try:
                return arrow.get(datetime_string).datetime
            except ValueError:
                return

    def parse_meta(self, item, metadata):
        datetime_created = self.parse_date_time(
            metadata.get(TAG.DATE_CREATED), metadata.get(TAG.TIME_CREATED)
        )
        if datetime_created:
            item["firstcreated"] = datetime_created

        # now we map IPTC metadata to superdesk metadata
        for source_key, dest_key in self.IPTC_MAPPING.items():
            try:
                item[dest_key] = metadata[source_key]
            except KeyError:
                continue

        # SDESK-6566
        if isinstance(item.get("keywords"), str):
            item["keywords"] = [item["keywords"]]

        return item


register_feed_parser(SttImageIPTCFeedParser.NAME, SttImageIPTCFeedParser())
