"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2_print import STTNewsmLG2PrintFormatter, ISODatetimeMixin


class STTNewsmLG2PrintTimezoneFormatter(ISODatetimeMixin, STTNewsmLG2PrintFormatter):

    type = "sttnewsmlg2printtimezone"
    name = "STT NewsML G2 timezone for Print"
