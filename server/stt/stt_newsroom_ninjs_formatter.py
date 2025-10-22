import logging

from superdesk.publish.formatters import NewsroomNinjsFormatter

logger = logging.getLogger(__name__)


class STTNewsroomNinjsFormatter(NewsroomNinjsFormatter):
    name = "STT Newsroom NINJS"
    type = "stt newsroom ninjs"

    def __init__(self):
        self.can_preview = False
        self.can_export = False
        self.internal_renditions = ["original", "viewImage", "baseImage"]

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

            ninjs["source"] = "-".join(sorted_sources)
        except Exception as e:
            logger.error(f"Error occurred when updating ninjs stt sources: {str(e)}")

    async def _transform_to_ninjs(self, article, subscriber, recursive=True):
        ninjs = await super()._transform_to_ninjs(article, subscriber, recursive)
        self.update_ninjs_stt_sources(ninjs)

        return ninjs
