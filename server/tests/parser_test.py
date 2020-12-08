from tests import TestCase


class STTParseTestCase(TestCase):
    fixture = 'stt_newsml_location_test.xml'

    def test_location_parsing(self):
        subject = self.item['subject']

        locality = next((subj for subj in subject if subj.get('qcode') == '392'))
        self.assertEqual('Tallinna', locality['name'])
        self.assertEqual('locality', locality['scheme'])

        with self.assertRaises(StopIteration):
            next((subj for subj in subject if subj.get('scheme') == 'state'))

        country = next((subj for subj in subject if subj.get('qcode') == '238'))
        self.assertEqual('Viro', country['name'])
        self.assertEqual('country', country['scheme'])

        region = next((subj for subj in subject if subj.get('qcode') == '150'))
        self.assertEqual('Eurooppa', region['name'])
        self.assertEqual('world_region', region['scheme'])

        rich = next((subj for subj in subject if subj.get('qcode') == '20016'))
        self.assertEqual('Myanmar', rich['name'])
        self.assertEqual('sttlocmeta', rich['scheme'])

        rich_reg = next((subj for subj in subject if subj.get('qcode') == '142'))
        self.assertEqual('Aasia', rich_reg['name'])
        self.assertEqual('world_region', rich_reg['scheme'])

    def test_extra_fields(self):
        self.assertEqual(self.item['urgency'], 3)
        self.assertEqual(self.item['extra']['sttidtype_textid'], '117616076')
        self.assertEqual(self.item['extra']['newsItem_guid'], 'urn:newsml:stt.fi:20170131:101159380')
        self.assertEqual(self.item['extra']['creator_name'], 'Areva Mari')
        self.assertEqual(self.item['extra']['creator_id'], 'stteditorid:26634')
        self.assertEqual(self.item['extra']['filename'], '1029359.jpg')
        self.assertEqual(self.item['extra']['stt_topics'], '490933')
        self.assertEqual(self.item['extra']['stt_events'], '213870')
        self.assertEqual(self.item['extra']['sttrating_webprio'], 4)
        self.assertEqual(self.item['extra']['imagetype']['id'], '20')
        self.assertEqual(self.item['extra']['imagetype']['name'], 'Kuvaaja paikalla')

    def test_preserve_links(self):
        body_html = self.item['body_html']
        expected_link_text = '<a href="https://coronavirus.jhu.edu/map.html" target="_blank">Johns Hopkins </a>'
        self.assertIn(expected_link_text, body_html)


class STTParsePRETestCase(TestCase):
    fixture = 'stt_newsml_pre_test.xml'

    def test_replace_pre_with_p(self):
        body_html = self.item['body_html']
        self.assertIn('<p>It used to be a pre</p>', body_html)
