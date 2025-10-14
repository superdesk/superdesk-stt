# -*- coding: utf-8 -*-
import asyncio
import json
import os
import unittest

from stt.io.feed_parsers.stt_tt_parse_content_api import ContentAPITTItemParser


def fixture(filename):
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


class ContentAPITTItemParserTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = ContentAPITTItemParser()

        # Load test fixture
        with open(fixture("api/stt_tt_content_api.json")) as _file:
            self.fixture_data = json.load(_file)

    def test_parser_with_fixture_data(self):
        """Test parser with real fixture data."""
        test_item = self.fixture_data["hits"][0]

        result = asyncio.run(self.parser.parse(test_item, provider={"config": {}}))

        self.assertEqual(test_item["uri"], result[0]["uri"])

    def test_parser_minimal_item(self):
        """Test parser with minimal required data."""
        minimal_item = {
            "uri": "http://tt.se/media/text/test-minimal",
            "source": "STT",
            "type": "text",
            "headline": "Test minimal headline",
            "body_text": "Test content",
        }

        result = asyncio.run(self.parser.parse(minimal_item, provider={"config": {}}))

        self.assertEqual(minimal_item["uri"], result[0]["uri"])

    def test_parser_guid_consistency(self):
        """Test that GUID generation is consistent for the same input."""
        test_item = self.fixture_data["hits"][0]

        result1 = asyncio.run(self.parser.parse(test_item, provider={"config": {}}))
        result2 = asyncio.run(self.parser.parse(test_item, provider={"config": {}}))

        self.assertEqual(result1[0]["uri"], result2[0]["uri"])


if __name__ == "__main__":
    unittest.main()
