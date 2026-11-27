from datetime import date

from django.test import SimpleTestCase

from documents.endpoint_assessment_services import _timeline_state


class EndpointAssessmentTests(SimpleTestCase):
    def test_actual_end_date_is_recorded(self):
        row = {
            "learn_start_date": date(2025, 1, 1),
            "learn_plan_end_date": date(2026, 1, 1),
            "learn_actual_end_date": date(2025, 12, 20),
        }

        _timeline_state(row, today=date(2026, 8, 1))

        self.assertEqual(row["timeline_status"], "completed")
        self.assertEqual(row["end_date_variance_days"], -12)

    def test_future_planned_end_is_in_progress(self):
        row = {
            "learn_start_date": date(2026, 1, 1),
            "learn_plan_end_date": date(2027, 1, 1),
            "learn_actual_end_date": None,
        }

        _timeline_state(row, today=date(2026, 8, 1))

        self.assertEqual(row["timeline_status"], "in-progress")

    def test_past_planned_end_without_actual_end_is_overdue(self):
        row = {
            "learn_start_date": date(2025, 1, 1),
            "learn_plan_end_date": date(2026, 7, 1),
            "learn_actual_end_date": None,
        }

        _timeline_state(row, today=date(2026, 8, 1))

        self.assertEqual(row["timeline_status"], "overdue")

    def test_missing_required_dates_is_missing(self):
        row = {
            "learn_start_date": date(2025, 1, 1),
            "learn_plan_end_date": None,
            "learn_actual_end_date": None,
        }

        _timeline_state(row, today=date(2026, 8, 1))

        self.assertEqual(row["timeline_status"], "missing")
