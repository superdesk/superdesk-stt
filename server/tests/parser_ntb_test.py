from unittest.mock import MagicMock, patch

from tests import TestCase
from stt.parser_ntb import NTBNewsMLFeedParser


class NTBNewsMLFeedParserTest(TestCase):
    """
    Tests for NTBNewsMLFeedParser using the real STT controlled vocabularies.

    Fixture subjects (qcode → status in topics CV):
      subj:Utenriks   → non-numeric, skipped
      subj:20000062   → active (Sodat Aseelliset konfliktit / war)
      subj:20000056   → active (Aseelliset konfliktit / armed conflict)
      subj:16000000   → active (Levottomuudet Konfliktit Sodat), appears TWICE → deduplicated
      subj:16009000   → not a qcode in topics (it is the iptc_subject value of 20000062) → skipped
      cat:n / cat:e   → no "subj:" prefix → skipped
    Expected matched topics: {16000000, 20000056, 20000062}
    """

    fixture = "ntb_newsml_test.xml"
    parser_class = NTBNewsMLFeedParser
    add_stt_cvs = True

    def test_guid(self):
        assert self.item["guid"] == "000ad412-7526-4472-8978-7aad3c19f2be"

    def test_headline(self):
        assert (
            self.item["headline"]
            == "Ukraina bekrefter angrep mot russisk oljeraffineri"
        )

    def test_anpa_category(self):
        # First <subject> qcode is "subj:Utenriks" → mapped to Ulkomaat
        assert self.item["anpa_category"] == [{"qcode": "14", "name": "Ulkomaat"}]

    def test_body_html(self):
        body = self.item["body_html"]
        assert body.startswith("<p>")
        assert body.count("<p>") == 7

    def test_sources(self):
        sources = [s for s in self.item["subject"] if s.get("scheme") == "sttsource"]
        qcodes = {s["qcode"] for s in sources}
        assert "NTB" in qcodes
        assert "STT" in qcodes

    def test_topics_matched_from_cv(self):
        # Exactly the three active qcodes present as qcodes in the topics CV
        topics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        qcodes = {s["qcode"] for s in topics}
        assert qcodes == {"16000000", "20000056", "20000062"}

    def test_topics_no_duplicates(self):
        # qcode 16000000 appears twice in the XML source but must be stored only once
        topics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        qcodes = [s["qcode"] for s in topics]
        assert len(qcodes) == len(set(qcodes))

    def test_topics_non_numeric_excluded(self):
        # "subj:Utenriks" and "cat:*" codes must not end up as topic subjects
        topics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        assert all(s["qcode"].isdigit() for s in topics)

    def test_topics_carry_full_cv_metadata(self):
        # Matched topics must carry the full CV item: name, parent, translations, scheme
        topics = {
            s["qcode"]: s for s in self.item["subject"] if s.get("scheme") == "topics"
        }
        war = topics["20000062"]
        assert war["name"] == "Sodat Aseelliset konfliktit"
        assert war["parent"] == "20000056"
        assert war["scheme"] == "topics"
        assert "translations" in war


class NTBNewsMLFeedParserVocabMockTest(TestCase):
    """
    Mock-based tests that verify the CV lookup behaviour in isolation,
    independent of what is stored in the database.
    """

    fixture = "ntb_newsml_test.xml"
    parser_class = NTBNewsMLFeedParser
    parse_source = False  # parsing is done manually inside each test

    @patch("stt.parser_ntb.get_resource_service")
    async def test_only_topics_returned_by_get_items_are_added(self, mock_get_service):
        """Parser must add only topics the CV service returns (active filtering is done by get_items)."""
        mock_vocab = MagicMock()
        mock_vocab.get_items.return_value = [
            {
                "name": "Levottomuudet Konfliktit Sodat",
                "qcode": "16000000",
                "parent": None,
                "scheme": "topics",
            },
            # 20000056 and 20000062 deliberately absent → must not appear in output
        ]
        mock_get_service.return_value = mock_vocab

        await self.parse_source_content()

        topics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        assert [s["qcode"] for s in topics] == ["16000000"]
        mock_vocab.get_items.assert_called_once_with("topics")

    @patch("stt.parser_ntb.get_resource_service")
    async def test_vocabulary_service_error_is_handled_gracefully(
        self, mock_get_service
    ):
        """If the vocabulary service raises an exception, parsing continues without topic subjects."""
        mock_get_service.side_effect = Exception("service unavailable")

        await self.parse_source_content()

        topics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        assert topics == []

    @patch("stt.parser_ntb.get_resource_service")
    async def test_deduplication_with_mock_cv(self, mock_get_service):
        """qcode 16000000 appears twice in the XML; only one entry must be stored."""
        mock_vocab = MagicMock()
        mock_vocab.get_items.return_value = [
            {
                "name": "Levottomuudet Konfliktit Sodat",
                "qcode": "16000000",
                "parent": None,
                "scheme": "topics",
            },
        ]
        mock_get_service.return_value = mock_vocab

        await self.parse_source_content()

        topics = [s for s in self.item["subject"] if s.get("scheme") == "topics"]
        qcodes = [s["qcode"] for s in topics]
        assert qcodes.count("16000000") == 1
