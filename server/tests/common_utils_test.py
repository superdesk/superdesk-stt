from . import TestCase
from stt.common import is_online_version, location_has_changes


class CommonUtilsTest(TestCase):
    parse_source = False

    async def test_is_online_version(self):
        self.fixture = "stt_newsml_link_content.xml"
        await self.parse_source_content()
        self.assertFalse(is_online_version(self.item))

        self.fixture = "stt_newsml_online_version.xml"
        await self.parse_source_content()
        self.assertTrue(is_online_version(self.item))

    def test_location_has_changes_ignores_missing_metadata(self):
        existing = {
            "address": {
                "city": "Ostrava",
                "country": "Tsekki",
                "extra": {
                    "iso3166": "iso3166-1a2:CZ",
                    "sttcity": 1325,
                    "sttcountry": 243,
                    "sttlocationalias": 6065,
                    "sttstate": 87,
                },
                "line": [],
                "postal_code": None,
                "state": "N/A",
                "title": "Ostrava",
            },
            "guid": "urn:stt:location:6065",
            "is_active": True,
            "name": "Ostrava",
            "type": "Unclassified",
            "unique_name": "Ostrava, Ostrava, Tsekki",
        }
        incoming = {
            "address": {
                "city": "Ostrava",
                "country": "Tsekki",
                "extra": {
                    "iso3166": "iso3166-1a2:CZ",
                    "sttcity": 1325,
                    "sttcountry": 243,
                    "sttlocationalias": 6065,
                    "sttstate": 87,
                },
                "line": [],
                "postal_code": None,
                "state": "N/A",
                "title": "Ostrava",
            },
            "guid": "urn:stt:location:6065",
            "is_active": True,
            "name": "Ostrava",
            "type": "Unclassified",
            "unique_name": "Ostrava, Ostrava, Tsekki",
            "qcode": "urn:stt:location:6065",
        }

        self.assertFalse(location_has_changes(existing, incoming))

        incoming["name"] = "Ostrava Center"
        self.assertTrue(location_has_changes(existing, incoming))
