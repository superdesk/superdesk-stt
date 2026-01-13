import lxml.etree as etree

from tests import TestCase

from stt.parser_afp import AFPNewsMLFeedParser


class AFPNewsMLFeedParserTestCase(TestCase):
    fixture = None
    parse_source = False
    parser_class = AFPNewsMLFeedParser

    async def parse_item_from_string(self, xml_string: str):
        xml_root = etree.fromstring(xml_string.encode("utf-8"))
        provider = {"name": "Test", "config": {}}
        async with self.ctx:
            parser = self.parser_class()
            return await parser.parse(xml_root, provider)

    async def test_prefixes_first_advisory_line_to_body_html(self):
        xml_string = """<?xml version="1.0" encoding="UTF-8"?>
      <NewsML Version="1.2">
  <NewsItem>
    <Identification>
      <NewsIdentifier>
        <ProviderId>afp.com</ProviderId>
        <DateId>20260109T091444Z</DateId>
        <NewsItemId>TX-PAR-BDO05</NewsItemId>
        <RevisionId PreviousRevision="0" Update="N">1</RevisionId>
        <PublicIdentifier>urn:newsml:afp.com:20260109:TX-PAR-BDO05</PublicIdentifier>
      </NewsIdentifier>
    </Identification>
    <NewsManagement>
      <FirstCreated>20260109T091444Z</FirstCreated>
      <ThisRevisionCreated>20260109T091444Z</ThisRevisionCreated>
      <Status FormalName="Usable"/>
    </NewsManagement>

    <NewsComponent>
      <Role FormalName="Main"/>
      <NewsLines>
        <NewsLine>
          <NewsLineType FormalName="AdvisoryLine"/>
          <NewsLineText xml:lang="en">CORRECTS para 4 and 9 to say Thursday, not Friday</NewsLineText>
        </NewsLine>
      </NewsLines>

      <ContentItem>
        <MediaType FormalName="Text"/>
        <DataContent>
          <nitf>
            <body>
              <body.content>
                <p>First para.</p>
              </body.content>
            </body>
          </nitf>
        </DataContent>
      </ContentItem>
    </NewsComponent>
  </NewsItem>
</NewsML>
"""
        item = await self.parse_item_from_string(xml_string)

        prefix = "<p>CORRECTS para 4 and 9 to say Thursday, not Friday</p>\n"
        self.assertTrue(item.get("body_html"))
        self.assertTrue(item["body_html"].startswith(prefix))

    async def test_does_not_prefix_when_newslinetype_is_not_advisoryline(self):
        xml_string = """<?xml version="1.0" encoding="UTF-8"?>
      <NewsML Version="1.2">
  <NewsItem>
    <Identification>
      <NewsIdentifier>
        <ProviderId>afp.com</ProviderId>
        <DateId>20260109T091444Z</DateId>
        <NewsItemId>TX-PAR-BDO05</NewsItemId>
        <RevisionId PreviousRevision="0" Update="N">1</RevisionId>
        <PublicIdentifier>urn:newsml:afp.com:20260109:TX-PAR-BDO05</PublicIdentifier>
      </NewsIdentifier>
    </Identification>
    <NewsManagement>
      <FirstCreated>20260109T091444Z</FirstCreated>
      <ThisRevisionCreated>20260109T091444Z</ThisRevisionCreated>
      <Status FormalName="Usable"/>
    </NewsManagement>

    <NewsComponent>
      <Role FormalName="Main"/>
      <NewsLines>
        <NewsLine>
          <NewsLineType FormalName="ProductLine"/>
          <NewsLineText xml:lang="en">DO NOT PREFIX THIS</NewsLineText>
        </NewsLine>
      </NewsLines>

      <ContentItem>
        <MediaType FormalName="Text"/>
        <DataContent>
          <nitf>
            <body>
              <body.content>
                <p>First para.</p>
              </body.content>
            </body>
          </nitf>
        </DataContent>
      </ContentItem>
    </NewsComponent>
  </NewsItem>
</NewsML>
"""
        item = await self.parse_item_from_string(xml_string)

        self.assertTrue(item.get("body_html"))
        self.assertFalse(item["body_html"].startswith("<p>DO NOT PREFIX THIS</p>\n"))
        self.assertNotIn("DO NOT PREFIX THIS", item["body_html"].split("\n", 1)[0])

    async def test_skips_when_body_html_missing_or_empty(self):
        xml_string = """<?xml version="1.0" encoding="UTF-8"?>
      <NewsML Version="1.2">
  <NewsItem>
    <Identification>
      <NewsIdentifier>
        <ProviderId>afp.com</ProviderId>
        <DateId>20260109T091444Z</DateId>
        <NewsItemId>TX-PAR-BDO05</NewsItemId>
        <RevisionId PreviousRevision="0" Update="N">1</RevisionId>
        <PublicIdentifier>urn:newsml:afp.com:20260109:TX-PAR-BDO05</PublicIdentifier>
      </NewsIdentifier>
    </Identification>
    <NewsManagement>
      <FirstCreated>20260109T091444Z</FirstCreated>
      <ThisRevisionCreated>20260109T091444Z</ThisRevisionCreated>
      <Status FormalName="Usable"/>
    </NewsManagement>

    <NewsComponent>
      <Role FormalName="Main"/>
      <NewsLines>
        <NewsLine>
          <NewsLineType FormalName="AdvisoryLine"/>
          <NewsLineText xml:lang="en">CORRECTS para 4 and 9 to say Thursday, not Friday</NewsLineText>
        </NewsLine>
      </NewsLines>

      <ContentItem>
        <MediaType FormalName="Text"/>
        <DataContent>
          <nitf>
            <body>
              <body.content>
              </body.content>
            </body>
          </nitf>
        </DataContent>
      </ContentItem>
    </NewsComponent>
  </NewsItem>
</NewsML>
"""
        item = await self.parse_item_from_string(xml_string)

        prefix = "<p>CORRECTS para 4 and 9 to say Thursday, not Friday</p>\n"
        self.assertFalse(str(item.get("body_html") or "").startswith(prefix))
