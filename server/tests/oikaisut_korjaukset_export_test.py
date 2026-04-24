from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from stt.oikaisut_korjaukset_export import enrich_items

_PREVIOUS_DAY_EVENING_ITEMS_PATCH = (
    "stt.oikaisut_korjaukset_export.enrich_items." "_get_previous_day_evening_items"
)


class OikaisutKorjauksetExportTestCase(unittest.TestCase):
    def test_reference_datetime_uses_latest_planning_date(self):
        reference_dt = enrich_items._get_reference_datetime_from_items(
            [
                {"planning_date": "2026-01-14T00:00:00+0000"},
                {"planning_date": datetime(2026, 1, 15, 0, 0, 0)},
                {"planning_date": "invalid"},
            ]
        )

        self.assertEqual(
            datetime(2026, 1, 14, 22, 0, 0, tzinfo=timezone.utc),
            reference_dt,
        )

    def test_previous_day_evening_window_utc_in_winter(self):
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        start_dt, end_dt = enrich_items._get_previous_day_evening_window_utc(now)

        self.assertEqual(
            datetime(2026, 1, 14, 18, 0, 0, tzinfo=timezone.utc),
            start_dt,
        )
        self.assertEqual(
            datetime(2026, 1, 14, 22, 0, 0, tzinfo=timezone.utc),
            end_dt,
        )

    def test_previous_day_evening_window_utc_in_summer(self):
        now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)

        start_dt, end_dt = enrich_items._get_previous_day_evening_window_utc(now)

        self.assertEqual(
            datetime(2026, 7, 14, 17, 0, 0, tzinfo=timezone.utc),
            start_dt,
        )
        self.assertEqual(
            datetime(2026, 7, 14, 21, 0, 0, tzinfo=timezone.utc),
            end_dt,
        )

    @patch("stt.oikaisut_korjaukset_export.enrich_items._group_items_by_type")
    @patch(_PREVIOUS_DAY_EVENING_ITEMS_PATCH)
    def test_enrich_merges_previous_day_items_without_duplicates(
        self,
        mock_get_previous_day_evening_items,
        mock_group_items_by_type,
    ):
        today_items = [{"_id": "today-1"}]
        mock_get_previous_day_evening_items.return_value = [
            {"_id": "today-1"},
            {"_id": "late-1"},
        ]
        mock_group_items_by_type.return_value = {
            "oikaisut": [],
            "korjaukset": [],
        }

        enrich_items.enrich_oikaisut_korjaukset_for_export(today_items)

        mock_get_previous_day_evening_items.assert_called_once_with(today_items)
        mock_group_items_by_type.assert_called_once_with(
            [{"_id": "today-1"}, {"_id": "late-1"}]
        )

    @patch("stt.oikaisut_korjaukset_export.enrich_items._group_items_by_type")
    @patch(_PREVIOUS_DAY_EVENING_ITEMS_PATCH)
    def test_enrich_uses_previous_day_items_when_today_list_is_empty(
        self,
        mock_get_previous_day_evening_items,
        mock_group_items_by_type,
    ):
        mock_get_previous_day_evening_items.return_value = [{"_id": "late-1"}]
        mock_group_items_by_type.return_value = {
            "oikaisut": [{"_id": "late-1"}],
            "korjaukset": [],
        }

        result = enrich_items.enrich_oikaisut_korjaukset_for_export([])

        mock_get_previous_day_evening_items.assert_called_once_with([])
        self.assertEqual(
            {"oikaisut": [{"_id": "late-1"}], "korjaukset": []},
            result,
        )
        mock_group_items_by_type.assert_called_once_with([{"_id": "late-1"}])

    @patch(
        "stt.oikaisut_korjaukset_export.enrich_items."
        "get_planning_items_with_published_corrections_between"
    )
    def test_previous_day_evening_items_use_reference_date_from_rows(
        self,
        mock_get_planning_items,
    ):
        mock_get_planning_items.return_value = []

        enrich_items._get_previous_day_evening_items(
            [{"planning_date": "2026-01-15T00:00:00+0000"}]
        )

        mock_get_planning_items.assert_called_once_with(
            datetime(2026, 1, 14, 18, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 14, 22, 0, 0, tzinfo=timezone.utc),
            projection={
                "_id": 1,
                "anpa_category": 1,
                "internal_coverages": 1,
                "planning_date": 1,
                "priority": 1,
                "slugline": 1,
                "state": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
