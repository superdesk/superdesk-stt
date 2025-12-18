"""

STT version of the NewsML G2 Superdesk formatter - Tabulated variant

"""

from .stt_newsml_g2 import STTNewsmLG2Formatter, TabsMixin


class STTNewsmLG2TabsFormatter(TabsMixin, STTNewsmLG2Formatter):

    type = "sttnewsmlg2tabs"
    name = "STT NewsML G2 tabulated"
