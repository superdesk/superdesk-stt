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


class STTDatapankkiNinjsFormatter(NewsroomNinjsFormatter):
    name = "STT Datapankki NINJS"
    type = "stt datapankki ninjs"

    def __init__(self):
        self.can_preview = False
        self.can_export = False
        self.internal_renditions = ["original", "viewImage", "baseImage"]

    def update_stt_sources(self, ninjs):
        """Derive the NINJS source field from sttsource subjects with stable ordering."""
        try:
            stt_sources = [
                (subj.get("name") or "").strip()
                for subj in ninjs.get("subject", [])
                if subj.get("scheme") == "sttsource"
            ]
            stt_sources = [name for name in stt_sources if name]

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
        """Insert headline into body for SMS/Viiva profiles when required."""
        profile = ninjs.get("profile")
        if not profile:
            return
        if profile.lower() in ("viiva", "sms"):
            headline = ninjs.get("headline", "")
            if headline:
                body = ninjs.get("body_html", "")
                ninjs["body_html"] = f"<p>{headline}</p>" + (body or "")

    def update_subheadline(self, ninjs, article):
        """Inject enabled subheadline into body_html as an H2 header."""
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
        """Attach sttversion subject based on content profile and vocabulary mapping."""
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
        """Prefix ednote with sttnewsroomnote subject label when present."""
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
        """Remove internal STT subject schemes that must not be published."""
        ninjs["subject"] = [
            subj
            for subj in ninjs.get("subject", [])
            if subj.get("scheme") not in FILTER_SUBJECT_SCHEMES
        ]

    def update_place_names(self, ninjs):
        """Backfill missing place names using locators vocabulary by code/qcode."""
        places = ninjs.get("place")
        if not isinstance(places, list):
            return
        needs_lookup = any(
            isinstance(place, dict)
            and not place.get("name")
            and (place.get("code") or place.get("qcode"))
            for place in places
        )
        if not needs_lookup:
            return

        vocab_service = get_resource_service("vocabularies")
        locator_map = vocab_service.find_one(req=None, _id="locators")
        if not locator_map or "items" not in locator_map:
            return

        items = locator_map.get("items") or []
        language = ninjs.get("language")
        try:
            items = vocab_service.get_locale_vocabulary(items, language)
        except Exception:
            pass

        lookup = {
            item.get("qcode"): item
            for item in items
            if isinstance(item, dict) and item.get("qcode")
        }

        def get_label(item):
            return (
                item.get("state")
                or item.get("country")
                or item.get("world_region")
                or item.get("group")
                or item.get("name")
            )

        for place in places:
            if not isinstance(place, dict) or place.get("name"):
                continue
            code = place.get("code") or place.get("qcode")
            if not code:
                continue
            matched = lookup.get(code)
            if matched:
                label = get_label(matched)
                if label:
                    place["name"] = label

    def _get_planning_item(self, planning_id):
        """Fetch planning item by id, returning None on lookup failures."""
        if not planning_id:
            return None
        try:
            planning_service = get_resource_service("planning")
            return planning_service.find_one(req=None, _id=planning_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch planning item for datapankki export (%s: %s)",
                exc.__class__.__name__,
                exc,
            )
            return None

    def _count_planning_events(self, planning_item):
        """Count related events for a planning item with sane fallbacks."""
        if not planning_item or not isinstance(planning_item, dict):
            return None

        related_events = planning_item.get("related_events")
        if isinstance(related_events, list):
            return len(related_events)
        if isinstance(related_events, dict):
            return len(related_events)

        if planning_item.get("event_item"):
            return 1

        return 0

    def _extract_imagetype(self, article):
        """Extract imagetype from article subject list (scheme sttimagetype)."""
        subjects = article.get("subject", []) if isinstance(article, dict) else []
        for subj in subjects:
            if subj.get("scheme") == "sttimagetype":
                imagetype = {}
                qcode_value = subj.get("qcode") or subj.get("code")
                if qcode_value is not None:
                    qcode = str(qcode_value)
                    imagetype["id"] = qcode.split(":")[-1] if qcode else qcode
                if subj.get("name"):
                    imagetype["name"] = subj.get("name")
                if imagetype:
                    return imagetype
        return None

    def _extract_imagetype_from_planning(self, planning_item):
        """Extract imagetype from planning coverages subject metadata."""
        if not planning_item or not isinstance(planning_item, dict):
            return None
        for coverage in planning_item.get("coverages") or []:
            if not isinstance(coverage, dict):
                continue
            planning = coverage.get("planning") or {}
            subjects = planning.get("subject") or []
            for subj in subjects:
                if subj.get("scheme") != "sttimagetype":
                    continue
                imagetype = {}
                qcode_value = subj.get("qcode") or subj.get("code")
                if qcode_value is not None:
                    qcode = str(qcode_value)
                    imagetype["id"] = qcode.split(":")[-1] if qcode else qcode
                if subj.get("name"):
                    imagetype["name"] = subj.get("name")
                if imagetype:
                    return imagetype
        return None

    def _get_datapankki_signal(self, article):
        """Map article state/rewrite/operation to a Datapankki signal string."""
        if not isinstance(article, dict):
            return None
        if article.get("state") == "corrected":
            return "corrected"
        if article.get("rewrite_of"):
            return "update"
        operation = article.get("operation")
        if operation:
            return str(operation)
        return None

    def _get_task_user(self, article):
        """Fetch the user document referenced by task.user, if available."""
        if not isinstance(article, dict):
            return None
        task = article.get("task") or {}
        user_id = task.get("user")
        if not user_id:
            return None
        try:
            users_service = get_resource_service("users")
            return users_service.find_one(req=None, _id=user_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch task user for datapankki export (%s: %s)",
                exc.__class__.__name__,
                exc,
            )
            return None

    def update_datapankki_fields(self, ninjs, article):
        """Enrich ninjs with Datapankki-specific fields and planning metadata."""
        extra = ninjs.setdefault("extra", {})

        planning_item = None
        if (
            "stt_events_count" not in extra
            or "anpa_category" not in extra
            or "imagetype" not in extra
        ):
            planning_id = ninjs.get("planning_id") or article.get("planning_id")
            planning_item = self._get_planning_item(planning_id)

        if "stt_events_count" not in extra:
            stt_events_count = self._count_planning_events(planning_item)
            if stt_events_count is not None:
                extra["stt_events_count"] = stt_events_count

        if "anpa_category" not in extra and planning_item:
            planning_anpa = planning_item.get("anpa_category")
            if planning_anpa is not None:
                extra["anpa_category"] = planning_anpa

        if "imagetype" not in extra:
            imagetype = self._extract_imagetype(article)
            if imagetype:
                extra["imagetype"] = imagetype
            elif planning_item:
                imagetype = self._extract_imagetype_from_planning(planning_item)
                if imagetype:
                    extra["imagetype"] = imagetype

        if "signal" not in extra:
            signal = self._get_datapankki_signal(article)
            if signal:
                extra["signal"] = signal

        if not extra.get("creator_id") or not extra.get("creator_name"):
            user = self._get_task_user(article)
            if user:
                if not extra.get("creator_id") and user.get("_id") is not None:
                    extra["creator_id"] = str(user.get("_id"))
                if not extra.get("creator_name") and user.get("display_name"):
                    extra["creator_name"] = user.get("display_name")

    async def _transform_to_ninjs(self, article, subscriber, recursive=True):
        """Transform item to NINJS and apply Datapankki-specific post-processing."""

        ninjs = await super()._transform_to_ninjs(article, subscriber, recursive)

        self.update_stt_sources(ninjs)
        self.update_subheadline(ninjs, article)
        self.update_body_from_content_profiles(ninjs)
        self.update_sttversion(ninjs)
        self.update_editorial_note(ninjs)
        self.filter_subjects(ninjs)
        self.update_place_names(ninjs)
        self.update_datapankki_fields(ninjs, article)

        ninjs.pop("slugline", None)

        if ninjs.get("body_html"):
            ninjs["body_html"] = encode_special_characters(ninjs["body_html"])

        if ninjs.get("headline"):
            ninjs["headline"] = decode_special_characters(
                encode_special_characters(ninjs["headline"])
            )

        if article.get("operation"):
            ninjs["operation"] = article.get("operation")

        return ninjs
