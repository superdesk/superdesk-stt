"""Shared constants for STT parsers to ensure consistency across all feed parsers."""

# Vocabulary IDs used in Superdesk for STT content
STT_DEPARTMENT_VOCAB_ID = "sttdepartment"
STT_MEDIA_TOPICS_VOCAB_ID = "stt_media_topics"

# Department mappings used across parsers
# TT department code -> (STT integer value, STT string value)
DEPARTMENT_MAP = {
    "INR": (3, "Kotimaa"),
    "UTR": (14, "Ulkomaat"),
    "SPO": (16, "Urheilu"),
    "HBT": (6, "Muuta"),
    "RED": (13, "Toimituksille tiedoksi"),
    "TTL": (16, "Urheilu"),
    "PRM": (12, "Tiedotepalvelu"),
    "DOM": (11, "Talous"),
    "FOR": (11, "Talous"),
    "SPR": (16, "Urheilu"),
    "TBL": (16, "Urheilu"),
}

# Default department for fallback
DEFAULT_DEPARTMENT = (3, "Kotimaa")

# Common timezone used across STT parsers
STT_TIMEZONE = "Europe/Helsinki"
