import math

from django.db import connection

from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PAGE_SIZE = 20


def _start_evidence_dates_match(row):
    return bool(
        row["learn_start_date"]
        and row["first_evidence_date"]
        and row["learn_start_date"] == row["first_evidence_date"]
    )


def _start_evidence_dates_mismatch(row):
    return bool(
        row["learn_start_date"]
        and row["first_evidence_date"]
        and row["learn_start_date"] != row["first_evidence_date"]
    )


def _match_reason(row):
    if not row["learn_start_date"]:
        return "ILR start date is missing"
    if not row["apprenticeship_agreement_date"] and not row["first_evidence_date"]:
        return "Apprenticeship Agreement and evidence dates are missing"
    if not row["apprenticeship_agreement_date"]:
        return "Apprenticeship Agreement date is missing"
    if not row["first_evidence_date"]:
        return "No evidence was found on or after the start date"
    if row["is_matched"]:
        return "Apprenticeship Agreement is on or before start; evidence is on or after start"
    if row["apprenticeship_agreement_date"] > row["learn_start_date"]:
        return "Apprenticeship Agreement was signed after the start date"
    return "The evidence date is before the start date"


def list_start_date_comparisons(
    page=1,
    search="",
    comparison_filter="all",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_filter = str(comparison_filter or "all").strip().lower()
    if normalized_filter not in {
        "all",
        "matched",
        "not-matched",
        "missing",
        "evidence-matched",
        "evidence-mismatched",
    }:
        raise ValueError("Invalid comparison filter.")
    params = []
    search_condition = ""

    if search.strip():
        pattern = f"%{search.strip()}%"
        search_condition = """
            WHERE ilr.full_name ILIKE %s
               OR ilr.email ILIKE %s
               OR COALESCE(aptem.program_name, '') ILIKE %s
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
                    delivery.learn_start_date,
                    delivery.learn_plan_end_date,
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
                    learn_start_date,
                    learn_plan_end_date,
                    planned_hours
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
                ilr.learn_start_date,
                apprenticeship_agreement.signed_date AS apprenticeship_agreement_date,
                apprenticeship_agreement.document_id::text AS apprenticeship_agreement_document_id,
                apprenticeship_agreement.is_manual AS apprenticeship_agreement_date_is_manual,
                COALESCE(
                    apprenticeship_agreement.is_selected_version
                    AND apprenticeship_agreement.signed_date <= ilr.learn_start_date,
                    FALSE
                ) AS apprenticeship_agreement_date_is_pre_start_version,
                COALESCE(
                    apprenticeship_agreement.is_selected_version
                    AND apprenticeship_agreement.signed_date > ilr.learn_start_date,
                    FALSE
                ) AS apprenticeship_agreement_date_is_after_start_version,
                first_evidence.evidence_date AS first_evidence_date,
                first_evidence.evidence_name AS first_evidence_name,
                (
                    ilr.learn_start_date IS NOT NULL
                    AND apprenticeship_agreement.signed_date <= ilr.learn_start_date
                    AND first_evidence.evidence_date >= ilr.learn_start_date
                ) AS is_matched
            FROM ilr
            LEFT JOIN LATERAL (
                SELECT
                    learner_match.aptem_id,
                    COALESCE(
                        NULLIF(aptem_user."Program Name", ''),
                        NULLIF(document_learner.program_name, '')
                    ) AS program_name,
                    COALESCE(
                        NULLIF(document_learner.program_status, ''),
                        NULLIF(aptem_user."Program-Status", '')
                    ) AS program_status
                FROM "Audit".learner_match learner_match
                LEFT JOIN "LMS"."Aptem_users" aptem_user
                    ON aptem_user."ID" = learner_match.aptem_id
                LEFT JOIN LATERAL (
                    SELECT COALESCE(
                        NULLIF(document.current_programme, ''),
                        NULLIF(document.program_name, '')
                    ) AS program_name,
                    NULLIF(document.program_status, '') AS program_status
                    FROM fetching_evidence.aptem_cv_contracts_probe document
                    WHERE document.learner_id = learner_match.aptem_id
                    ORDER BY document.fetched_at DESC NULLS LAST, document.id DESC
                    LIMIT 1
                ) document_learner ON TRUE
                WHERE LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                   OR LOWER(REGEXP_REPLACE(TRIM(learner_match.learner_name), '\\s+', ' ', 'g'))
                      = LOWER(REGEXP_REPLACE(TRIM(ilr.full_name), '\\s+', ' ', 'g'))
                ORDER BY (
                    LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                ) DESC,
                learner_match.aptem_id DESC
                LIMIT 1
            ) aptem ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    document.id AS document_id,
                    CASE
                        WHEN document.comparison_apprenticeship_agreement_date IS NOT NULL
                        THEN document.comparison_apprenticeship_agreement_date
                        WHEN document.apprenticeship_agreement_version_created_at IS NOT NULL
                        THEN document.apprenticeship_agreement_version_created_at::date
                        WHEN COALESCE(document.status, '') ILIKE '%%signed%%'
                          OR COALESCE(document.status, '') ILIKE '%%verified%%'
                        THEN document.date::date
                    END AS signed_date,
                    (document.comparison_apprenticeship_agreement_date IS NOT NULL) AS is_manual,
                    (
                        document.comparison_apprenticeship_agreement_date IS NULL
                        AND document.apprenticeship_agreement_version_id IS NOT NULL
                    ) AS is_selected_version
                FROM fetching_evidence.aptem_cv_contracts_probe document
                WHERE document.learner_id = aptem.aptem_id
                  AND LOWER(TRIM(document.document_name)) = 'apprenticeship agreement'
                ORDER BY
                    (document.comparison_apprenticeship_agreement_date IS NOT NULL) DESC,
                    document.date DESC NULLS LAST,
                    document.id DESC
                LIMIT 1
            ) apprenticeship_agreement ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    candidate.evidence_date,
                    candidate.evidence_name
                FROM fetching_evidence.learner_evidence learner_evidence
                CROSS JOIN LATERAL JSONB_ARRAY_ELEMENTS(
                    COALESCE(learner_evidence.evidence, '[]'::jsonb)
                ) evidence_item
                CROSS JOIN LATERAL (
                    SELECT
                        COALESCE(
                            CASE
                                WHEN COALESCE(evidence_item->>'created_date', '')
                                     ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                                THEN LEFT(evidence_item->>'created_date', 10)::date
                            END,
                            CASE
                                WHEN COALESCE(evidence_item#>>'{{raw,SubmissionDate}}', '')
                                     ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                                THEN LEFT(evidence_item#>>'{{raw,SubmissionDate}}', 10)::date
                            END,
                            CASE
                                WHEN COALESCE(evidence_item#>>'{{raw,CompletedDate}}', '')
                                     ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                                THEN LEFT(evidence_item#>>'{{raw,CompletedDate}}', 10)::date
                            END
                        ) AS evidence_date,
                        COALESCE(
                            NULLIF(evidence_item->>'name', ''),
                            NULLIF(evidence_item#>>'{{raw,EvidenceName}}', ''),
                            'Evidence'
                        ) AS evidence_name,
                        COALESCE((evidence_item->>'id')::bigint, 0) AS evidence_id
                ) candidate
                WHERE learner_evidence.learner_id = aptem.aptem_id
                  AND candidate.evidence_date >= ilr.learn_start_date
                ORDER BY candidate.evidence_date ASC, candidate.evidence_id ASC
                LIMIT 1
            ) first_evidence ON TRUE
            {search_condition}
            ORDER BY ilr.full_name ASC, ilr.learn_ref_number ASC
            """,
            params,
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for row in rows:
        row["start_evidence_dates_match"] = _start_evidence_dates_match(row)
        row["start_evidence_dates_mismatch"] = _start_evidence_dates_mismatch(row)
        row["match_reason"] = _match_reason(row)

    rows = filter_rows_by_program_status(rows, program_status)

    summary_rows = rows
    matched = sum(1 for row in summary_rows if row["is_matched"])
    evidence_matched = sum(
        1 for row in summary_rows if row["start_evidence_dates_match"]
    )
    evidence_mismatched = sum(
        1 for row in summary_rows if row["start_evidence_dates_mismatch"]
    )
    missing = sum(
        1
        for row in summary_rows
        if not row["apprenticeship_agreement_date"] or not row["first_evidence_date"]
    )

    if normalized_filter == "matched":
        rows = [row for row in rows if row["is_matched"]]
    elif normalized_filter == "not-matched":
        rows = [row for row in rows if not row["is_matched"]]
    elif normalized_filter == "missing":
        rows = [
            row
            for row in rows
            if not row["apprenticeship_agreement_date"] or not row["first_evidence_date"]
        ]
    elif normalized_filter == "evidence-matched":
        rows = [row for row in rows if row["start_evidence_dates_match"]]
    elif normalized_filter == "evidence-mismatched":
        rows = [row for row in rows if row["start_evidence_dates_mismatch"]]

    total = len(rows)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    safe_page = min(safe_page, pages)
    offset = (safe_page - 1) * PAGE_SIZE
    page_rows = rows[offset : offset + PAGE_SIZE]

    return {
        "rows": page_rows,
        "summary": {
            "learners": len(summary_rows),
            "matched": matched,
            "notMatched": len(summary_rows) - matched,
            "missingDates": missing,
            "evidenceMatched": evidence_matched,
            "evidenceMismatched": evidence_mismatched,
        },
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


def update_apprenticeship_agreement_date(document_id, agreement_date):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE fetching_evidence.aptem_cv_contracts_probe
            SET comparison_apprenticeship_agreement_date = %s
            WHERE id = %s
              AND LOWER(TRIM(document_name)) = 'apprenticeship agreement'
            RETURNING id::text
            """,
            [agreement_date, document_id],
        )
        row = cursor.fetchone()
        return row[0] if row else None
