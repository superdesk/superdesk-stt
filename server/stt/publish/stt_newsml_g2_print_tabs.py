"""

STT version of the NewsML G2 Superdesk formatter - Tabulated variant

"""

import re
import logging

from .stt_newsml_g2_print import STTNewsmLG2PrintFormatter

logger = logging.getLogger(__name__)


class STTNewsmLG2PrintTabsFormatter(STTNewsmLG2PrintFormatter):

    type = "sttnewsmlg2printtabs"
    name = "STT NewsML G2 tabulated for Print"

    def format_contentSet_body(self, article, body):
        """Override body formatting to convert HTML tables to tab-separated text.

        :param dict article: The article to format
        :param Element body: The body element to append content to
        """
        # Body
        if article.get("body_html", None):

            # Find all rows
            rows = re.findall(
                r"<tr.*?>(.*?)</tr>", article.get("body_html"), flags=re.DOTALL
            )

            lines = []
            for row in rows:

                # Find all <td> in a row
                cells = re.findall(r"<td.*?>(.*?)</td>", row, flags=re.DOTALL)

                cleanCells = []
                for cell in cells:

                    # Clean out unnecessary tags
                    text = re.sub(r"<.*?>", "", cell).strip()

                    # column has ndash in it
                    if "–" in text:
                        parts = re.split(r"–", text, maxsplit=1)
                        cleanCells.append(parts[0] + "–")
                        cleanCells.append(parts[1])
                    else:
                        cleanCells.append(text)

                # Join with tab characters
                lines.append("\t".join(cleanCells))

            # Join rows with newlines
            paragraph = "</p>\n<p>".join(lines)
            replacement = f"<p>{paragraph}</p>"

            # replace HTML table with tabbed text
            bodyHtml = article.get("body_html", None)

            if bodyHtml:
                resultHTML = re.sub(
                    "<table.*?>.*?</table>", replacement, bodyHtml, flags=re.DOTALL
                )

                # Update the article's body_html with the converted version
                article = article.copy()
                article["body_html"] = resultHTML

        # Call parent class method to handle the rest of the formatting
        super().format_contentSet_body(article, body)
