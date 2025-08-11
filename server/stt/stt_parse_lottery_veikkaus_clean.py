# server/stt/io/feed_parsers/veikkaus_text.py
# -*- coding: utf-8 -*-
"""
Superdesk feed parser for Veikkaus lottery plain-text drops.

Accepts either raw text files or historical <root><p>...</p></root> XML-wrapped text.
Maps metadata according to the legacy Neo import rules:
    - Headline = first non-empty line
    - Description = filename
    - Department = "Peliuutiset" (stored under extra.veikkaus.department)
    - Source = "STT" (original_source)
    - Desk = "Kotimaa" (stored under extra.veikkaus.desk)
    - Priority = 4 (urgency)
    - Body_html = full content with <br/> for line breaks
"""

import os
import re
import logging
from typing import List, Optional

from superdesk.io.feed_parsers import FeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.metadata.utils import generate_tag_from_url

logger = logging.getLogger(__name__)

XML_WRAP_RE = re.compile(r"^\s*<root>\s*<p>(.*)</p>\s*</root>\s*$", re.S)

# Common encoding issues in Finnish text - mapping corrupted chars to correct ones
ENCODING_FIXES = {
    "l‰htˆ": "lähtö",
    "‰": "ä",
    "ˆ": "ö",
}


def fix_encoding_issues(text: str) -> str:
    """
    Fix common encoding issues in Finnish text.
    
    :param text: text with potential encoding issues
    :return: text with encoding issues fixed
    """
    fixed_text = text
    for wrong, correct in ENCODING_FIXES.items():
        fixed_text = fixed_text.replace(wrong, correct)
    return fixed_text


def to_body_html(lines: List[str]) -> str:
    """
    Wrap the entire text into one <p>...</p> block with <br/> between original lines.

    :param lines: list of strings (original lines of the file)
    :return: HTML string
    """
    # Remove trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()
    content = "<br/>\n".join(line.rstrip() for line in lines)
    return f"<p>{content}</p>"


class VeikkausTextFeedParser(FeedParser):
    """Parser for Veikkaus lottery plain-text drops."""

    NAME = "veikkaus_text"
    label = "STT Veikkaus Text Parser"

    def can_parse(self, file_path: str) -> bool:
        """
        Accept .txt or .xml files, or detect XML-wrapped text via regex.

        :param file_path: path to the candidate file
        :return: True if this parser can handle it
        """
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".txt", ".xml"):
                return True

            with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                sample = file.read(4096)
            return bool(XML_WRAP_RE.match(sample))
        except Exception:
            logger.exception("Veikkaus can_parse failed")
            return False

    def parse(self, file_path: str, provider: Optional[dict] = None) -> list:
        """
        Parse the Veikkaus file into a Superdesk ingest item.

        :param file_path: path to file to parse
        :param provider: optional provider configuration
        :return: list of parsed items (always length 1 here)
        """
        # Read file with encoding handling
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            raw = file.read()
        
        # Apply encoding fixes
        raw = fix_encoding_issues(raw)

        # Unwrap the old <root><p>...</p></root> if present
        match = XML_WRAP_RE.match(raw)
        text = match.group(1) if match else raw

        # Normalize and split
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        headline = (
            next((text_line.strip() for text_line in lines if text_line.strip()), "")
            or "Veikkaus"
        )
        body_html = to_body_html(lines)

        filename = os.path.basename(file_path)
        guid = generate_tag_from_url(filename, "urn")

        item = {
            "guid": guid,
            "type": "text",
            "headline": headline,
            "body_html": body_html,
            "description_text": filename,
            "original_source": "STT",
            "urgency": 4,
            "pubstatus": "usable",
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
