import logging
import re

from superdesk import get_resource_service
from superdesk.publish.formatters import NewsroomNinjsFormatter

from stt.publish.utils import decode_special_characters, encode_special_characters


logger = logging.getLogger(__name__)

FILTER_SUBJECT_SCHEMES = {
    "stttopstory",
    "sttsource",
    "sttdepartment",
    "sttsubject",
    "sttsubj",
    "sttdone1",
}


class STTNewsroomNinjsFormatter(NewsroomNinjsFormatter):
    name = "STT Newsroom NINJS"
    type = "stt newsroom ninjs"

    def __init__(self):
        self.can_preview = False
        self.can_export = False
        self.internal_renditions = ["original", "viewImage", "baseImage"]

    def update_stt_sources(self, ninjs):
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
            logger.error(f"Error occurred when updating stt sources: {str(e)}")

    def update_body_from_content_profiles(self, ninjs):
        profile = ninjs.get("profile")
        if not profile:
            return
        if profile.lower() in ("viiva", "sms"):
            headline = ninjs.get("headline", "")
            if headline:
                body = ninjs.get("body_html", "")
                ninjs["body_html"] = f"<p>{headline}</p>" + (body or "")

    def update_subheadline(self, ninjs, article):
        extra = ninjs.get("extra", {})
        sttsubheadline = extra.get("sttsubheadline")
        if not sttsubheadline:
            return

        profile = (
            article.get("profile")
            and get_resource_service("content_types").find_one(
                req=None, _id=article.get("profile")
            )
            or None
        )

        try:
            subheadline_enabled = (
                profile and profile["editor"]["sttsubheadline"]["enabled"]
            )
        except (KeyError, TypeError):
            subheadline_enabled = False

        if not subheadline_enabled:
            return

        text = re.sub(r"<[^>]+>", "", sttsubheadline).strip()
        if not text:
            text = sttsubheadline.strip()
        header = f"<h2>{text}</h2>\n"
        body = ninjs.get("body_html", "")
        ninjs["body_html"] = header + (body or "")

    def update_sttversion(self, ninjs):
        profile = ninjs.get("profile")
        if not profile:
            return

        vocabulary_items = get_resource_service("vocabularies").get_items(
            "sttversion", is_active=None
        )

        content_profile_name = None
        qcode = None
        profile_lower = profile.lower()

        for vocab_item in vocabulary_items:
            vocab_name = vocab_item.get("name", "").lower()
            vocab_cp_name = (vocab_item.get("content_profile_name") or "").lower()

            if vocab_name == profile_lower or vocab_cp_name == profile_lower:
                content_profile_name = vocab_item.get("content_profile_name")
                qcode = vocab_item.get("qcode")

                # Special case for backward consistency
                if profile_lower in ("pikaplus", "pika+"):
                    content_profile_name = "Pika+"

                break

        version = (
            str(content_profile_name if content_profile_name is not None else profile)
            .strip()
            .capitalize()
        )

        if qcode and version:
            ninjs.setdefault("subject", [])

            sttversion_exists = any(
                subj.get("scheme") == "sttversion" for subj in ninjs["subject"]
            )

            if not sttversion_exists:
                ninjs["subject"].append(
                    {"name": version, "scheme": "sttversion", "code": qcode}
                )

    def update_editorial_note(self, ninjs):
        name = None
        for subject in ninjs.get("subject", []):
            if subject.get("scheme") == "sttnewsroomnote":
                name = subject.get("name")
                break
        if not name:
            return
        ednote = ninjs.get("ednote", "")
        ninjs["ednote"] = f"{name}. {ednote}"

    def filter_subjects(self, ninjs):
        ninjs["subject"] = [
            subj
            for subj in ninjs.get("subject", [])
            if subj.get("scheme") not in FILTER_SUBJECT_SCHEMES
        ]

    async def _transform_to_ninjs(self, article, subscriber, recursive=True):
        ninjs = await super()._transform_to_ninjs(article, subscriber, recursive)

        self.update_stt_sources(ninjs)
        self.update_subheadline(ninjs, article)
        self.update_body_from_content_profiles(ninjs)
        self.update_sttversion(ninjs)
        self.update_editorial_note(ninjs)
        self.filter_subjects(ninjs)

        ninjs.pop("slugline", None)

        if ninjs.get("body_html"):
            ninjs["body_html"] = encode_special_characters(ninjs["body_html"])

        if ninjs.get("headline"):
            ninjs["headline"] = decode_special_characters(
                encode_special_characters(ninjs["headline"])
            )

        return ninjs
