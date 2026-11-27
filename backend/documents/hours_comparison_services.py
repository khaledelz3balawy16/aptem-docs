import math

from django.db import connection

from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PAGE_SIZE = 20
AL_FANAR_PROGRAM = "project control professional level 6 - al fanar"


def _comparison_state(row):
    values = (
        row["ilr_planned_hours"],
        row["training_plan_planned_hours"],
        row["apprenticeship_agreement_planned_hours"],
    )
    missing_labels = [
        label
        for label, value in zip(
            ("ILR", "Training Plan", "Apprenticeship Agreement"), values
        )
        if value is None
    ]
    if missing_labels:
        row["comparison_status"] = "missing"
        row["is_matched"] = False
        row["comparison_reason"] = f"Missing: {', '.join(missing_labels)}"
    elif values[0] == values[1] == values[2]:
        row["comparison_status"] = "matched"
        row["is_matched"] = True
        row["comparison_reason"] = "All three planned-hours values match"
    else:
        row["comparison_status"] = "mismatched"
        row["is_matched"] = False
        row["comparison_reason"] = "The three planned-hours values do not match"


def list_planned_hours_comparisons(
    page=1,
    search="",
    comparison_filter="all",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_filter = str(comparison_filter or "all").strip().lower()
    if normalized_filter not in {"all", "matched", "mismatched", "missing"}:
        raise ValueError("Invalid comparison filter.")

    params = []
    search_condition = ""
    if search.strip():
        pattern = f"%{search.strip()}%"
        search_condition = """
            AND (
                ilr.full_name ILIKE %s
                OR ilr.email ILIKE %s
                OR COALESCE(aptem.program_name, '') ILIKE %s
            )
        """
        params.extend([pattern, pattern, pattern])

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH ranked_ilr AS (
                SELECT
                    delivery.id,
                    delivery.learn_ref_number,
                    delivery.given_names,
                    delivery.family_name,
                    delivery.email,
                    delivery.planned_hours,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(delivery.email))
                        ORDER BY (delivery.aim_type = 1) DESC,
                                 (delivery.planned_hours IS NOT NULL) DESC,
                                 delivery.updated_at DESC NULLS LAST,
                                 delivery.id DESC
                    ) AS learner_row
                FROM "Audit".ilr_learning_deliveries delivery
                WHERE NULLIF(TRIM(delivery.email), '') IS NOT NULL
            ),
            ilr AS (
                SELECT
                    id,
                    learn_ref_number,
                    CONCAT_WS(' ', given_names, family_name) AS full_name,
                    email,
                    planned_hours::numeric AS ilr_planned_hours
                FROM ranked_ilr
                WHERE learner_row = 1
            )
            SELECT
                ilr.learn_ref_number,
                ilr.full_name,
                ilr.email,
                aptem.aptem_id::text AS learner_id,
                aptem.program_name,
                aptem.program_status,
                ilr.ilr_planned_hours,
                aptem.training_plan_planned_hours,
                aptem.apprenticeship_agreement_planned_hours
            FROM ilr
            LEFT JOIN LATERAL (
                SELECT
                    learner_match.aptem_id,
                    COALESCE(
                        document_learner.program_name,
                        NULLIF(aptem_user."Program Name", '')
                    ) AS program_name,
                    COALESCE(
                        document_learner.program_status,
                        NULLIF(aptem_user."Program-Status", '')
                    ) AS program_status,
                    training_plan.training_plan_planned_hours,
                    agreement.apprenticeship_agreement_planned_hours
                FROM "Audit".learner_match learner_match
                LEFT JOIN "LMS"."Aptem_users" aptem_user
                    ON aptem_user."ID" = learner_match.aptem_id
                LEFT JOIN LATERAL (
                    SELECT
                        COALESCE(
                            MAX(NULLIF(document.current_programme, '')),
                            (
                                ARRAY_AGG(
                                    NULLIF(document.program_name, '')
                                    ORDER BY (
                                        document.document_name IN (
                                            'Training Plan',
                                            'Training Plan 25/26',
                                            'Apprenticeship Agreement'
                                        )
                                    ) DESC,
                                    document.date DESC NULLS LAST,
                                    document.id DESC
                                ) FILTER (
                                    WHERE NULLIF(document.program_name, '') IS NOT NULL
                                )
                            )[1]
                        ) AS program_name,
                        MAX(NULLIF(document.program_status, '')) AS program_status
                    FROM fetching_evidence.aptem_cv_contracts_probe document
                    WHERE document.learner_id = learner_match.aptem_id
                ) document_learner ON TRUE
                LEFT JOIN LATERAL (
                    SELECT document.training_plan_planned_hours
                    FROM fetching_evidence.aptem_cv_contracts_probe document
                    WHERE document.learner_id = learner_match.aptem_id
                      AND document.document_name IN ('Training Plan', 'Training Plan 25/26')
                      AND LOWER(TRIM(document.program_name)) = LOWER(TRIM(COALESCE(
                            document_learner.program_name,
                            NULLIF(aptem_user."Program Name", '')
                      )))
                    ORDER BY COALESCE(
                        document.fully_signed_date,
                        document.learner_signed_date,
                        document.date
                    ) DESC NULLS LAST,
                    document.id DESC
                    LIMIT 1
                ) training_plan ON TRUE
                LEFT JOIN LATERAL (
                    SELECT document.apprenticeship_agreement_planned_hours
                    FROM fetching_evidence.aptem_cv_contracts_probe document
                    WHERE document.learner_id = learner_match.aptem_id
                      AND document.document_name = 'Apprenticeship Agreement'
                      AND LOWER(TRIM(document.program_name)) = LOWER(TRIM(COALESCE(
                            document_learner.program_name,
                            NULLIF(aptem_user."Program Name", '')
                      )))
                    ORDER BY COALESCE(
                        document.fully_signed_date,
                        document.learner_signed_date,
                        document.date
                    ) DESC NULLS LAST,
                    document.id DESC
                    LIMIT 1
                ) agreement ON TRUE
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
            [AL_FANAR_PROGRAM, *params],
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for row in rows:
        _comparison_state(row)

    rows = filter_rows_by_program_status(rows, program_status)

    summary_rows = rows
    summary = {
        "learners": len(summary_rows),
        "matched": sum(row["comparison_status"] == "matched" for row in summary_rows),
        "mismatched": sum(
            row["comparison_status"] == "mismatched" for row in summary_rows
        ),
        "missingValues": sum(
            row["comparison_status"] == "missing" for row in summary_rows
        ),
    }

    if normalized_filter != "all":
        rows = [
            row for row in rows if row["comparison_status"] == normalized_filter
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
