"""

STT version of the NewsML G2 Superdesk formatter - Tabulated variant

"""

from .stt_newsml_g2 import TabsMixin
from .stt_newsml_g2_print import STTNewsmLG2PrintFormatter


class STTNewsmLG2PrintTabsFormatter(TabsMixin, STTNewsmLG2PrintFormatter):

    type = "sttnewsmlg2printtabs"
    name = "STT NewsML G2 tabulated for Print"
