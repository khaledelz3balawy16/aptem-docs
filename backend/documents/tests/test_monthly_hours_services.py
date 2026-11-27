from datetime import date

from django.test import SimpleTestCase

from documents.monthly_hours_services import (
    _available_years,
    _is_test_row,
    _monthly_state,
    _select_year,
)


class MonthlyHoursServicesTests(SimpleTestCase):
    def test_monthly_state_builds_all_months_and_totals(self):
        row = {
            "planned_hours_monthly": {"2026-01": "12", "2026-02": 0},
            "completed_hours_monthly": {"2026-01": "7.5", "2026-03": 4},
        }

        result = _monthly_state(row, 2026)

        self.assertEqual(len(result["months"]), 12)
        self.assertEqual(result["months"][0]["planned"], 12)
        self.assertEqual(result["months"][0]["completed"], 7.5)
        self.assertEqual(result["planned_total"], 12)
        self.assertEqual(result["completed_total"], 11.5)
        self.assertTrue(result["has_hours"])

    def test_available_years_ignores_anomalous_keys(self):
        rows = [{
            "planned_hours_monthly": {"1998-08": 2, "2025-03": 4},
            "completed_hours_monthly": {"2026-04": 5, "2038-01": 1},
        }]

        years = _available_years(rows, today=date(2026, 8, 2))

        self.assertEqual(years, [2025, 2026])

    def test_select_year_prefers_current_year(self):
        self.assertEqual(
            _select_year("", [2024, 2025, 2026], today=date(2026, 8, 2)),
            2026,
        )

    def test_select_year_rejects_out_of_range_value(self):
        with self.assertRaises(ValueError):
            _select_year("2038", [2026], today=date(2026, 8, 2))

    def test_test_rows_are_excluded_without_matching_legitimate_words(self):
        self.assertTrue(_is_test_row({"full_name": "APM L4 (Test)"}))
        self.assertTrue(_is_test_row({"program_name": "Test Programme"}))
        self.assertFalse(_is_test_row({"full_name": "Daniel Welton"}))
        self.assertFalse(_is_test_row({"program_name": "Market Research"}))
