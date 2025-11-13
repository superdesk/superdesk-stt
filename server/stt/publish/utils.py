def replace_special_characters(html: str) -> str:
    # Replace special Unicode characters as entities manually (ndhas, thinsp, tab, etc.)
    html = html.replace("\u2013", "&#8211;")
    html = html.replace("\t", "&#9;")
    html = html.replace("\u2009", "&#8201;")

    # Replace STT editorial agreements
    html = html.replace("---", "&#8211;")
    html = html.replace("¤", "&#8201;")

    return html
