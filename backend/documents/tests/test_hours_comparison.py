from decimal import Decimal

from django.test import SimpleTestCase

from documents.hours_comparison_services import _comparison_state


class PlannedHoursComparisonStateTests(SimpleTestCase):
    def row(self, ilr, training_plan, agreement):
        return {
            "ilr_planned_hours": ilr,
            "training_plan_planned_hours": training_plan,
            "apprenticeship_agreement_planned_hours": agreement,
        }

    def test_marks_equal_values_as_matched(self):
        row = self.row(Decimal("850"), Decimal("850.00"), Decimal("850.0"))
        _comparison_state(row)
        self.assertEqual(row["comparison_status"], "matched")
        self.assertTrue(row["is_matched"])

    def test_marks_different_values_as_mismatched(self):
        row = self.row(Decimal("850"), Decimal("849"), Decimal("850"))
        _comparison_state(row)
        self.assertEqual(row["comparison_status"], "mismatched")
        self.assertFalse(row["is_matched"])

    def test_marks_incomplete_values_as_missing(self):
        row = self.row(Decimal("850"), None, Decimal("850"))
        _comparison_state(row)
        self.assertEqual(row["comparison_status"], "missing")
        self.assertIn("Training Plan", row["comparison_reason"])
