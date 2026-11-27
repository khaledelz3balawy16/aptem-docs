from decimal import Decimal

from django.test import SimpleTestCase

from documents.skills_radar_services import _is_test_row, _skills_radar_state


class SkillsRadarStateTests(SimpleTestCase):
    def test_calculates_funding_reduction_from_oldest_to_latest_tnp(self):
        row = {
            "ilr_planned_hours": Decimal("421"),
            "app_fin_records": [
                {"AFinCode": "1", "AFinDate": "2026-01-01", "AFinType": "TNP", "AFinAmount": "7000"},
                {"AFinCode": "2", "AFinDate": "2026-01-01", "AFinType": "TNP", "AFinAmount": "1000"},
                {"AFinCode": "1", "AFinDate": "2026-02-01", "AFinType": "TNP", "AFinAmount": "5000"},
                {"AFinCode": "2", "AFinDate": "2026-02-01", "AFinType": "TNP", "AFinAmount": "1000"},
                {"AFinCode": "1", "AFinDate": "2026-02-01", "AFinType": "PMR", "AFinAmount": "300"},
            ],
        }

        result = _skills_radar_state(row)

        self.assertEqual(result["original_ilr_funding"], Decimal("8000"))
        self.assertEqual(result["funding_reduction"], Decimal("2000"))
        self.assertEqual(result["funding_reduction_percentage"], Decimal("25"))
        self.assertEqual(result["funding_snapshot_count"], 2)
        self.assertTrue(result["has_funding_reduction"])
        self.assertEqual(result["ilr_training_amount"], Decimal("5000"))
        self.assertEqual(result["ilr_epa_amount"], Decimal("1000"))
        self.assertEqual(result["ilr_finance_total"], Decimal("6000"))

    def test_never_reports_a_negative_reduction(self):
        result = _skills_radar_state(
            {
                "ilr_planned_hours": Decimal("375"),
                "app_fin_records": [
                    {"AFinCode": "1", "AFinDate": "2026-01-01", "AFinType": "TNP", "AFinAmount": "5000"},
                    {"AFinCode": "1", "AFinDate": "2026-02-01", "AFinType": "TNP", "AFinAmount": "6000"},
                ],
            }
        )

        self.assertEqual(result["funding_reduction"], Decimal("0"))
        self.assertFalse(result["has_funding_reduction"])

    def test_identifies_test_learners_and_programmes(self):
        self.assertTrue(_is_test_row({"full_name": "APM Test", "program_name": "Programme"}))
        self.assertTrue(_is_test_row({"full_name": "Learner", "program_name": "Test cohort"}))
        self.assertFalse(_is_test_row({"full_name": "Contest Smith", "program_name": "Marketing"}))
