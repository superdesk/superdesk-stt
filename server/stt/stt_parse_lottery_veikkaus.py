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
from superdesk.metadata.utils import generate_tag_from_url

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
    """Wrap all lines in a single paragraph and separate with `<br/>`.

    Trailing blank lines are removed.
    """
    while lines and not lines[-1].strip():  # trim trailing blanks
        lines.pop()
    content = "<br/>\n".join(line.rstrip() for line in lines)
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

        print("PARSING", file_path)

        raw = detect_and_read_file(file_path)

        print("RAW", raw)

        match = XML_WRAP_RE.match(raw)
        text = match.group(1) if match else raw

        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        headline = next((ln.strip() for ln in lines if ln.strip()), "") or "Veikkaus"
        body_html = to_body_html(lines)

        filename = os.path.basename(file_path)
        guid = generate_tag_from_url(filename, "urn")

        item: Dict[str, Any] = {
            "guid": guid,
            "type": "text",
            "headline": headline,
            "body_html": body_html,
            "description_text": filename,
            "original_source": "STT",
            "urgency": 4,
            "pubstatus": "usable",
            "versioncreated": datetime.now(timezone.utc),
            "extra": {
                "veikkaus": {
                    "department": "Peliuutiset",
                    "desk": "Kotimaa",
                    "filename": filename,
                }
            },
            "slugline": "Veikkaus",
            "keywords": ["Veikkaus", "lottery"],
        }

        return [item]


register_feed_parser(VeikkausTextFeedParser.NAME, VeikkausTextFeedParser())
