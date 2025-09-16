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
MEDIA_TOPICS_CV = "stt_media_topics"
DEPT_CATEGORIES_CV = "stt-department-categories"

# Default department qcode when NTB category has no mapping (per ticket requirement)
DEFAULT_DEPT_FALLBACK_QCODE = "12"

logger = logging.getLogger(__name__)

# Map NTB category labels to STT department qcodes
DEFAULT_NTB_TO_STT_DEPT = {
    "Innenriks": "3",  # Kotimaa (Domestic)
    "Utenriks": "14",  # Ulkomaat (Foreign)
    "Sport": "16",  # Urheilu (Sports)
}


# ----------------------------- Helpers -------------------------------------


def _load_cv(vocab_id: str) -> List[Dict[str, Any]]:
    """Load active items from a Superdesk vocabulary.

    Args:
        vocab_id: Vocabulary identifier

    Returns:
        List of active vocabulary items, or empty list if not found/error

    The function prefers the `get_items` method (returns active items only),
    falling back to `find_one` with manual filtering when necessary.
    """

    try:
        from superdesk import get_resource_service  # type: ignore

        service = get_resource_service("vocabularies")
        if not service:
            logger.warning("Vocabularies service not available")
            return []

        # Preferred method: get_items returns active items only
        if hasattr(service, "get_items") and callable(service.get_items):
            items = service.get_items(vocab_id)
            return _ensure_list(items)

        # Fallback: use find_one and filter manually
        if hasattr(service, "find_one") and callable(service.find_one):
            return _load_vocab_with_filtering(service, vocab_id)

        logger.warning("Vocabularies service missing required methods")
        return []

    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load vocabulary '%s': %s", vocab_id, exc)
        return []


def _ensure_list(items: Any) -> List[Dict[str, Any]]:
    """Ensure the result is a list of dictionaries."""
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _load_vocab_with_filtering(service: Any, vocab_id: str) -> List[Dict[str, Any]]:
    """Load vocabulary using find_one and filter active items."""
    vocab = service.find_one(req=None, _id=vocab_id)
    if not isinstance(vocab, dict):
        return []

    items = vocab.get("items") or []
    if not isinstance(items, list):
        return []

    # Filter by is_active if the field exists
    if items and isinstance(items[0], dict) and "is_active" in items[0]:
        return [
            item
            for item in items
            if isinstance(item, dict) and item.get("is_active", True)
        ]

    # Return all items if no is_active field
    return [item for item in items if isinstance(item, dict)]


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
        # Override any anpa_category set by parent class with our custom mapping
        if isinstance(subjects, list):
            cv_depts = _load_cv(DEPT_CATEGORIES_CV)
            mapped_cats: List[Dict[str, Any]] = []
            for s in subjects:
                if not isinstance(s, dict):
                    continue
                raw_code = strip_text(s.get("code")) or DEFAULT_DEPT_FALLBACK_QCODE
                mapped_code = DEFAULT_NTB_TO_STT_DEPT.get(
                    raw_code, DEFAULT_DEPT_FALLBACK_QCODE
                )
                hit = _cv_lookup(cv_depts, mapped_code)
                if hit:
                    mapped_cats.append(
                        {"qcode": hit.get("qcode"), "name": hit.get("name")}
                    )
            # Always set anpa_category (override parent), even if empty
            if mapped_cats:
                item["anpa_category"] = mapped_cats
            else:
                # Remove anpa_category if no category subjects found
                item.pop("anpa_category", None)

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
