"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2 import TabsMixin, TimezoneMixin
from .stt_newsml_g2_print import STTNewsmLG2PrintFormatter


class STTNewsmLG2PrintTabsTimezoneFormatter(
    TabsMixin, TimezoneMixin, STTNewsmLG2PrintFormatter
):

    type = "sttnewsmlg2printtabstimezone"
    name = "STT NewsML G2 tabulated timezone for Print"
