import json
import logging
from typing import Any, Dict, Iterable, List, Optional

from lxml import etree
from lxml import html as lxml_html
from superdesk.io.feed_parsers.ninjs import NINJSFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.text_utils import sanitize_html
from superdesk.utc import local_to_utc

TIMEZONE = "Europe/Helsinki"

# CV paths (override via provider if desired)
MEDIA_TOPICS_CV = "vocab:stt_media_topics"
DEPT_CATEGORIES_CV = "vocab:stt-department-categories"

logger = logging.getLogger(__name__)


# ----------------------------- Helpers -------------------------------------


def _load_cv(path: str) -> List[Dict[str, Any]]:
    """Load a CV from Superdesk vocabularies."""
    if not path.startswith("vocab:"):
        raise ValueError("Only Superdesk vocabularies are supported in parser runtime")

    vocab_id = path.split(":", 1)[1]
    try:
        from superdesk import get_resource_service  # type: ignore

        svc = get_resource_service("vocabularies")
        if svc and hasattr(svc, "get_items"):
            items = svc.get_items(vocab_id)
            return items if isinstance(items, list) else []
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load vocabulary '%s' from service: %s", vocab_id, exc)

    return []


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def _cv_lookup(
    cv_items: Iterable[Dict[str, Any]], qcode: str
) -> Optional[Dict[str, Any]]:
    q = _norm(qcode).lower()
    if not q:
        return None
    for it in cv_items:
        if _norm(it.get("qcode", "")).lower() == q:
            return it
    return None


def _prepend_abstract(item: Dict[str, Any]) -> None:
    """Prepend description_html as the first <p> of body_html."""
    abstract = _norm(item.get("description_html"))
    if not abstract:
        return
    body = _norm(item.get("body_html"))
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
        self.is_sport_item = False

    # Keep your original behavior: read JSON and skip image items
    def can_parse(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            ninjs = json.load(f)
            return ninjs.get("type") != "image"

    def datetime(self, value):
        """When there is no timezone info, assume it's Helsinki timezone.

        Mirrors the behavior used in other STT parsers to ensure consistency.
        """
        parsed = super().datetime(value)
        if "+" not in value:
            return local_to_utc(TIMEZONE, parsed)
        return parsed

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
        return sanitized_html[5:-6]

    # --- NINJS -> Item (+ STT mappings) -------------------------------------

    def _transform_from_ninjs(self, ninjs):
        # drop heavy associations
        ninjs.pop("associations", None)

        # use core transform first
        item = super()._transform_from_ninjs(ninjs)

        # sport flag stays (if downstream needs it)
        self.is_sport_item = ninjs.get("sector") == "SPT"

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
                if _norm(s.get("scheme")).lower() not in {"topics", "topic"}:
                    continue
                hit = _cv_lookup(cv_topics, _norm(s.get("code")))
                if hit:
                    mapped_topics.append(hit)
            if mapped_topics:
                item["media_topics"] = mapped_topics
        # 4) Category mapping: subject(scheme: category) -> anpa_category
        if isinstance(subjects, list):
            cv_depts = _load_cv(DEPT_CATEGORIES_CV)
            mapped_cats: List[Dict[str, Any]] = []
            for s in subjects:
                if not isinstance(s, dict):
                    continue
                if _norm(s.get("scheme")).lower() != "category":
                    continue
                hit = _cv_lookup(cv_depts, _norm(s.get("code")))
                if hit:
                    # keep common structure {qcode, name}
                    mapped_cats.append(
                        {"qcode": hit.get("qcode"), "name": hit.get("name")}
                    )
            if mapped_cats:
                item["anpa_category"] = mapped_cats

        return item


register_feed_parser(STTTTNINJSParseFeedParser.NAME, STTTTNINJSParseFeedParser())
