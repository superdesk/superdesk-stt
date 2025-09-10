import logging

from superdesk import get_resource_service
from superdesk.publish.formatters import NewsroomNinjsFormatter

logger = logging.getLogger(__name__)


class STTNewsroomNinjsFormatter(NewsroomNinjsFormatter):
    name = "STT Newsroom NINJS"
    type = "stt newsroom ninjs"

    def __init__(self):
        self.can_preview = False
        self.can_export = False
        self.internal_renditions = ["original", "viewImage", "baseImage"]

    def update_ninjs_stt_urgency(self, ninjs):
        priority = ninjs.get("priority", 0)

        if priority == 1:
            qcode = "stturgency-1"
        elif priority == 2 or priority == 3:
            # Special case where qcode 2 and 3 mapped to value of qcode 2 to NH
            qcode = "stturgency-2"
        elif priority == 4:
            qcode = "stturgency-4"
        else:
            qcode = "stturgency-5"

        items = get_resource_service("vocabularies").get_items("stturgency")

        stturgency_item = None
        for item in items:
            if item.get("qcode") == qcode:
                stturgency_item = item
                break

        if stturgency_item:
            if "subject" not in ninjs:
                ninjs["subject"] = []

            ninjs["subject"] = [
                subj for subj in ninjs["subject"] if subj.get("scheme") != "stturgency"
            ]

            ninjs["subject"].append(
                {
                    "name": stturgency_item["name"],
                    "qcode": qcode,
                    "scheme": "stturgency",
                }
            )

    def update_ninjs_stt_sources(self, ninjs):
        try:
            stt_sources = [
                subj["name"]
                for subj in ninjs.get("subject", [])
                if subj.get("scheme") == "sttsource"
            ]

            if not stt_sources:
                ninjs["source"] = "STT"
                return

            # Remove duplicates and sort with STT being first, then alphabetical order
            unique_sources = list(set(stt_sources))
            if "STT" in unique_sources:
                unique_sources.remove("STT")
                sorted_sources = ["STT"] + sorted(unique_sources, key=str.lower)
            else:
                sorted_sources = sorted(unique_sources, key=str.lower)

            ninjs["source"] = ", ".join(sorted_sources)
        except Exception as e:
            logger.error(f"Error occurred when updating ninjs stt sources: {str(e)}")

    async def _transform_to_ninjs(self, article, subscriber, recursive=True):
        ninjs = await super()._transform_to_ninjs(article, subscriber, recursive)
        self.update_ninjs_stt_sources(ninjs)
        self.update_ninjs_stt_urgency(ninjs)

        return ninjs
