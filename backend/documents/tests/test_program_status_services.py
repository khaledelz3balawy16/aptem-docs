from django.test import SimpleTestCase

from documents.program_status_services import (
    filter_rows_by_program_status,
    normalize_program_status,
)


class ProgramStatusServiceTests(SimpleTestCase):
    def test_normalizes_program_status_case_and_spacing(self):
        self.assertEqual(normalize_program_status("  Withdrawn "), "withdrawn")

    def test_defaults_blank_program_status_to_all(self):
        self.assertEqual(normalize_program_status("  "), "all")

    def test_filters_rows_case_insensitively(self):
        rows = [
            {"full_name": "One", "program_status": "Active"},
            {"full_name": "Two", "program_status": "Withdrawn"},
            {"full_name": "Three", "program_status": None},
        ]

        self.assertEqual(
            filter_rows_by_program_status(rows, "active"),
            [rows[0]],
        )
