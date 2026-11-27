import json
from decimal import Decimal

from django.db import connection

from .funding_comparison_services import _decimal_value, _ilr_finance_state
from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PRIOR_LEARNING_LEARNERS = (
    "Stephen Burns",
    "Barry McLaughlin",
    "Karan Mandanna",
    "Kayleigh Hill",
    "Jennifer Caine",
    "Beatrice Piazza",
    "Adam Wheeler",
    "Kate Mclellan",
    "Ashley Nunes",
    "Eleanor Imray",
    "Amir Emran Soltani",
    "Emily Dowd",
    "Abbie Ridgway",
)


def _funding_value(funding, key):
    item = funding.get(key) if isinstance(funding, dict) else None
    return _decimal_value(item.get("value")) if isinstance(item, dict) else None


def _prior_learning_state(row):
    _ilr_finance_state(row)

    funding = row.pop("written_agreement_funding", None)
    if isinstance(funding, str):
        try:
            funding = json.loads(funding)
        except json.JSONDecodeError:
            funding = None

    ilr_items = row.get("ilr_finance_items", {})
    row["ilr_training_amount"] = sum(
        (value for code, value in ilr_items.items() if str(code) in {"1", "3"}),
        Decimal("0"),
    ) if ilr_items else None
    row["ilr_epa_amount"] = sum(
        (value for code, value in ilr_items.items() if str(code) in {"2", "4"}),
        Decimal("0"),
    ) if ilr_items else None

    row["agreement_actual_funding"] = _funding_value(funding, "actual_funding")
    row["agreement_epa"] = _funding_value(funding, "end_point_assessment")
    row["agreement_total"] = _funding_value(
        funding, "total_price_of_apprenticeship"
    )
    row["agreement_band_maximum"] = _funding_value(
        funding, "funding_band_maximum_value"
    )

    minimum = row.get("aptem_minimum_hours")
    planned = row.get("aptem_planned_hours")
    row["minimum_planned_difference"] = (
        minimum - planned if minimum is not None and planned is not None else None
    )
    row["funding_reduction_from_band"] = (
        row["agreement_band_maximum"] - row["agreement_total"]
        if row["agreement_band_maximum"] is not None
        and row["agreement_total"] is not None
        else None
    )
    row["funding_difference"] = (
        row["ilr_finance_total"] - row["agreement_total"]
        if row["ilr_finance_total"] is not None
        and row["agreement_total"] is not None
        else None
    )

    if row.get("ilr_planned_hours") is None or planned is None:
        row["hours_status"] = "missing"
        row["hours_reason"] = "ILR or Aptem planned hours are missing"
    elif row["ilr_planned_hours"] == planned:
        row["hours_status"] = "matched"
        row["hours_reason"] = "ILR and Aptem planned hours match"
    else:
        row["hours_status"] = "mismatched"
        row["hours_reason"] = "ILR and Aptem planned hours differ"

    if row["ilr_finance_total"] is None or row["agreement_total"] is None:
        row["funding_status"] = "missing"
        row["funding_reason"] = "ILR or Written Agreement total is missing"
    elif row["ilr_finance_total"] == row["agreement_total"]:
        row["funding_status"] = "matched"
        row["funding_reason"] = "ILR and Written Agreement totals match"
    else:
        row["funding_status"] = "mismatched"
        row["funding_reason"] = "ILR and Written Agreement totals differ"
    return row


