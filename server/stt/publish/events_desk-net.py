import logging
import pytz

from lxml import etree
from lxml.etree import SubElement
from superdesk.resource_fields import VERSION
from superdesk.publish.formatters import Formatter
from superdesk.errors import FormatterError
from superdesk.publish_async.utils import generate_sequence_number

XML_LANG = '{http://www.w3.org/XML/1998/namespace}lang'
STT_FORMATVERSION = '{http://www.stt-lehtikuva.fi/NewsML}formatversion'
XSI_SCHEMALOCATION = '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'

logger = logging.getLogger(__name__)


class STTEventDeskNetFormatter(Formatter):

    ENCODING = 'UTF-8'
    XML_ROOT = '<?xml version="1.0" encoding="{}"?>\n'.format(ENCODING)

    type = 'stteventdesknet'
    name = 'STT Event Desk-Net'

    _message_nsmap = {
        None: 'http://iptc.org/std/nar/2006-10-01/',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'stt': 'http://www.stt-lehtikuva.fi/NewsML'
    }

    # Helpers: department
    def format_department(self, article, parentNode):

        # Department
        # Map 'anpa_category' into subject tag with correct attributes
        # Events should only have one value in 'anpa_category' but this
        # solution could also handle multiple values.
        anpa_category = article.get('anpa_category', {})
        for s in anpa_category:
            department = SubElement(parentNode, 'subject', attrib={'type': 'cpnat:abstract', 'qcode': 'sttdepartment:' + s.get('qcode', '')})
            departmentName = SubElement(department, 'name')
            departmentName.text = s.get('name', '')

    # Format itemMeta
    def format_itemMeta(self, article, parentNode):

        itemMeta = SubElement(parentNode, 'itemMeta')

        SubElement(itemMeta, 'itemClass', attrib={'qcode': 'cinat:concept'})
        SubElement(itemMeta, 'provider', attrib={'literal': 'STT'})

        versionCreated = SubElement(itemMeta, 'versionCreated')
        versionCreated.text = article.get('versioncreated', None).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y-%m-%dT%H:%M:%S')
        firstCreated = SubElement(itemMeta, 'firstCreated')
        firstCreated.text = article.get('firstcreated', None).astimezone(pytz.timezone('Europe/Helsinki')).strftime("%Y-%m-%dT%H:%M:%S")

        SubElement(itemMeta, 'pubstatus', attrib={'qcode': 'stat:usable'})

        # State 'scheduled': julkaistu
        # State 'killed': poisto
        state = article.get('state', '')
        match state:
            case 'scheduled':
                SubElement(itemMeta, 'signal', attrib={'qcode': 'sttinstruct:add'})
            case 'killed':
                SubElement(itemMeta, 'signal', attrib={'qcode': 'sttinstruct:remove'})
            case _:
                SubElement(itemMeta, 'signal', attrib={'qcode': 'sttinstruct:add'})

    # Format contentMeta
    def format_contentMeta(self, article, parentNode):

        contentMeta = SubElement(parentNode, 'contentMeta')

        contentCreated = SubElement(contentMeta, 'contentCreated')
        contentCreated.text = article.get('firstcreated', None).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y-%m-%dT%H:%M:%S')

        contentModified = SubElement(contentMeta, 'contentModified')
        contentModified.text = article.get('versioncreated', None).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y-%m-%dT%H:%M:%S')

        infoSource = SubElement(contentMeta, 'infoSource', attrib={'qcode': 'sttsource:1'})
        infoSourceName = SubElement(infoSource, 'name')
        infoSourceName.text = 'STT'
        contributor = SubElement(contentMeta, 'contributor')
        contributorName = SubElement(contributor, 'name')
        contributorName.text = 'STT'

        SubElement(contentMeta, 'language', attrib={'tag': 'fi-FI'})

    # Format location
    def format_location(self, article, parentNode):

        locations = article.get('location', {})

        for loc in locations:

            location = SubElement(parentNode, 'location')
            locationName = SubElement(location, 'name')
            locationName.text = loc['name']

            if 'address' in loc:

                POIDetails = SubElement(location, 'POIDetails')
                address = SubElement(POIDetails, 'address')

                if 'line' in loc['address']:
                    addressLine = SubElement(address, 'line')
                    addressLine.text = loc['address']['line'][0]

                if 'city' in loc['address']:
                    locality = SubElement(address, 'locality')
                    localityName = SubElement(locality, 'name')
                    localityName.text = loc['address']['city']

                if 'country' in loc['address']:
                    country = SubElement(address, 'country')
                    countryName = SubElement(country, 'name')
                    countryName.text = loc['address']['country']

                if 'postal_code' in loc['address']:
                    postalCode = SubElement(address, 'postalCode')
                    postalCode.text = loc['address']['postal_code']

            """
            if addressDict:
                POIDetails = SubElement(location, 'POIDetails')
                address = SubElement(POIDetails, 'address')
                addressLine = SubElement(address, 'line')
                addressLine.text = addressDict.get('line', '')
                locality = SubElement(address, 'locality')
                localityName = SubElement(locality, 'name')
                localityName.text = addressDict.get('city','')
                country = SubElement(address, 'country')
                countryName = SubElement(country, 'name')
                countryName.text = addressDict.get('country','')
                postalCode = SubElement(address, 'postalCode')
                postalCode.text = addressDict.get('postal_code', '')
            """

    # Format eventDetails
    def format_eventDetails(self, article, parentNode):

        eventDetails = SubElement(parentNode, 'elementDetails')

        dates = SubElement(eventDetails, 'dates')
        datesDict = article.get('dates', {})

        if datesDict:
            if datesDict.get('all_day', '') is True:
                startDate = SubElement(dates, 'start')
                startDate.text = datesDict.get('start', {}).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y-%m-%d')
                endDate = SubElement(dates, 'end')
                endDate.text = datesDict.get('end', {}).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y-%m-%d')
            else:
                startDate = SubElement(dates, 'start')
                startDate.text = datesDict.get('start', {}).astimezone(pytz.timezone('Europe/Helsinki')).isoformat(timespec='seconds')

                if datesDict.get('no_end_time', '') is True:
                    endDate = SubElement(dates, 'end')
                    endDate.text = datesDict.get('end', {}).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y-%m-%d')
                else:
                    endDate = SubElement(dates, 'end')
                    endDate.text = datesDict.get('end', {}).astimezone(pytz.timezone('Europe/Helsinki')).isoformat(timespec='seconds')

        # IPTC category of event
        subjecs = article.get('subject', {})
        for s in subjecs:
            if s.get('scheme') == 'topics':
                subj = SubElement(eventDetails, "subject", attrib={"type": "cpnat:abstract", "qcode": 'sttsubject:' + s.get('qcode', '')})
                subjName = SubElement(subj, 'name')
                subjName.text = s.get('name', '')

        # Registration: ilmoittautuminen (Neossa: järjestäjän antamaa lisätietoa)
        # Mistä haetaan tähän tieto Superdeskissä?
        registration = SubElement(eventDetails, 'registration')
        registration.text = article.get('registration_details', '')

        self.format_location(article, eventDetails)

        # Tarvitaanko tätä millä tasolla?
        """
        location = SubElement(eventDetails,'location',attrib={'qcode':'sttlocationalias:12345'})
        locationName = SubElement(location, 'name')
        locationName.text = 'Westmont'

        broader = SubElement(location,'broader', attrib={'type':'cpnat:geoArea','qcode':'sttcity:1234'})
        broaderName = SubElement(broader, 'name')
        broaderName.text = 'Westmont'

        broader2 = SubElement(location,'broader', attrib={'type':'cpnat:geoArea','qcode':'sttstate:1234'})
        broader2Name = SubElement(broader2, 'name')
        broader2Name.text = 'Illinois'

        broader3 = SubElement(location,'broader', attrib={'type':'cpnat:geoArea','qcode':'sttcountry:1234'})
        broader3Name = SubElement(broader3, 'name')
        broader3Name.text = 'Yhdysvallat'
        SubElement(broader3, 'sameAs', attrib={'qcode':'iso3166-1a2:US'})

        POI = SubElement(location, 'POIDetails')
        address = SubElement(POI, 'address')
        SubElement(address, 'line')
        loc = SubElement(address, 'locality', attrib={'qcode':'sttcity:2692'})
        locName = SubElement(loc, 'name')
        locName.text = 'Westmont'
        country = SubElement(address, 'country', attrib={'qcode':'sttcountry:1234'})
        countryName = SubElement(country, 'name', attrib={'role':'nrol:display'})
        countryName.text = 'Yhdysvallat'
        SubElement(country, 'sameAs', attrib={'qcode':'iso3166-1a2:US'})
        SubElement(address, 'postalcode')
        """

    # Format concept
    def format_concept(self, article, parentNode):

        # Use isoformat to get timezone offset correctly
        createdStr = article.get('versioncreated', None).astimezone(pytz.timezone('Europe/Helsinki')).isoformat(timespec='seconds')

        concept = SubElement(parentNode, "concept")
        SubElement(concept, 'conceptId', attrib={'qcode': 'sttevents:' + article.get('guid', ''), 'created': createdStr})
        SubElement(concept, 'type', attrib={'qcode': 'cpnat:event'})

        # Event name
        eventName = SubElement(concept, 'name')
        eventName.text = article.get('name', '')

        # Remote info, n..1
        SubElement(concept, 'remoteInfo')

        # Note: Lue kutsu
        note = SubElement(concept, 'note', attrib={'role': 'sttdescription:eventinv'})
        note.text = article.get('invitation_details', '')

        # Definition: Tapahtuman kuvaus
        definition = SubElement(concept, 'definition', attrib={'role': 'drol:summary'})
        definition.text = article.get('definition_short', '')

        # Related: tapahtuman tyyppi, qcode arvoe eri kuin tuotannossa. Haittaako?
        if 'subject' in article and article['subject'] is not None:
            for s in article['subject']:
                if 'scheme' in s and 'name' in s:
                    if s['scheme'] == 'event_type':
                        related = SubElement(concept, 'related', attrib={'rel': 'sttnat:sttEventType', 'qcode': 'sttEventType:' + s['qcode']})
                        relatedName = SubElement(related, 'name')
                        relatedName.text = s['name']

        # Event details
        self.format_eventDetails(article, concept)

    def can_format(self, format_type, article):
        return format_type == self.type

    async def format(self, article, subscriber, codes=None):

        try:

            # print(article)

            pub_seq_num = await generate_sequence_number(subscriber)
            dateStr = article.get('versioncreated', None).astimezone(pytz.timezone('Europe/Helsinki')).strftime('%Y%m%d')

            conceptItem = etree.Element('conceptItem', attrib={
                'guid': 'urn:newsml:stt.fi:' + dateStr + ':' + article.get('guid', ''),
                'version': str(article[VERSION]),
                'standardversion': '2.12',
                'conformance': 'power',
                XML_LANG: 'fi-FI',
                'standard': 'NewsML-G2',
                XSI_SCHEMALOCATION: 'http://iptc.org/std/nar/2006-10-01/ http://www.iptc.org/std/NewsML-G2/2.12/specification/NewsML-G2_2.12-spec-All-Power.xsd http://www.stt-lehtikuva.fi/NewsML http://www.stt-lehtikuva.fi/newsml/schema/STT-Lehtikuva_NewsML_G2.xsd',
                STT_FORMATVERSION: '1.1',
            }, nsmap=self._message_nsmap)

            # Add Catalogs for conceptItem
            SubElement(conceptItem, "catalogRef", attrib={"href": "http://www.iptc.org/std/catalog/catalog.IPTC-G2-Standards_19.xml"})
            SubElement(conceptItem, 'catalogRef', attrib={'href': 'http://www.stt-lehtikuva.fi/newsml/doc/stt-NewsCodesCatalog_1.xml'})

            self.format_itemMeta(article, conceptItem)
            self.format_contentMeta(article, conceptItem)
            self.format_concept(article, conceptItem)

            return [
                (
                    pub_seq_num,
                    self.XML_ROOT
                    + etree.tostring(conceptItem, method='xml', pretty_print=True, encoding=self.ENCODING).decode(self.ENCODING),
                )
            ]

        except Exception as ex:
            raise await FormatterError.newsmlG2FormatterError(ex, subscriber).send_notifications()
