from superdesk import etree as sd_etree
from superdesk.io.registry import register_feed_parser
from superdesk.io.feed_parsers.stt_newsml import STTNewsMLFeedParser

from .common import STTParserMixin, remove_date_portion_from_id


NA = "N/A"


def get_subject_names(item):
    return [subj.get("name") for subj in item.get("subject", [])]


class STTParser(STTParserMixin, STTNewsMLFeedParser):
    NAME = "sttnewsmlnewsroom"
    label = "STT NewsML for Newsroom"

    async def parse(self, xml, provider=None):
        items = await super().parse(xml, provider)
        for item in items:
            item.setdefault("subject", [])
            if item.get("place"):
                self.parse_place(item)
            await self.set_extra_fields(item, xml)
        return items

    def parse_inline_content(self, tree, item):
        html_elt = tree.find(self.qname("html"))
        body_elt = html_elt.find(self.qname("body"))
        body_elt = sd_etree.clean_html(body_elt)
        # replace <pre> with <p>
        for pre in body_elt.findall(".//pre"):
            pre.tag = "p"
        # add target blank for all links
        for a in body_elt.findall(".//a"):
            a.attrib["target"] = "_blank"

        content = dict()
        content["contenttype"] = tree.attrib["contenttype"]

        if len(body_elt) > 0:
            contents = [
                sd_etree.to_string(e, encoding="unicode", method="html")
                for e in body_elt
            ]
            content["content"] = "\n".join(contents)
        elif body_elt.text:
            content["content"] = "<p>" + body_elt.text + "</p>"
            content["format"] = "xhtml/xml"

        if content.get("content"):
            content["content"] = content["content"].replace(
                "&lt;endash&gt;-&lt;/endash&gt;", "-"
            )

        return content

    async def set_extra_fields(self, item, xml):
        """Adds extra fields"""

        # newsItem guid
        if "uri" in item:
            item.setdefault("extra", {})["newsItem_guid"] = item["uri"]
            item["uri"] = remove_date_portion_from_id(item["uri"])

        # newsItem altId
        try:
            for alt_id in xml.find(self.qname("contentMeta")).findall(
                self.qname("altId")
            ):
                if alt_id.get("type") == "sttidtype:textid" and alt_id.text:
                    # textid is STT's Article ID
                    item.setdefault("extra", {})["sttidtype_textid"] = alt_id.text
        except AttributeError:
            pass

        # creator fields
        try:
            creator_node = xml.find(self.qname("contentMeta")).find(
                self.qname("creator")
            )

            if creator_node is not None:
                creator_name = creator_node.find(self.qname("name")).text
                if creator_name:
                    item.setdefault("extra", {})["creator_name"] = creator_name

                creator_id = creator_node.attrib.get("qcode")
                if creator_id:
                    item.setdefault("extra", {})["creator_id"] = creator_id
        except AttributeError:
            pass

        # filename
        try:
            link_node = xml.find(self.qname("itemMeta")).find(self.qname("link"))

            if link_node is not None:
                filename = link_node.find(self.qname("filename")).text
                if filename:
                    item.setdefault("extra", {})["filename"] = filename

        except AttributeError:
            pass

        subjects = xml.find(self.qname("contentMeta")).findall(self.qname("subject"))
        self.parse_subjects(item, subjects)

        # webprio
        try:
            for rating in xml.find(self.qname("contentMeta")).findall(
                self.qname("rating")
            ):
                if rating.get("ratingtype") == "sttrating:webprio":
                    value = rating.get("value")
                    if value:
                        item.setdefault("extra", {})["sttrating_webprio"] = int(value)
        except (AttributeError, ValueError):
            pass

        # imagetype
        try:

            def get_name_value(genre):
                return genre.find(self.qname("name")).text

            for genre in xml.find(self.qname("contentMeta")).findall(
                self.qname("genre")
            ):
                if genre.get("qcode") == "sttdescription:imagetype":
                    item.setdefault("extra", {}).setdefault("imagetype", {})["id"] = (
                        get_name_value(genre)
                    )
                elif genre.get("qcode") == "sttdescription:imagetypename":
                    item.setdefault("extra", {}).setdefault("imagetype", {})["name"] = (
                        get_name_value(genre)
                    )
        except AttributeError:
            pass

    def parse_content_meta(self, tree, item):
        super().parse_content_meta(tree, item)
        if item.get("source"):
            file_sources = item["source"].split("-")
            cv_sources = self.get_cv_items("sttsource")
            for cv_source in cv_sources:
                if cv_source.get("qcode") in file_sources:
                    item.setdefault("subject", []).append(cv_source)

    def parse_place(self, item):
        place_list = []
        places_lookup = {p["qcode"]: p for p in self.get_cv_items("locators")}
        for place in item["place"]:
            if place.get("country_code"):
                country_code = "sttcountry:" + place["country_code"]
                if places_lookup.get(country_code):
                    place_list.append(places_lookup[country_code])
            if place.get("locality_code"):
                city_code = "sttcity:" + place["locality_code"]
                if places_lookup.get(city_code):
                    place_list.append(places_lookup[city_code])
        item["place"] = place_list


register_feed_parser(STTParser.NAME, STTParser())
