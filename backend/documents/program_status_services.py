from django.db import connection


ALL_PROGRAM_STATUSES = "all"


def normalize_program_status(value):
    normalized = str(value or ALL_PROGRAM_STATUSES).strip().lower()
    return normalized or ALL_PROGRAM_STATUSES


def filter_rows_by_program_status(rows, program_status):
    normalized = normalize_program_status(program_status)
    if normalized == ALL_PROGRAM_STATUSES:
        return rows
    return [
        row
        for row in rows
        if str(row.get("program_status") or "").strip().lower() == normalized
    ]


def list_program_statuses():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MIN(status) AS status
            FROM (
                SELECT NULLIF(TRIM(program_status), '') AS status
                FROM fetching_evidence.aptem_cv_contracts_probe
            ) statuses
            WHERE status IS NOT NULL
            GROUP BY LOWER(status)
            ORDER BY LOWER(MIN(status))
            """
        )
        return [row[0] for row in cursor.fetchall()]
