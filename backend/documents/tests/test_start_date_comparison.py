from datetime import date

from django.test import SimpleTestCase

from documents.comparison_services import (
    _match_reason,
    _start_evidence_dates_match,
    _start_evidence_dates_mismatch,
)


class StartDateComparisonTests(SimpleTestCase):
    def test_start_and_first_evidence_dates_match_on_the_same_day(self):
        row = {
            "learn_start_date": date(2026, 1, 15),
            "first_evidence_date": date(2026, 1, 15),
        }

        self.assertTrue(_start_evidence_dates_match(row))

    def test_start_and_first_evidence_dates_do_not_match_on_different_days(self):
        row = {
            "learn_start_date": date(2026, 1, 15),
            "first_evidence_date": date(2026, 1, 16),
        }

        self.assertFalse(_start_evidence_dates_match(row))

    def test_start_and_first_evidence_dates_mismatch_on_different_days(self):
        row = {
            "learn_start_date": date(2026, 1, 15),
            "first_evidence_date": date(2026, 1, 16),
        }

        self.assertTrue(_start_evidence_dates_mismatch(row))

    def test_missing_evidence_is_not_counted_as_an_evidence_mismatch(self):
        row = {
            "learn_start_date": date(2026, 1, 15),
            "first_evidence_date": None,
        }

        self.assertFalse(_start_evidence_dates_mismatch(row))

    def test_matches_agreement_on_or_before_start_and_evidence_on_or_after(self):
        row = {
            "learn_start_date": date(2026, 1, 15),
            "apprenticeship_agreement_date": date(2026, 1, 13),
            "first_evidence_date": date(2026, 1, 15),
            "is_matched": True,
        }

        self.assertEqual(
            _match_reason(row),
            "Apprenticeship Agreement is on or before start; evidence is on or after start",
        )

    def test_reports_apprenticeship_agreement_after_start(self):
        row = {
            "learn_start_date": date(2026, 5, 20),
            "apprenticeship_agreement_date": date(2026, 7, 13),
            "first_evidence_date": date(2026, 5, 20),
            "is_matched": False,
        }

        self.assertEqual(
            _match_reason(row),
            "Apprenticeship Agreement was signed after the start date",
        )

    def test_reports_missing_apprenticeship_agreement(self):
        row = {
            "learn_start_date": date(2026, 5, 20),
            "apprenticeship_agreement_date": None,
            "first_evidence_date": date(2026, 5, 20),
            "is_matched": False,
        }

        self.assertEqual(
            _match_reason(row), "Apprenticeship Agreement date is missing"
        )
