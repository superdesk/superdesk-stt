"""

STT version of the NewsML G2 Superdesk formatter

"""

from .stt_newsml_g2_print import ISODatetimeMixin
from .stt_newsml_g2_print_tabs import STTNewsmLG2PrintTabsFormatter


class STTNewsmLG2TabsTimezoneFormatter(ISODatetimeMixin, STTNewsmLG2PrintTabsFormatter):

    type = "sttnewsmlg2printtabstimezone"
    name = "STT NewsML G2 tabulated timezone for Print"
