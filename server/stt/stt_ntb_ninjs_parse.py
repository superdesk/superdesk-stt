import json
import logging
from datetime import timezone
from typing import Any, Dict, Iterable, List, Optional

from lxml import etree
from lxml import html as lxml_html
from dateutil import tz
from dateutil.parser import isoparse
from superdesk.io.feed_parsers.ninjs import NINJSFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.text_utils import sanitize_html

TIMEZONE = "Europe/Helsinki"

# CV paths (override via provider if desired)
MEDIA_TOPICS_CV = "topics"
DEPT_CATEGORIES_CV = "categories"

# Default department qcode when NTB category has no mapping (per ticket requirement)
DEFAULT_DEPT_FALLBACK_QCODE = "12"
STATIC_DEPT_FALLBACK_NAME = "Tiedotepalvelu"

# Static names for department qcodes (used when CV is missing)
STATIC_DEPT_NAMES = {
    "3": "Kotimaa",  # Domestic
    "14": "Ulkomaat",  # Foreign
    "16": "Urheilu",  # Sports
    "12": "Tiedotepalvelu",  # Fallback department
}

logger = logging.getLogger(__name__)

# Map NTB category labels to STT department qcodes
DEFAULT_NTB_TO_STT_DEPT = {
    "Innenriks": "3",  # Kotimaa (Domestic)
    "Utenriks": "14",  # Ulkomaat (Foreign)
    "Sport": "16",  # Urheilu (Sports)
}


# ----------------------------- Helpers -------------------------------------


def _load_cv(vocab_id: str) -> List[Dict[str, Any]]:
    """Load active items from a Superdesk vocabulary using get_items only.

    Args:
        vocab_id: Vocabulary identifier

    Returns:
        List of active vocabulary items, or empty list if not found/error.

    The vocabularies service `get_items` method already returns active items only,
    so we don't need any manual filtering or a fallback path here.
    """
    try:
        from superdesk import get_resource_service  # type: ignore

        service = get_resource_service("vocabularies")
        if not service:
            logger.warning("Vocabularies service not available")
            return []

        if hasattr(service, "get_items") and callable(service.get_items):
            items = service.get_items(vocab_id)
            return _ensure_list(items)

        logger.warning("Vocabularies service does not provide get_items()")
        return []

    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load vocabulary '%s': %s", vocab_id, exc)
        return []


def _ensure_list(items: Any) -> List[Dict[str, Any]]:
    """Ensure the result is a list of dictionaries."""
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def strip_text(s: Optional[str]) -> str:
    return (s or "").strip()


def _cv_lookup(
    cv_items: Iterable[Dict[str, Any]], qcode: str
) -> Optional[Dict[str, Any]]:
    q = strip_text(qcode).lower()
    if not q:
        return None
    for it in cv_items:
        # First try to match by qcode
        if strip_text(it.get("qcode", "")).lower() == q:
            return it
        # Then try to match by name for mapping entries
        if strip_text(it.get("name", "")).lower() == q:
            return it
    return None


def _prepend_abstract(item: Dict[str, Any]) -> None:
    """Prepend description_html as the first <p> of body_html."""
    abstract = strip_text(item.get("description_html"))
    if not abstract:
        return
    body = strip_text(item.get("body_html"))
    prefix = f"<p>{abstract}</p>"
    if body.startswith(prefix) or body.startswith(abstract):
        return
    item["body_html"] = f"{prefix}{body}" if body else prefix


def _strip_ignored(item: Dict[str, Any]) -> None:
    """Drop fields we do not ingest."""
    for k in ("place", "genre"):
        item.pop(k, None)


# ------------------------------ Parser -------------------------------------


