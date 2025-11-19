def encode_special_characters(html: str) -> str:
    """Replace special unicode characters and STT specific sequences with html entities."""
    # Replace special Unicode characters as entities manually (ndhas, thinsp, tab, etc.)
    html = html.replace("\u2013", "&#8211;")
    html = html.replace("\t", "&#9;")
    html = html.replace("\u2009", "&#8201;")

    # Replace STT editorial agreements
    html = html.replace("---", "&#8211;")
    html = html.replace("¤", "&#8201;")

    return html


def decode_special_characters(html: str) -> str:
    """Replace html entities with unicode characters."""
    html = html.replace("&#9;", "\t")
    html = html.replace("&#8211;", "\u2013")
    html = html.replace("&#8201;", "\u2009")
    return html
