"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2 import TimezoneMixin
from .stt_newsml_g2_print import STTNewsmLG2PrintFormatter


class STTNewsmLG2PrintTimezoneFormatter(TimezoneMixin, STTNewsmLG2PrintFormatter):

    type = "sttnewsmlg2printtimezone"
    name = "STT NewsML G2 timezone for Print"