class STTTTNINJSParseFeedParser(NINJSFeedParser):
    """
    Feed Parser for STT TT NINJS format (extends core NINJS + STT-specific mapping)
    """

    NAME = "stt_ntb_ninjs_parse"
    label = "STT NTB NINJS Parse Feed Parser"

    def __init__(self) -> None:
        super().__init__()

    # Keep your original behavior: read JSON and skip image items
    def can_parse(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                ninjs = json.load(f)
                return ninjs.get("type") != "image"
        except Exception:
            return False

    def datetime(self, value):
        """Parse to tz-aware UTC datetime. If naive, assume Europe/Helsinki."""
        if not value:
            return None
        try:
            dt = isoparse(value)
        except Exception:
            return super().datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz.gettz(TIMEZONE))
        return dt.astimezone(timezone.utc)

    def sanitise_stt_tt_html(self, html):
        if not html:
            return ""

        remove_tags = [
            "html",
            "body",
            "title",
            "article",
            "section",
            "aside",
            "div",
            "h4",
        ]
        kill_tags = ["head"]

        root_elem = lxml_html.fromstring(html)
        for _action, el in etree.iterwalk(root_elem):
            if el.tag == "div" and el.get("class") == "byline":
                el.tag = "p"
            if el.tag == "span":
                el.tag = "p"

        traversed_html = etree.tostring(root_elem, encoding="unicode")
        sanitized_html = sanitize_html(
            traversed_html,
            remove_tags=remove_tags,
            kill_tags=kill_tags,
        )
        # trim the outer <p> wrapper if present (keeps parity with your sample)
        out = sanitized_html.strip()
        if out.startswith("<p>") and out.endswith("</p>"):
            return out[3:-4]
        return out

    # --- NINJS -> Item (+ STT mappings) -------------------------------------

    def _transform_from_ninjs(self, ninjs):
        # drop heavy associations without mutating the original
        work = dict(ninjs)
        work.pop("associations", None)

        # use core transform first
        item = super()._transform_from_ninjs(work)

        # body_html from body_html5 (sanitized)
        item["body_html"] = self.sanitise_stt_tt_html(ninjs.get("body_html5"))

        # keep description_html for abstract prepending
        if ninjs.get("description_html"):
            item["description_html"] = ninjs.get("description_html")

        # 1) strip ignored fields
        _strip_ignored(item)

        # 2) prepend abstract as first paragraph
        _prepend_abstract(item)

        # 3) Media Topics mapping: subject(scheme: topics) -> media_topics
        subjects = ninjs.get("subject") or []
        if isinstance(subjects, list):
            cv_topics = _load_cv(MEDIA_TOPICS_CV)
            mapped_topics: List[Dict[str, Any]] = []
            for s in subjects:
                if not isinstance(s, dict):
                    continue
                if strip_text(s.get("scheme")).lower() not in {"topics", "topic"}:
                    continue
                hit = _cv_lookup(cv_topics, strip_text(s.get("code")))
                if hit:
                    mapped_topics.append(hit)
            if mapped_topics:
                item["media_topics"] = mapped_topics
        # 4) Category mapping: subject(scheme: category) -> anpa_category
        # Ensure exactly one category entry (deterministic choice with fallback)
        if isinstance(subjects, list):
            cv_depts = _load_cv(DEPT_CATEGORIES_CV)

            # Find the first category subject from source
            selected_code: Optional[str] = None
            for s in subjects:
                if not isinstance(s, dict):
                    continue
                scheme = strip_text(s.get("scheme")).lower()
                if scheme == "category":
                    selected_code = strip_text(s.get("code"))
                    break

            anpa_category: List[Dict[str, Any]] = []
            if selected_code:
                # Map NTB -> STT department qcode, defaulting to fallback mapping if unknown
                mapped_code = DEFAULT_NTB_TO_STT_DEPT.get(
                    selected_code, DEFAULT_DEPT_FALLBACK_QCODE
                )
                hit = _cv_lookup(cv_depts, mapped_code)
                if hit:
                    # Use the CV hit
                    anpa_category = [
                        {"qcode": hit.get("qcode"), "name": hit.get("name")}  # type: ignore[dict-item]
                    ]
                else:
                    # CV not available or no match -> still honor the mapped qcode with a static name
                    anpa_category = [
                        {
                            "qcode": mapped_code,
                            "name": STATIC_DEPT_NAMES.get(
                                mapped_code, "Tiedotepalvelu"
                            ),
                        }
                    ]
            # If no category was selected at all, use static fallback
            if not anpa_category:
                anpa_category = [
                    {
                        "qcode": DEFAULT_DEPT_FALLBACK_QCODE,
                        "name": STATIC_DEPT_FALLBACK_NAME,
                    }
                ]
            # Assign exactly one entry
            item["anpa_category"] = anpa_category

        # 5) Filter subject field: remove category subjects, keep only topics and other schemes
        if isinstance(subjects, list) and "subject" in item:
            filtered_subjects = []
            for s in item.get("subject", []):
                if isinstance(s, dict):
                    scheme = strip_text(s.get("scheme", "")).lower()
                    # Keep everything except category subjects
                    if scheme != "category":
                        filtered_subjects.append(s)
            if filtered_subjects:
                item["subject"] = filtered_subjects
            else:
                item.pop("subject", None)

        return item


register_feed_parser(STTTTNINJSParseFeedParser.NAME, STTTTNINJSParseFeedParser())