def list_prior_learning(
    search="",
    comparison_filter="all",
    program_status="all",
):
    normalized_filter = str(comparison_filter or "all").strip().lower()
    if normalized_filter not in {
        "all",
        "hours-matched",
        "hours-mismatched",
        "funding-matched",
        "funding-mismatched",
        "missing",
    }:
        raise ValueError("Invalid prior-learning filter.")

    names = [name.lower() for name in PRIOR_LEARNING_LEARNERS]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH ranked_ilr AS (
                SELECT
                    delivery.id,
                    delivery.learn_ref_number,
                    CONCAT_WS(' ', delivery.given_names, delivery.family_name) AS full_name,
                    delivery.email,
                    delivery.learn_start_date,
                    delivery.planned_hours::numeric AS ilr_planned_hours,
                    delivery.app_fin_records,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(delivery.email))
                        ORDER BY (delivery.aim_type = 1) DESC,
                                 delivery.learn_start_date DESC NULLS LAST,
                                 (delivery.planned_hours IS NOT NULL) DESC,
                                 delivery.updated_at DESC NULLS LAST,
                                 delivery.id DESC
                    ) AS learner_row
                FROM "Audit".ilr_learning_deliveries delivery
                WHERE LOWER(CONCAT_WS(' ', delivery.given_names, delivery.family_name))
                      = ANY(%s)
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
                ilr.ilr_planned_hours,
                ilr.app_fin_records,
                learner.aptem_id::text AS learner_id,
                aptem.program_id,
                aptem.program_name,
                aptem.program_status,
                aptem.minimum AS aptem_minimum_hours,
                aptem.planned AS aptem_planned_hours,
                training_plan.training_plan_planned_hours,
                apprenticeship_agreement.apprenticeship_agreement_planned_hours,
                written_agreement.document_name AS written_agreement_name,
                written_agreement.source_document_id AS written_agreement_document_id,
                written_agreement.file AS written_agreement_file,
                written_agreement.written_agreement_funding
            FROM ilr
            LEFT JOIN LATERAL (
                SELECT learner_match.aptem_id
                FROM "Audit".learner_match learner_match
                WHERE LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                   OR LOWER(REGEXP_REPLACE(TRIM(learner_match.learner_name), '\\s+', ' ', 'g'))
                      = LOWER(REGEXP_REPLACE(TRIM(ilr.full_name), '\\s+', ' ', 'g'))
                ORDER BY (
                    LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                ) DESC,
                learner_match.aptem_id DESC
                LIMIT 1
            ) learner ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    document.program_id,
                    COALESCE(
                        NULLIF(document.current_programme, ''),
                        NULLIF(document.program_name, '')
                    ) AS program_name,
                    NULLIF(document.program_status, '') AS program_status,
                    document.minimum,
                    document.planned
                FROM fetching_evidence.aptem_cv_contracts_probe document
                WHERE document.learner_id = learner.aptem_id
                ORDER BY (NULLIF(document.current_programme, '') IS NOT NULL) DESC,
                         COALESCE(
                            document.fully_signed_date,
                            document.learner_signed_date,
                            document.date
                         ) DESC NULLS LAST,
                         document.id DESC
                LIMIT 1
            ) aptem ON TRUE
            LEFT JOIN LATERAL (
                SELECT document.training_plan_planned_hours
                FROM fetching_evidence.aptem_cv_contracts_probe document
                WHERE document.learner_id = learner.aptem_id
                  AND document.program_id = aptem.program_id
                  AND LOWER(TRIM(document.document_name)) IN (
                    'training plan', 'training plan 25/26'
                  )
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
                WHERE document.learner_id = learner.aptem_id
                  AND document.program_id = aptem.program_id
                  AND LOWER(TRIM(document.document_name)) = 'apprenticeship agreement'
                ORDER BY COALESCE(
                    document.fully_signed_date,
                    document.learner_signed_date,
                    document.date
                ) DESC NULLS LAST,
                document.id DESC
                LIMIT 1
            ) apprenticeship_agreement ON TRUE
            LEFT JOIN LATERAL (
                SELECT document.*
                FROM fetching_evidence.aptem_cv_contracts_probe document
                WHERE document.learner_id = learner.aptem_id
                  AND document.program_id = aptem.program_id
                  AND LOWER(TRIM(document.document_name)) IN (
                    'written agreement', 'written agreement 25/26'
                  )
                ORDER BY COALESCE(
                    document.fully_signed_date,
                    document.learner_signed_date,
                    document.date
                ) DESC NULLS LAST,
                document.id DESC
                LIMIT 1
            ) written_agreement ON TRUE
            ORDER BY ilr.full_name ASC
            """,
            [names],
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, record)) for record in cursor.fetchall()]

    rows = [_prior_learning_state(row) for row in rows]
    order = {
        name.lower(): index for index, name in enumerate(PRIOR_LEARNING_LEARNERS)
    }
    rows.sort(key=lambda row: order.get(row["full_name"].lower(), len(order)))

    normalized_search = search.strip().lower()
    if normalized_search:
        rows = [
            row
            for row in rows
            if normalized_search
            in " ".join(
                str(row.get(key) or "")
                for key in ("full_name", "email", "program_name", "learn_ref_number")
            ).lower()
        ]

    rows = filter_rows_by_program_status(rows, program_status)

    summary = {
        "learners": len(rows),
        "hoursMatched": sum(row["hours_status"] == "matched" for row in rows),
        "hoursMismatched": sum(
            row["hours_status"] == "mismatched" for row in rows
        ),
        "fundingMatched": sum(
            row["funding_status"] == "matched" for row in rows
        ),
        "fundingMismatched": sum(
            row["funding_status"] == "mismatched" for row in rows
        ),
        "missingValues": sum(
            row["hours_status"] == "missing" or row["funding_status"] == "missing"
            for row in rows
        ),
    }

    if normalized_filter != "all":
        filters = {
            "hours-matched": lambda row: row["hours_status"] == "matched",
            "hours-mismatched": lambda row: row["hours_status"] == "mismatched",
            "funding-matched": lambda row: row["funding_status"] == "matched",
            "funding-mismatched": lambda row: row["funding_status"] == "mismatched",
            "missing": lambda row: (
                row["hours_status"] == "missing"
                or row["funding_status"] == "missing"
            ),
        }
        rows = [row for row in rows if filters[normalized_filter](row)]

    return {
        "rows": rows,
        "summary": summary,
        "activeFilter": normalized_filter,
        "activeProgramStatus": normalize_program_status(program_status),
        "programStatuses": list_program_statuses(),
    }
