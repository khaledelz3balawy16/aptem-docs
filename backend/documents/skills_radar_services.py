import json
import math
import re
from datetime import date
from decimal import Decimal

from django.db import connection

from .funding_comparison_services import _decimal_value, _ilr_finance_state
from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PAGE_SIZE = 20
AL_FANAR_PROGRAM = "project control professional level 6 - al fanar"
TEST_TOKEN = re.compile('CHANGE_ME', re.IGNORECASE)


def _skills_radar_state(row):
    records = row.get("app_fin_records", None)
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except json.JSONDecodeError:
            records = None
    records = records if isinstance(records, list) else []

    dated_totals = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("AFinType") or "").strip().upper() != "TNP":
            continue
        try:
            record_date = date.fromisoformat(str(record.get("AFinDate") or ""))
        except ValueError:
            continue
        amount = _decimal_value(record.get("AFinAmount"))
        if amount is None:
            continue
        dated_totals[record_date] = dated_totals.get(record_date, Decimal("0")) + amount

    ordered_totals = sorted(dated_totals.items())
    original_funding = ordered_totals[0][1] if ordered_totals else None
    latest_funding = ordered_totals[-1][1] if ordered_totals else None
    reduction = (
        max(original_funding - latest_funding, Decimal("0"))
        if original_funding is not None and latest_funding is not None
        else None
    )
    reduction_percentage = (
        reduction / original_funding * Decimal("100")
        if reduction is not None and original_funding
        else None
    )

    _ilr_finance_state(row)

    ilr_hours = row.get("ilr_planned_hours")
    if ilr_hours is not None:
        ilr_hours = Decimal(str(ilr_hours))
        row["ilr_planned_hours"] = ilr_hours

    row["original_ilr_funding"] = original_funding
    row["funding_snapshot_count"] = len(ordered_totals)
    row["funding_reduction"] = reduction
    row["funding_reduction_percentage"] = reduction_percentage
    row["has_funding_reduction"] = bool(reduction and reduction > 0)

    finance_items = row.get("ilr_finance_items", {})
    row["ilr_training_amount"] = (
        sum(
            (value for code, value in finance_items.items() if str(code) in {"1", "3"}),
            Decimal("0"),
        )
        if finance_items
        else None
    )
    row["ilr_epa_amount"] = (
        sum(
            (value for code, value in finance_items.items() if str(code) in {"2", "4"}),
            Decimal("0"),
        )
        if finance_items
        else None
    )
    return row


def _is_test_row(row):
    return any(
        TEST_TOKEN.search(str(row.get(field) or ""))
        for field in ("full_name", "program_name")
    )


