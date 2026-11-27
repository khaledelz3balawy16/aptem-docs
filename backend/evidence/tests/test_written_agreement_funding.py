from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from evidence.services.written_agreement_funding import (
    extract_written_agreement_funding,
)


class WrittenAgreementFundingTests(SimpleTestCase):
    def test_extracts_full_cost_breakdown_and_actual_funding(self):
        page = MagicMock()
        page.extract_text.return_value = """Costs:
Item Associated price
Training that IBIS Consultancy - Kent Business College will deliver Off the Job £ 3000
Distance, online or blended learning relating to the off-the-job training £ 3000
English & maths training that IBIS Consultancy - Kent Business College will deliver Off the Job (L3+ only) £
Materials (non-capital items) used in the delivery of the apprenticeship £ 100
End Point Assessment £ 1350
Any other costs not fundable by Levy funds or ESFA contribution £ 0
Total price of Apprenticeship £ 9000
Funding Band Maximum value £ 9000
Balance due £ 0
Please refer to Guidance document
"""
        with patch("evidence.services.written_agreement_funding.PdfReader") as reader:
            reader.return_value.pages = [page]
            funding = extract_written_agreement_funding(b"pdf")

        self.assertEqual(funding["actual_funding"]["value"], 7650)
        self.assertEqual(funding["cost_breakdown"]["training_delivery"]["value"], 3000)
        self.assertIsNone(funding["cost_breakdown"]["english_maths"]["value"])
        self.assertEqual(funding["cost_breakdown"]["materials"]["value"], 100)
        self.assertEqual(funding["balance_due"]["value"], 0)

    def test_supports_new_template_without_ibis_in_cost_labels(self):
        page = MagicMock()
        page.extract_text.return_value = """Costs:
Training that Kent Business College will deliver to the Apprentice Off the Job £ 9000
Assessment that Kent Business College will deliver (Including Progress Reviews) £ 4000
Support that Kent Business College will provide to the Subcontractor £
Monitoring that Kent Business College will undertake £
End Point Assessment £ 3400
Total price of Apprenticeship £ 27000
Funding Band Maximum value £ 27000
Balance due £
Please refer to Guidance document
"""
        with patch("evidence.services.written_agreement_funding.PdfReader") as reader:
            reader.return_value.pages = [page]
            funding = extract_written_agreement_funding(b"pdf")

        self.assertEqual(funding["cost_breakdown"]["training_delivery"]["value"], 9000)
        self.assertEqual(
            funding["cost_breakdown"]["assessment_progress_reviews"]["value"],
            4000,
        )
        self.assertIsNone(funding["cost_breakdown"]["subcontractor_support"]["value"])
        self.assertIsNone(funding["balance_due"]["value"])

    def test_supports_column_major_pdf_text(self):
        page = MagicMock()
        page.extract_text.return_value = """Costs:
Total price of Apprenticeship
Balance due
Any other costs not fundable by Levy funds or DfE contribution
Item
Training that Kent Business College will deliver Off the Job
Distance, online or blended learning
English & maths training
Assessment including Progress Reviews
Registration, examination and certification
Materials
Administration costs including EPA
Training delivered by the Subcontractor
Assessment undertaken by the Subcontractor
Support provided to the Subcontractor
Monitoring
End Point Assessment
Apprenticeship Certification
External Quality Assurance
£
£13800
Associated price
£4000
£4000
£
£2400
£
£
£
£
£
£
£
£3400
£
£
Funding Band Maximum value
£27000
Balance due
£
Please refer to Guidance document
"""
        with patch("evidence.services.written_agreement_funding.PdfReader") as reader:
            reader.return_value.pages = [page]
            funding = extract_written_agreement_funding(b"pdf")

        self.assertEqual(funding["cost_breakdown"]["training_delivery"]["value"], 4000)
        self.assertEqual(funding["cost_breakdown"]["end_point_assessment"]["value"], 3400)
        self.assertEqual(funding["total_price_of_apprenticeship"]["value"], 13800)
        self.assertEqual(funding["funding_band_maximum_value"]["value"], 27000)
        self.assertEqual(funding["actual_funding"]["value"], 10400)
