"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2 import STTNewsmLG2Formatter, ISODatetimeMixing


class STTNewsmLG2TimezoneFormatter(ISODatetimeMixing, STTNewsmLG2Formatter):

    type = "sttnewsmlg2timezone"
    name = "STT NewsML G2 timezone"
