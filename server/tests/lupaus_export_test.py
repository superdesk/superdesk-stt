import unittest

from stt.lupaus_export import enrich_related


class LupausExportTestCase(unittest.TestCase):
    def test_planning_coverages_metadata_skips_excluded_pictureservice_coverages(self):
        planning_item = {
            "coverages": [
                {
                    "news_coverage_status": {"qcode": "ncostat:notdec"},
                    "planning": {
                        "g2_content_type": "text",
                        "subject": [
                            {
                                "scheme": "sttpictureservice",
                                "qcode": "Tilauskuvaus",
                            }
                        ],
                        "fields": [
                            {
                                "field": "sttpicturewhatabout",
                                "value": "Should be ignored",
                            }
                        ],
                    },
                },
                {
                    "news_coverage_status": {"qcode": "ncostat:int"},
                    "planning": {
                        "g2_content_type": "text",
                        "fields": [
                            {
                                "field": "sttpicturewhatabout",
                                "value": "Text coverage description",
                            }
                        ],
                    },
                },
                {
                    "news_coverage_status": {"qcode": "ncostat:int"},
                    "planning": {
                        "g2_content_type": "picture",
                        "subject": [
                            {"scheme": "sttimagetype", "name": "Kuvaaja paikalla"}
                        ],
                        "fields": [
                            {
                                "field": "sttpicturewhatabout",
                                "value": "Allowed description",
                            }
                        ],
                    },
                },
                {
                    "news_coverage_status": {"qcode": "ncostat:int"},
                    "planning": {
                        "g2_content_type": "picture",
                        "subject": [
                            {"scheme": "sttimagetype", "name": "Arkistokuvaa"},
                            {
                                "scheme": "sttpictureservice",
                                "qcode": "Arkistoon",
                            },
                        ],
                        "fields": [
                            {
                                "field": "sttpicturewhatabout",
                                "value": "Also ignored",
                            }
                        ],
                    },
                },
            ]
        }

        status = enrich_related._get_planning_coverages_metadata(planning_item, "teksti")
        imagetypes = enrich_related._get_planning_coverages_metadata(
            planning_item,
            "kuva",
            imagetypes=True,
        )
        picturewhatabouts = enrich_related._get_planning_coverages_metadata(
            planning_item,
            "kuva",
            sttpicturewhatabout=True,
        )

        self.assertEqual({"qcode": "ncostat:int"}, status)
        self.assertEqual({"imagetypes": ["Kuvaaja paikalla"]}, imagetypes)
        self.assertEqual(
            {
                "sttpicturewhatabout": [
                    "Text coverage description",
                    "Allowed description",
                ]
            },
            picturewhatabouts,
        )


if __name__ == "__main__":
    unittest.main()
