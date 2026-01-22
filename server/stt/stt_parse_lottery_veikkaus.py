"""Veikkaus lottery plain‑text feed parser.

This parser handles plain text (and legacy XML‑wrapped text) drops from Veikkaus
and produces a single Superdesk ingest item.

Refactored to be Black/Flake8 compliant.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import chardet
from superdesk.io.feed_parsers import FeedParser
from superdesk.io.registry import register_feed_parser

# Regex for legacy XML wrapper: <root><p> ... </p></root>
XML_WRAP_RE = re.compile(r"^\s*<root>\s*<p>(.*)</p>\s*</root>\s*$", re.S)

# Common encoding issues in Finnish text. Intentionally avoid empty-string keys.
ENCODING_FIXES: Dict[str, str] = {
    "l‰htˆ": "lähtö",
    "‰": "ä",
    "ˆ": "ö",
    "Œ": "Ä",
    # Removed invalid empty-string key that caused runaway replacements.
    "…": "å",
    "€": "€",  # Euro symbol sometimes gets corrupted but keep for completeness
}

# Fallback encodings typically seen in Finnish content
FALLBACK_ENCODINGS: List[str] = [
    "utf-8",
    "iso-8859-1",
    "windows-1252",
    "cp1252",
]


def detect_and_read_file(file_path: str) -> str:
    """Detect file encoding and return decoded text with common fixes applied.

    Args:
        file_path: Path to the source file.

    Returns:
        The decoded and post-processed file content as a string.
    """
    try:
        with open(file_path, "rb") as fh:
            raw = fh.read()

        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "utf-8"
        confidence = float(detected.get("confidence") or 0.0)

        if confidence > 0.7:
            try:
                return fix_encoding_issues(raw.decode(encoding))
            except UnicodeDecodeError:
                pass

        for enc in FALLBACK_ENCODINGS:
            try:
                text = raw.decode(enc)
                return fix_encoding_issues(text)
            except UnicodeDecodeError:
                continue

        return fix_encoding_issues(raw.decode("utf-8", errors="replace"))
    except Exception:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            return fix_encoding_issues(fh.read())


def fix_encoding_issues(text: str) -> str:
    """Apply simple replacement rules for common mojibake in Finnish text."""
    fixed = text
    for wrong, correct in ENCODING_FIXES.items():
        if wrong:  # guard against accidental empty keys
            fixed = fixed.replace(wrong, correct)
    return fixed


def to_body_html(lines: List[str]) -> str:
    """Wrap each line in its own <p>...</p> block."""
    while lines and lines[-1] == "":
        lines.pop()

    content = "<br/>\n".join(line.rstrip() for line in lines)

    # Remove unwanted characters:
    # Replace \u2020 with thinspace (\u2009)
    content = content.replace("\u2020", "\u2009")

    return f"<p>{content}</p>"


class VeikkausTextFeedParser(FeedParser):
    """Parser for Veikkaus lottery plain-text drops."""

    NAME = "veikkaus_text"
    label = "STT Veikkaus Text Parser"

    def can_parse(self, file_path: str) -> bool:
        """Accept `.txt` or `.xml` files or text matching the legacy wrapper."""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in {".txt", ".xml"}:
                return True

            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                sample = fh.read(4096)
            return bool(XML_WRAP_RE.match(sample))
        except Exception:
            return False

    async def parse(
        self, file_path: str, provider: Optional[dict] = None
    ) -> List[Dict[str, Any]]:
        """Parse the Veikkaus file into a Superdesk ingest item.

        Returns a list with a single item.
        """
        # Provider is part of the base signature; not used here.
        del provider

        raw = detect_and_read_file(file_path)
        match = XML_WRAP_RE.match(raw)
        text = match.group(1) if match else raw

        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        headline = f"*** {(next((ln.strip() for ln in lines if ln.strip()), '') or 'Veikkaus')} ***"
        body_html = to_body_html(lines)

        # create unique guid as urn:filename_timestamp
        filename = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = int(datetime.now(timezone.utc).timestamp())
        guid = f"urn:{filename}_{timestamp}"

        item: Dict[str, Any] = {
            "guid": guid,
            "type": "text",
            "headline": headline,
            "body_html": body_html,
            "description_text": filename,
            "anpa_category": [{"qcode": "8", "name": "Peliuutiset"}],
            "genre": [{"qcode": "sttgenre:1", "name": "Uutinen"}],
            "subject": [
                {"qcode": "STT", "name": "STT", "scheme": "sttsource"},
                {"qcode": "Veikkaus", "name": "Veikkaus", "scheme": "sttsource"},
            ],
            "urgency": 3,
            "versioncreated": datetime.now(timezone.utc),
            "extra": {
                "veikkaus": {
                    "filename": filename,
                }
            },
            "slugline": "Veikkaus",
            # "keywords": ["Veikkaus", "lottery"],
        }

        return [item]


register_feed_parser(VeikkausTextFeedParser.NAME, VeikkausTextFeedParser())
