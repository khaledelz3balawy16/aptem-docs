import math
from datetime import date

from django.db import connection

from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PAGE_SIZE = 20
AL_FANAR_PROGRAM = "project control professional level 6 - al fanar"


def _timeline_state(row, today=None):
    today = today or date.today()
    start_date = row.get("learn_start_date")
    planned_end_date = row.get("learn_plan_end_date")
    actual_end_date = row.get("learn_actual_end_date")

    if start_date is None or planned_end_date is None:
        row["timeline_status"] = "missing"
        row["timeline_reason"] = "ILR start or planned end date is missing"
    elif actual_end_date is not None:
        row["timeline_status"] = "completed"
        row["timeline_reason"] = "ILR actual end date is recorded"
    elif planned_end_date < today:
        row["timeline_status"] = "overdue"
        row["timeline_reason"] = "Planned end date has passed without an actual end date"
    else:
        row["timeline_status"] = "in-progress"
        row["timeline_reason"] = "Programme is before its planned end date"

    row["end_date_variance_days"] = (
        (actual_end_date - planned_end_date).days
        if actual_end_date is not None and planned_end_date is not None
        else None
    )
    return row


def list_endpoint_assessments(
    page=1,
    search="",
    timeline_filter="all",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_filter = str(timeline_filter or "all").strip().lower()
    if normalized_filter not in {
        "all",
        "completed",
        "in-progress",
        "overdue",
        "missing",
    }:
        raise ValueError("Invalid endpoint-assessment filter.")

    params = [AL_FANAR_PROGRAM]
    search_condition = ""
    if search.strip():
        pattern = f"%{search.strip()}%"
        search_condition = """
            AND (
                ilr.full_name ILIKE %s
                OR ilr.email ILIKE %s
                OR ilr.learn_ref_number ILIKE %s
                OR COALESCE(aptem.program_name, '') ILIKE %s
            )
        """
        params.extend([pattern, pattern, pattern, pattern])

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH ranked_ilr AS (
                SELECT
                    delivery.id,
                    delivery.learn_ref_number,
                    CONCAT_WS(' ', delivery.given_names, delivery.family_name) AS full_name,
                    delivery.email,
                    delivery.learn_start_date,
                    delivery.learn_plan_end_date,
                    delivery.learn_actual_end_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(delivery.email))
                        ORDER BY (delivery.aim_type = 1) DESC,
                                 delivery.learn_start_date DESC NULLS LAST,
                                 delivery.updated_at DESC NULLS LAST,
                                 delivery.id DESC
                    ) AS learner_row
                FROM "Audit".ilr_learning_deliveries delivery
                WHERE NULLIF(TRIM(delivery.email), '') IS NOT NULL
            ),
            ilr AS (
                SELECT * FROM ranked_ilr WHERE learner_row = 1
            )
            SELECT
                ilr.learn_ref_number AS row_key,
                ilr.learn_ref_number,
                ilr.full_name,
                ilr.email,
                ilr.learn_start_date,
                ilr.learn_plan_end_date,
                ilr.learn_actual_end_date,
                aptem.aptem_id::text AS learner_id,
                aptem.program_name,
                aptem.program_status
            FROM ilr
            LEFT JOIN LATERAL (
                SELECT
                    learner_match.aptem_id,
                    COALESCE(
                        current_document.program_name,
                        NULLIF(aptem_user."Program Name", '')
                    ) AS program_name,
                    COALESCE(
                        current_document.program_status,
                        NULLIF(aptem_user."Program-Status", '')
                    ) AS program_status
                FROM "Audit".learner_match learner_match
                LEFT JOIN "LMS"."Aptem_users" aptem_user
                    ON aptem_user."ID" = learner_match.aptem_id
                LEFT JOIN LATERAL (
                    SELECT
                        COALESCE(
                            NULLIF(document.current_programme, ''),
                            NULLIF(document.program_name, '')
                        ) AS program_name,
                        NULLIF(document.program_status, '') AS program_status
                    FROM fetching_evidence.aptem_cv_contracts_probe document
                    WHERE document.learner_id = learner_match.aptem_id
                    ORDER BY COALESCE(
                        document.fully_signed_date,
                        document.learner_signed_date,
                        document.date
                    ) DESC NULLS LAST,
                    document.id DESC
                    LIMIT 1
                ) current_document ON TRUE
                WHERE LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                   OR LOWER(REGEXP_REPLACE(TRIM(learner_match.learner_name), '\\s+', ' ', 'g'))
                      = LOWER(REGEXP_REPLACE(TRIM(ilr.full_name), '\\s+', ' ', 'g'))
                ORDER BY (
                    LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                ) DESC,
                learner_match.aptem_id DESC
                LIMIT 1
            ) aptem ON TRUE
            WHERE LOWER(TRIM(COALESCE(aptem.program_name, '')))
                  IS DISTINCT FROM %s
            {search_condition}
            ORDER BY ilr.full_name ASC, ilr.learn_ref_number ASC
            """,
            params,
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, record)) for record in cursor.fetchall()]

    rows = [_timeline_state(row) for row in rows]
    rows = filter_rows_by_program_status(rows, program_status)
    summary = {
        "learners": len(rows),
        "completed": sum(row["timeline_status"] == "completed" for row in rows),
        "inProgress": sum(
            row["timeline_status"] == "in-progress" for row in rows
        ),
        "overdue": sum(row["timeline_status"] == "overdue" for row in rows),
        "missingDates": sum(
            row["timeline_status"] == "missing" for row in rows
        ),
    }

    if normalized_filter != "all":
        rows = [
            row for row in rows if row["timeline_status"] == normalized_filter
        ]

    total = len(rows)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    safe_page = min(safe_page, pages)
    offset = (safe_page - 1) * PAGE_SIZE

    return {
        "rows": rows[offset : offset + PAGE_SIZE],
        "summary": summary,
        "pagination": {
            "page": safe_page,
            "pageSize": PAGE_SIZE,
            "total": total,
            "pages": pages,
        },
        "activeFilter": normalized_filter,
        "activeProgramStatus": normalize_program_status(program_status),
        "programStatuses": list_program_statuses(),
    }
