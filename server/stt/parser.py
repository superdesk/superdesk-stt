from superdesk import etree as sd_etree
from superdesk.metadata.item import CONTENT_TYPE
from superdesk.io.registry import register_feed_parser
from superdesk.io.feed_parsers.stt_newsml import STTNewsMLFeedParser, STT_LOCATION_MAP


NA = 'N/A'


def get_subject_names(item):
    return [subj.get('name') for subj in item.get('subject', [])]


class STTParser(STTNewsMLFeedParser):
    NAME = 'sttnewsmlnewsroom'
    label = 'STT NewsML for Newsroom'

    def parse(self, xml, provider=None):
        items = super().parse(xml, provider)
        for item in items:
            item.setdefault('subject', [])
            if item.get('place'):
                for place in item['place']:
                    if place.get('name') and place.get('qcode') and place.get('scheme') == 'sttlocmeta':
                        item['subject'].append({
                            'name': place['name'],
                            'qcode': place['qcode'],
                            'scheme': place['scheme'],
                        })
                    for field in STT_LOCATION_MAP.values():
                        if place.get(field['name']) and place[field['name']] != NA and \
                                place[field['name']] not in get_subject_names(item):
                            item['subject'].append({
                                'name': place[field['name']],
                                'qcode': place[field['qcode']],
                                'scheme': field['name'],
                            })

            self.set_extra_fields(item, xml)
        return items

    def parse_inline_content(self, tree, item):
        html_elt = tree.find(self.qname('html'))
        body_elt = html_elt.find(self.qname('body'))
        body_elt = sd_etree.clean_html(body_elt)
        # replace <pre> with <p>
        for pre in body_elt.findall('.//pre'):
            pre.tag = 'p'
        # add target blank for all links
        for a in body_elt.findall('.//a'):
            a.attrib['target'] = '_blank'

        content = dict()
        content['contenttype'] = tree.attrib['contenttype']

        if len(body_elt) > 0:
            contents = [sd_etree.to_string(e, encoding='unicode', method="html") for e in body_elt]
            content['content'] = '\n'.join(contents)
        elif body_elt.text:
            content['content'] = '<p>' + body_elt.text + '</p>'
            content['format'] = 'xhtml/xml'

        if content.get('content'):
            content['content'] = content['content'].replace('&lt;endash&gt;-&lt;/endash&gt;', '-')

        return content

    def set_extra_fields(self, item, xml):
        """Adds extra fields"""

        # newsItem guid
        if 'uri' in item:
            item.setdefault('extra', {})['newsItem_guid'] = item['uri']

        # newsItem altId
        try:
            alt_id = xml.find(self.qname('contentMeta')).find(self.qname('altId')).text
            if alt_id:
                item.setdefault('extra', {})['sttidtype_textid'] = alt_id
        except AttributeError:
            pass

        # creator fields
        try:
            creator_node = xml.find(self.qname('contentMeta')).find(self.qname('creator'))

            if creator_node is not None:
                creator_name = creator_node.find(self.qname('name')).text
                if creator_name:
                    item.setdefault('extra', {})['creator_name'] = creator_name

                creator_id = creator_node.attrib.get('qcode')
                if creator_id:
                    item.setdefault('extra', {})['creator_id'] = creator_id
        except AttributeError:
            pass

        # filename
        try:
            link_node = xml.find(self.qname('itemMeta')).find(self.qname('link'))

            if link_node is not None:
                filename = link_node.find(self.qname('filename')).text
                if filename:
                    item.setdefault('extra', {})['filename'] = filename

        except AttributeError:
            pass

        # stt-topics, stt-events
        try:
            for subject in xml.find(self.qname('contentMeta')).findall(self.qname('subject')):
                values = subject.get('qcode', '').split(':')
                if values:
                    if values[0] == 'stt-topics':
                        item.setdefault('extra', {})['stt_topics'] = values[1]
                    elif values[0] == 'stt-events':
                        item.setdefault('extra', {})['stt_events'] = values[1]
        except AttributeError:
            pass

        # webprio
        try:
            for rating in xml.find(self.qname('contentMeta')).findall(self.qname('rating')):
                if rating.get('ratingtype') == 'sttrating:webprio':
                    value = rating.get('value')
                    if value:
                        item.setdefault('extra', {})['sttrating_webprio'] = int(value)
        except (AttributeError, ValueError):
            pass

        # imagetype
        try:
            def get_name_value(genre):
                return genre.find(self.qname('name')).text

            for genre in xml.find(self.qname('contentMeta')).findall(self.qname('genre')):
                if genre.get('qcode') == 'sttdescription:imagetype':
                    item.setdefault('extra', {}).setdefault('imagetype', {})['id'] = get_name_value(genre)
                elif genre.get('qcode') == 'sttdescription:imagetypename':
                    item.setdefault('extra', {}).setdefault('imagetype', {})['name'] = get_name_value(genre)
        except AttributeError:
            pass


register_feed_parser(STTParser.NAME, STTParser())
