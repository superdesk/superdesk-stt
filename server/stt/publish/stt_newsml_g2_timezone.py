"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2 import STTNewsmLG2Formatter, ISODatetimeMixin


class STTNewsmLG2TimezoneFormatter(ISODatetimeMixin, STTNewsmLG2Formatter):

    type = "sttnewsmlg2timezone"
    name = "STT NewsML G2 timezone"
