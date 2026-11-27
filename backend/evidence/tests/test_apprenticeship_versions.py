from datetime import date

from django.test import SimpleTestCase

from evidence.services.apprenticeship_versions import (
    agreement_version_url,
    best_agreement_version_for_start,
)


class ApprenticeshipVersionTests(SimpleTestCase):
    def test_selects_latest_version_before_start_for_same_program(self):
        documents = [
            {"Id": 8859, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2026-05-14T11:57:04"},
            {"Id": 8863, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2026-05-14T11:59:42"},
            {"Id": 10487, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2026-07-07T12:22:56"},
            {"Id": 4466, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 4322, "CreateDateTime": "2025-10-15T14:14:04"},
        ]

        selected = best_agreement_version_for_start(
            documents, 14227, date(2026, 5, 20)
        )

        self.assertEqual(selected["Id"], 8863)

    def test_selects_closest_version_when_every_version_is_after_start(self):
        documents = [
            {"Id": 1914, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2025-05-09T14:07:38"},
            {"Id": 1893, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2025-05-09T12:39:33"},
        ]

        selected = best_agreement_version_for_start(
            documents, 14227, date(2025, 5, 2)
        )

        self.assertEqual(selected["Id"], 1893)

    def test_selects_latest_version_created_on_start_date(self):
        documents = [
            {"Id": 8859, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2026-05-20T08:00:00"},
            {"Id": 8863, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 14227, "CreateDateTime": "2026-05-20T16:00:00"},
        ]

        selected = best_agreement_version_for_start(
            documents, 14227, date(2026, 5, 20)
        )

        self.assertEqual(selected["Id"], 8863)

    def test_uses_reference_document_program_when_database_program_id_differs(self):
        documents = [
            {"Id": 908, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 1383, "CreateDateTime": "2025-04-23T11:13:14"},
            {"Id": 909, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 1383, "CreateDateTime": "2025-04-23T11:14:06"},
            {"Id": 8541, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 1383, "CreateDateTime": "2026-05-11T15:12:03"},
            {"Id": 500, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 5, "CreateDateTime": "2025-05-01T12:00:00"},
        ]

        selected = best_agreement_version_for_start(
            documents,
            program_id=5,
            start_date=date(2025, 5, 2),
            reference_document_id=8541,
        )

        self.assertEqual(selected["Id"], 909)

    def test_returns_none_when_no_version_matches_the_resolved_program(self):
        documents = [
            {"Id": 500, "ComplianceName": "Apprenticeship Agreement", "ProgramId": 99, "CreateDateTime": "2025-05-01T12:00:00"},
        ]

        selected = best_agreement_version_for_start(
            documents,
            program_id=5,
            start_date=date(2025, 5, 2),
        )

        self.assertIsNone(selected)

    def test_builds_historical_download_url(self):
        self.assertEqual(
            agreement_version_url("https://example.aptem.co.uk/", 8863, 4609),
            "https://example.aptem.co.uk/DownloadFile/Compliance/8863?userId=4609",
        )
