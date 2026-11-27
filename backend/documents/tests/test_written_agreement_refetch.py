from datetime import datetime, timezone

from django.test import SimpleTestCase

from documents.written_agreement_refetch_services import (
    select_latest_written_agreement,
)


class WrittenAgreementRefetchTests(SimpleTestCase):
    def test_selects_latest_written_agreement_for_current_programme(self):
        rows = [
            {
                "source_document_id": 100,
                "document_name": "Written Agreement",
                "program_name": "Programme A",
                "date": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
            {
                "source_document_id": 101,
                "document_name": "Written Agreement 25/26",
                "program_name": "Programme A",
                "date": datetime(2026, 2, 1, tzinfo=timezone.utc),
            },
            {
                "source_document_id": 999,
                "document_name": "Written Agreement",
                "program_name": "Programme B",
                "date": datetime(2026, 3, 1, tzinfo=timezone.utc),
            },
            {
                "source_document_id": 1000,
                "document_name": "Apprenticeship Agreement",
                "program_name": "Programme A",
                "date": datetime(2026, 4, 1, tzinfo=timezone.utc),
            },
        ]

        selected = select_latest_written_agreement(rows, "Programme A")

        self.assertEqual(selected["source_document_id"], 101)

    def test_returns_none_without_an_agreement_for_the_current_programme(self):
        rows = [
            {
                "source_document_id": 999,
                "document_name": "Written Agreement",
                "program_name": "Programme B",
                "date": datetime(2026, 3, 1, tzinfo=timezone.utc),
            }
        ]

        self.assertIsNone(select_latest_written_agreement(rows, "Programme A"))
