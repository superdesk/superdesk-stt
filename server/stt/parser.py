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
        return items


register_feed_parser(STTParser.NAME, STTParser())
