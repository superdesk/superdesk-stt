import html


def get_headline_for_item(translated_item):
    # headline should be english version like
    """
    Sebastian Aho scored half of the Ottawa Senators' goals against the Carolina Hurricanes*** TRANSLATED ***
    """
    headline = translated_item.get("translated_headline_en", "")
    # add "*** TRANSLATED ***" to the end of the headline
    if headline and not headline.endswith("*** TRANSLATED ***"):
        headline += " *** TRANSLATED ***"
    return headline


def get_body_html_for_item(translated_item, item):
    # body html needs to start like this:
    """
    <h2>AUTOMATED TRANSLATION FROM FINNISH NEWS FEED</h2>

    *** DISCLAIMER: THIS IS AN AUTOMATED TRANSLATION FROM FINNISH ***
    """
    body_html = "<h2>AUTOMATED TRANSLATION FROM FINNISH NEWS FEED</h2>"
    body_html += "<p><b>*** DISCLAIMER: THIS IS AN AUTOMATED TRANSLATION FROM FINNISH ***</b></p>"
    # then add english version of the text
    body_html += f"{translated_item.get('translated_text_en', '')}"
    # then add this text:
    """
    *** ANSVARSFRISKRIVNING: DETTA ÄR EN AUTOMATISK ÖVERSÄTTNING FRÅN FINSKA ***
    """
    body_html += "<p><b>*** ANSVARSFRISKRIVNING: DETTA ÄR EN AUTOMATISK ÖVERSÄTTNING FRÅN FINSKA ***</b></p>"
    # and then add swedish version of the headline
    translated_headline_sv = translated_item.get("translated_headline_sv", "")
    if translated_headline_sv:
        body_html += f"<h2>{html.escape(translated_headline_sv)}</h2>"
    # and then add swedish version of the text
    body_html += f"{translated_item.get('translated_text_sv', '')}"
    # then add:
    """
    *** ORIGINAL TEXT ***
    """
    body_html += "<p><b>*** ORIGINAL TEXT ***</b></p>"
    # and then add the original headline
    original_headline = translated_item.get("original_headline", "")
    if original_headline:
        body_html += f"<h2>{html.escape(original_headline)}</h2>"
    # and then add the original text
    body_html += f"{item.get('body_html', '')}"
    # and return the body html
    return body_html
