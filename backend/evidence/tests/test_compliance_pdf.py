from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from evidence.services.compliance_pdf import extract_planned_off_the_job_hours


class CompliancePdfExtractionTests(SimpleTestCase):
    def extract_from_text(self, text):
        page = MagicMock()
        page.extract_text.return_value = text
        with patch("evidence.services.compliance_pdf.PdfReader") as reader:
            reader.return_value.pages = [page]
            return extract_planned_off_the_job_hours(b"fake pdf")

    def test_extracts_current_training_plan_wording(self):
        value = self.extract_from_text(
            "The agreed planned hours at the start of the apprenticeship "
            "are 308 hours of off-the-job training."
        )
        self.assertEqual(value, Decimal("308"))

    def test_extracts_new_training_plan_ilr_wording(self):
        value = self.extract_from_text("ILR Planned Hours: 356")
        self.assertEqual(value, Decimal("356"))

    def test_extracts_legacy_letter_spaced_training_plan_wording(self):
        value = self.extract_from_text("I L R  P l a n n e d  H o u r s :\n8 6 7")
        self.assertEqual(value, Decimal("867"))

    def test_extracts_table_value_separated_from_training_plan_label(self):
        value = self.extract_from_text(
            "I L R  P l a n n e d  H o u r s :\n"
            "I L R  P l a n n e d  E n d  D a t e\n"
            "1 8 / 1 0 / 2 0 2 4\n1 7 / 0 4 / 2 0 2 8\n"
            "1 5 6 . 4 3  w e e ks\n8 6 7"
        )
        self.assertEqual(value, Decimal("867"))

    def test_extracts_table_value_separated_from_agreement_label(self):
        value = self.extract_from_text(
            "P l a n n e d  a m o u n t  o f  o f f - t h e - j o b\n"
            "t r a i n i n g  ( h o u r s )  ( s e e  n o t e  5 ) :\n"
            "D a t e :\n1 7 / 0 4 / 2 0 2 8\n1 7 / 1 0 / 2 0 2 7\n8 6 7"
        )
        self.assertEqual(value, Decimal("867"))

    def test_extracts_legacy_letter_spaced_agreement_wording(self):
        value = self.extract_from_text(
            "P l a n n e d  a m o u n t  o f  o f f - t h e - j o b  "
            "t r a i n i n g  ( h o u r s )  ( s e e  n o t e  5 ) :\n8 6 7"
        )
        self.assertEqual(value, Decimal("867"))

    def test_extracts_esfa_table_wording_without_using_note_number(self):
        value = self.extract_from_text(
            "Planned amount of off-the-job training (hours) (see note 5):\n375"
        )
        self.assertEqual(value, Decimal("375"))