def list_skills_radar_audit(
    page=1,
    search="",
    radar_filter="all",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_filter = str(radar_filter or "all").strip().lower()
    if normalized_filter not in {"all", "assessed", "reduced", "missing"}:
        raise ValueError("Invalid Skills Radar filter.")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH ranked_ilr AS (
                SELECT
                    delivery.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(delivery.email))
                        ORDER BY (delivery.aim_type = 1) DESC,
                                 delivery.learn_start_date DESC NULLS LAST,
                                 (delivery.planned_hours IS NOT NULL) DESC,
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
                CONCAT_WS(' ', ilr.given_names, ilr.family_name) AS full_name,
                ilr.email,
                ilr.learn_start_date,
                ilr.planned_hours::numeric AS ilr_planned_hours,
                ilr.app_fin_records,
                learner.aptem_id::text AS learner_id,
                aptem.program_name,
                aptem.program_status,
                radar.competency_name,
                radar.score_percentage,
                radar.average_level,
                radar.assessed_items,
                radar.total_items,
                radar.latest_assessment_date
            FROM ilr
            LEFT JOIN LATERAL (
                SELECT learner_match.aptem_id
                FROM "Audit".learner_match learner_match
                WHERE LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                   OR LOWER(REGEXP_REPLACE(TRIM(learner_match.learner_name), '\\s+', ' ', 'g'))
                      = LOWER(REGEXP_REPLACE(
                          TRIM(CONCAT_WS(' ', ilr.given_names, ilr.family_name)),
                          '\\s+', ' ', 'g'
                        ))
                ORDER BY (
                    LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                ) DESC,
                learner_match.aptem_id DESC
                LIMIT 1
            ) learner ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    COALESCE(
                        NULLIF(document.current_programme, ''),
                        NULLIF(document.program_name, '')
                    ) AS program_name,
                    NULLIF(document.program_status, '') AS program_status
                FROM fetching_evidence.aptem_cv_contracts_probe document
                WHERE document.learner_id = learner.aptem_id
                ORDER BY (NULLIF(document.current_programme, '') IS NOT NULL) DESC,
                         document.fetched_at DESC NULLS LAST,
                         document.id DESC
                LIMIT 1
            ) aptem ON TRUE
            LEFT JOIN LATERAL (
                WITH radar_rows AS (
                    SELECT
                        source.*,
                        level_range.maximum_level
                    FROM fetching_evidence.aptem_skills_radar_probe source
                    LEFT JOIN LATERAL (
                        SELECT MAX((level_item ->> 'level')::numeric) AS maximum_level
                        FROM JSONB_ARRAY_ELEMENTS(source.levels) level_item
                    ) level_range ON TRUE
                    WHERE source.learner_id = learner.aptem_id
                ),
                competency_scores AS (
                    SELECT
                        competency_id,
                        MAX(competency_name) AS competency_name,
                        COUNT(*) AS total_items,
                        COUNT(assessed_level) AS assessed_items,
                        ROUND(AVG(assessed_level)::numeric, 2) AS average_level,
                        ROUND(
                            AVG(
                                assessed_level::numeric
                                / NULLIF(maximum_level, 0)
                            ) * 100,
                            1
                        ) AS score_percentage,
                        MAX(latest_completed_date) AS latest_assessment_date,
                        MAX(fetched_at) AS latest_fetch
                    FROM radar_rows
                    GROUP BY competency_id
                )
                SELECT *
                FROM competency_scores
                ORDER BY latest_assessment_date DESC NULLS LAST,
                         latest_fetch DESC NULLS LAST,
                         competency_id DESC
                LIMIT 1
            ) radar ON TRUE
            WHERE LOWER(TRIM(COALESCE(aptem.program_name, '')))
                  IS DISTINCT FROM %s
            ORDER BY full_name ASC, ilr.learn_ref_number ASC
            """,
            [AL_FANAR_PROGRAM],
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, record)) for record in cursor.fetchall()]

    rows = [_skills_radar_state(row) for row in rows]
    rows = [row for row in rows if not _is_test_row(row)]

    normalized_search = search.strip().lower()
    if normalized_search:
        rows = [
            row
            for row in rows
            if normalized_search
            in " ".join(
                str(row.get(key) or "")
                for key in (
                    "full_name",
                    "email",
                    "program_name",
                    "learn_ref_number",
                    "competency_name",
                )
            ).lower()
        ]

    rows = filter_rows_by_program_status(rows, program_status)

    summary = {
        "learners": len(rows),
        "radarAssessed": sum(row.get("score_percentage") is not None for row in rows),
        "fundingReduced": sum(row["has_funding_reduction"] for row in rows),
        "fundingAvailable": sum(row.get("ilr_finance_total") is not None for row in rows),
    }

    if normalized_filter == "assessed":
        rows = [row for row in rows if row.get("score_percentage") is not None]
    elif normalized_filter == "reduced":
        rows = [row for row in rows if row["has_funding_reduction"]]
    elif normalized_filter == "missing":
        rows = [row for row in rows if row.get("score_percentage") is None]

    total = len(rows)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    current_page = min(safe_page, pages)
    start = (current_page - 1) * PAGE_SIZE

    return {
        "rows": rows[start : start + PAGE_SIZE],
        "summary": summary,
        "pagination": {
            "page": current_page,
            "pages": pages,
            "pageSize": PAGE_SIZE,
            "total": total,
        },
        "activeFilter": normalized_filter,
        "activeProgramStatus": normalize_program_status(program_status),
        "programStatuses": list_program_statuses(),
    }
