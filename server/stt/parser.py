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

    def set_extra_fields(self, item, xml):
        """ Adds extra fields"""

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

            if creator_node:
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

            if link_node:
                filename = link_node.find(self.qname('filename')).text
                if filename:
                    item.setdefault('extra', {})['filename'] = filename

        except AttributeError:
            pass

        # stt-topics
        try:
            for subject in xml.find(self.qname('contentMeta')).findall(self.qname('subject')):
                values = subject.get('qcode', '').split(':')
                if len(values) and values[0] == 'stt-topics':
                    item.setdefault('extra', {})['stt_topics'] = values[1]
                    break
        except AttributeError:
            pass


register_feed_parser(STTParser.NAME, STTParser())
