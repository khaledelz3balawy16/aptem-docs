from decimal import Decimal

from django.test import SimpleTestCase

from documents.prior_learning_services import _prior_learning_state


class PriorLearningTests(SimpleTestCase):
    def test_extracts_latest_ilr_tnp_and_written_agreement_values(self):
        row = {
            "ilr_planned_hours": Decimal("702"),
            "aptem_minimum_hours": Decimal("835"),
            "aptem_planned_hours": Decimal("702"),
            "app_fin_records": [
                {"AFinCode": "1", "AFinDate": "2026-01-30", "AFinType": "TNP", "AFinAmount": "21240"},
                {"AFinCode": "2", "AFinDate": "2026-01-30", "AFinType": "TNP", "AFinAmount": "3400"},
                {"AFinCode": "1", "AFinDate": "2026-07-10", "AFinType": "PMR", "AFinAmount": "1080"},
            ],
            "written_agreement_funding": {
                "actual_funding": {"value": 21240},
                "end_point_assessment": {"value": 3400},
                "total_price_of_apprenticeship": {"value": 24640},
                "funding_band_maximum_value": {"value": 27000},
            },
        }

        _prior_learning_state(row)

        self.assertEqual(row["ilr_training_amount"], Decimal("21240"))
        self.assertEqual(row["ilr_epa_amount"], Decimal("3400"))
        self.assertEqual(row["ilr_finance_total"], Decimal("24640"))
        self.assertEqual(row["minimum_planned_difference"], Decimal("133"))
        self.assertEqual(row["funding_reduction_from_band"], Decimal("2360"))
        self.assertEqual(row["hours_status"], "matched")
        self.assertEqual(row["funding_status"], "matched")

    def test_reports_source_mismatches_independently(self):
        row = {
            "ilr_planned_hours": Decimal("449"),
            "aptem_minimum_hours": Decimal("362"),
            "aptem_planned_hours": Decimal("448"),
            "app_fin_records": [
                {"AFinCode": "3", "AFinDate": "2025-10-16", "AFinType": "TNP", "AFinAmount": "19100"},
                {"AFinCode": "4", "AFinDate": "2025-10-16", "AFinType": "TNP", "AFinAmount": "3400"},
            ],
            "written_agreement_funding": {
                "actual_funding": {"value": 23600},
                "end_point_assessment": {"value": 3400},
                "total_price_of_apprenticeship": {"value": 27000},
                "funding_band_maximum_value": {"value": 27000},
            },
        }

        _prior_learning_state(row)

        self.assertEqual(row["hours_status"], "mismatched")
        self.assertEqual(row["funding_status"], "mismatched")
        self.assertEqual(row["funding_difference"], Decimal("-4500"))

    def test_missing_sources_are_not_treated_as_matches(self):
        row = {
            "ilr_planned_hours": None,
            "aptem_minimum_hours": Decimal("400"),
            "aptem_planned_hours": None,
            "app_fin_records": [],
            "written_agreement_funding": None,
        }

        _prior_learning_state(row)

        self.assertEqual(row["hours_status"], "missing")
        self.assertEqual(row["funding_status"], "missing")
        self.assertIsNone(row["funding_difference"])
