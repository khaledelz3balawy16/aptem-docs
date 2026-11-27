from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from documents.funding_comparison_services import (
    COST_ITEMS,
    _funding_validation_state,
    _ilr_finance_state,
    _ilr_agreement_comparison_state,
    _visible_ilr_finance_codes,
    _visible_cost_items,
    _visible_reference_items,
)


def funding_row(values, json_total=6000):
    breakdown = {
        key: {"value": values.get(key), "currency": "GBP"}
        for key, _label in COST_ITEMS
    }
    return {
        "written_agreement_funding": {
            "cost_breakdown": breakdown,
            "funding_band_maximum_value": {"value": 9000, "currency": "GBP"},
            "balance_due": {"value": 0, "currency": "GBP"},
            "actual_funding": {"value": 4650, "currency": "GBP"},
            "total_price_of_apprenticeship": {
                "value": json_total,
                "currency": "GBP",
            },
        }
    }


class FundingComparisonTests(SimpleTestCase):
    def test_ilr_uses_latest_tnp_date_and_excludes_pmr(self):
        row = {
            "app_fin_records": [
                {"AFinCode": "1", "AFinDate": "2025-01-17", "AFinType": "TNP", "AFinAmount": "5010"},
                {"AFinCode": "2", "AFinDate": "2025-01-17", "AFinType": "TNP", "AFinAmount": "990"},
                {"AFinCode": "1", "AFinDate": "2026-06-01", "AFinType": "PMR", "AFinAmount": "240"},
                {"AFinCode": "2", "AFinDate": "2026-06-01", "AFinType": "PMR", "AFinAmount": "60"},
            ]
        }

        _ilr_finance_state(row)

        self.assertEqual(row["ilr_finance_date"], date(2025, 1, 17))
        self.assertEqual(row["ilr_finance_items"], {"1": Decimal("5010"), "2": Decimal("990")})
        self.assertEqual(row["ilr_finance_total"], Decimal("6000"))

    def test_ilr_groups_latest_tnp_records_by_code(self):
        row = {
            "app_fin_records": [
                {"AFinCode": "1", "AFinDate": "2024-10-18", "AFinType": "TNP", "AFinAmount": "25000"},
                {"AFinCode": "2", "AFinDate": "2024-10-18", "AFinType": "TNP", "AFinAmount": "2000"},
                {"AFinCode": "3", "AFinDate": "2026-03-01", "AFinType": "TNP", "AFinAmount": "10000"},
                {"AFinCode": "3", "AFinDate": "2026-03-01", "AFinType": "TNP", "AFinAmount": "400"},
                {"AFinCode": "4", "AFinDate": "2026-03-01", "AFinType": "TNP", "AFinAmount": "3400"},
            ]
        }

        _ilr_finance_state(row)

        self.assertEqual(row["ilr_finance_date"], date(2026, 3, 1))
        self.assertEqual(row["ilr_finance_items"], {"3": Decimal("10400"), "4": Decimal("3400")})
        self.assertEqual(row["ilr_finance_total"], Decimal("13800"))
        self.assertEqual(_visible_ilr_finance_codes([row]), ["3", "4"])

    def test_ilr_with_only_pmr_has_no_finance_total(self):
        row = {
            "app_fin_records": [
                {"AFinCode": "1", "AFinDate": "2026-06-01", "AFinType": "PMR", "AFinAmount": "240"}
            ]
        }

        _ilr_finance_state(row)

        self.assertIsNone(row["ilr_finance_date"])
        self.assertEqual(row["ilr_finance_items"], {})
        self.assertIsNone(row["ilr_finance_total"])

    def test_ilr_and_agreement_totals_match(self):
        row = {"ilr_finance_total": Decimal("6000"), "json_total": Decimal("6000")}

        _ilr_agreement_comparison_state(row)

        self.assertEqual(row["ilr_agreement_status"], "matched")
        self.assertEqual(row["ilr_agreement_difference"], Decimal("0"))

    def test_ilr_and_agreement_totals_mismatch(self):
        row = {"ilr_finance_total": Decimal("5900"), "json_total": Decimal("6000")}

        _ilr_agreement_comparison_state(row)

        self.assertEqual(row["ilr_agreement_status"], "mismatched")
        self.assertEqual(row["ilr_agreement_difference"], Decimal("-100"))

    def test_ilr_and_agreement_comparison_requires_both_totals(self):
        row = {"ilr_finance_total": None, "json_total": Decimal("6000")}

        _ilr_agreement_comparison_state(row)

        self.assertEqual(row["ilr_agreement_status"], "missing")
        self.assertIn("ILR", row["ilr_agreement_reason"])

    def test_matches_when_item_sum_equals_json_total(self):
        row = funding_row(
            {
                "training_delivery": 3000,
                "assessment_progress_reviews": 1650,
                "end_point_assessment": 1350,
            }
        )
        _funding_validation_state(row)

        self.assertEqual(row["calculated_total"], Decimal("6000"))
        self.assertEqual(row["json_total"], Decimal("6000"))
        self.assertEqual(row["difference"], Decimal("0"))
        self.assertEqual(row["funding_band_maximum"], Decimal("9000"))
        self.assertEqual(row["balance_due"], Decimal("0"))
        self.assertEqual(row["actual_funding"], Decimal("4650"))
        self.assertEqual(row["comparison_status"], "matched")

    def test_mismatches_when_item_sum_differs_from_json_total(self):
        row = funding_row({"training_delivery": 3000}, json_total=6000)
        _funding_validation_state(row)

        self.assertEqual(row["calculated_total"], Decimal("3000"))
        self.assertEqual(row["difference"], Decimal("-3000"))
        self.assertEqual(row["comparison_status"], "mismatched")

    def test_blank_currency_values_are_counted_as_zero(self):
        row = funding_row({"training_delivery": 6000})
        _funding_validation_state(row)

        self.assertEqual(row["calculated_total"], Decimal("6000"))
        self.assertEqual(row["comparison_status"], "matched")

    def test_missing_funding_json_is_missing(self):
        row = {"written_agreement_funding": None}
        _funding_validation_state(row)

        self.assertIsNone(row["calculated_total"])
        self.assertEqual(row["comparison_status"], "missing")

    def test_missing_cost_key_is_missing_not_zero(self):
        row = funding_row({"training_delivery": 6000})
        del row["written_agreement_funding"]["cost_breakdown"]["materials"]
        _funding_validation_state(row)

        self.assertEqual(row["comparison_status"], "missing")
        self.assertIn("Materials", row["comparison_reason"])

    def test_empty_columns_are_not_returned(self):
        rows = [
            {
                "cost_items": {
                    "training_delivery": Decimal("1000"),
                    "subcontractor_training": None,
                    "other_non_fundable_costs": Decimal("0"),
                },
                "funding_band_maximum": Decimal("6000"),
                "balance_due": None,
                "actual_funding": Decimal("5100"),
            }
        ]

        cost_keys = [key for key, _label in _visible_cost_items(rows)]
        reference_keys = [key for key, _label in _visible_reference_items(rows)]

        self.assertIn("training_delivery", cost_keys)
        self.assertNotIn("subcontractor_training", cost_keys)
        self.assertNotIn("other_non_fundable_costs", cost_keys)
        self.assertEqual(
            reference_keys, ["funding_band_maximum", "actual_funding"]
        )
