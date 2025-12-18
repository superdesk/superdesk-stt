"""

STT version of the NewsML G2 Superdesk formatter for Print

"""

from .stt_newsml_g2 import STTNewsmLG2Formatter, PrintMixin


class STTNewsmLG2PrintFormatter(PrintMixin, STTNewsmLG2Formatter):

    type = "sttnewsmlg2print"
    name = "STT NewsML G2 for Print"
