"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2 import TimezoneMixin
from .stt_newsml_g2_tabs import STTNewsmLG2TabsFormatter


class STTNewsmLG2TabsTimezoneFormatter(TimezoneMixin, STTNewsmLG2TabsFormatter):

    type = "sttnewsmlg2tabstimezone"
    name = "STT NewsML G2 tabulated timezone"
