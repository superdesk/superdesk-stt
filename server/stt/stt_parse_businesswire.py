from superdesk.etree import etree
from superdesk.io.feed_parsers import NewsMLOneFeedParser
from superdesk.io.registry import register_feed_parser

import logging

logger = logging.getLogger(__name__)

NS = {
    "xhtml": "http://www.w3.org/1999/xhtml",
}


class BusinessWireParser(NewsMLOneFeedParser):
    label = "BusinessWire"
    NAME = label.lower()

    COMPONENT_ROLE_MAPPING = {
        "Body": "body_html",
        "HeadLine": "headline",
        "Abstract": "abstract",
    }

    def parse_content(self, item, xml):
        # Extract External ID
        news_item_id = xml.findtext("NewsItem/Identification/NewsIdentifier/NewsItemId")
        if news_item_id:
            item["external_id"] = news_item_id.strip()

        # Extract Headline (Name)
        headline = xml.findtext(
            "NewsItem/NewsComponent/NewsComponent/NewsLines/HeadLine"
        )
        if headline:
            item["name"] = headline.strip()

        # Parse BusinessWire keywords metadata
        self.parse_bw_metadata(item, xml)

        # Extract SlugLine
        slugline = xml.findtext(
            "NewsItem/NewsComponent/NewsComponent/NewsLines/SlugLine"
        )
        if slugline:
            item["slugline"] = slugline.strip()

        # Extract ByLine
        byline = xml.findtext("NewsItem/NewsComponent/NewsComponent/NewsLines/ByLine")
        if byline:
            item["byline"] = byline.strip()

        # Extract Dateline
        dateline = xml.findtext(
            "NewsItem/NewsComponent/NewsComponent/NewsLines/DateLine"
        )
        if dateline:
            item["dateline"] = dateline.strip()

        components = xml.findall("NewsItem/NewsComponent/NewsComponent/NewsComponent")
        for component in components:
            role = component.find("Role")
            if role is None:
                continue

            role_name = role.get("FormalName")
            dest = self.COMPONENT_ROLE_MAPPING.get(role_name)
            if not dest:
                continue

            # Extract <body> for HTML content
            body = component.find(
                "ContentItem/DataContent/xhtml:html/xhtml:body", namespaces=NS
            )

            if dest == "headline":
                # Headline as plain text - store as both headline and name
                if body is not None:
                    headline_text = etree.tostring(
                        body, encoding="unicode", method="text"
                    ).strip()
                    item[dest] = headline_text
                    # Also store as name for compatibility
                    item["name"] = headline_text

            elif dest == "abstract":
                # Abstract as plain string (no XHTML expected)
                abstract = component.find("ContentItem/DataContent")
                if abstract is not None and abstract.text:
                    item[dest] = abstract.text.strip()

            elif dest == "body_html":
                # Join all XHTML elements in <body>
                if body is not None:
                    item[dest] = "\n".join(
                        [
                            etree.tostring(
                                elem, encoding="unicode", method="html"
                            ).replace(' xmlns="http://www.w3.org/1999/xhtml"', "")
                            for elem in body
                        ]
                    )

        # Flatten bw_keywords into keywords
        bw_keywords = item.get("extra", {}).get("bw_keywords", {})
        flat_keywords = [kw for group in bw_keywords.values() for kw in group]
        if flat_keywords:
            item["keywords"] = flat_keywords

        # Extract Subject tags
        subjects = []
        for subj in xml.findall(".//Subject"):
            formal = subj.get("FormalName")
            if formal:
                subjects.append(formal)
        if subjects:
            item["subject"] = subjects

    def parse_bw_metadata(self, item, xml):
        """Parse BusinessWire specific metadata"""
        # Initialize extra if not present
        if "extra" not in item:
            item["extra"] = {}

        # Find BWKeywords metadata - iterate through all Metadata elements
        for metadata in xml.findall(".//Metadata"):
            metadata_type = metadata.find("MetadataType")
            if (
                metadata_type is not None
                and metadata_type.get("FormalName") == "BWKeywords"
            ):
                bw_keywords = {}

                # Extract all BW keyword properties
                for prop in metadata.findall("Property"):
                    formal_name = prop.get("FormalName")
                    value = prop.get("Value")

                    if formal_name and value:
                        if formal_name not in bw_keywords:
                            bw_keywords[formal_name] = []
                        bw_keywords[formal_name].append(value)

                if bw_keywords:
                    item["extra"]["bw_keywords"] = bw_keywords

            elif (
                metadata_type is not None
                and metadata_type.get("FormalName") == "Securities Identifier"
            ):
                securities = {}

                for prop in metadata.findall("Property"):
                    formal_name = prop.get("FormalName")
                    value = prop.get("Value")

                    if formal_name and value:
                        securities[formal_name] = value

                if securities:
                    item["extra"]["securities"] = securities

    def populate_fields(self, item):
        # Call the superclass method to fill base fields
        super().populate_fields(item)
        return item

    def parse(self, xml, provider=None):
        """Override parse to return a list of items instead of a single item"""
        item = super().parse(xml, provider)
        return [item] if item else []


parser_instance = BusinessWireParser()
register_feed_parser(BusinessWireParser.NAME, parser_instance)
