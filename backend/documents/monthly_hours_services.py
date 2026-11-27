import json
import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import connection

from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PAGE_SIZE = 20
MIN_YEAR = 2024
MAX_YEAR_OFFSET = 5
AL_FANAR_PROGRAM = "project control professional level 6 - al fanar"
TEST_TOKEN = re.compile('CHANGE_ME', re.IGNORECASE)
MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _hour_value(value):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite():
        return None
    return float(number)


def _available_years(rows, today=None):
    today = today or date.today()
    maximum_year = today.year + MAX_YEAR_OFFSET
    years = set()
    for row in rows:
        for field in ("planned_hours_monthly", "completed_hours_monthly"):
            for key in _json_object(row.get(field)):
                match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", str(key))
                if match and MIN_YEAR <= int(match.group(1)) <= maximum_year:
                    years.add(int(match.group(1)))
    return sorted(years)


def _select_year(requested_year, available_years, today=None):
    today = today or date.today()
    if requested_year not in (None, ""):
        selected = int(requested_year)
        if selected < MIN_YEAR or selected > today.year + MAX_YEAR_OFFSET:
            raise ValueError("Invalid monthly-hours year.")
        return selected
    if today.year in available_years:
        return today.year
    return max(available_years, default=today.year)


def _monthly_state(row, year):
    planned = _json_object(row.pop("planned_hours_monthly", {}))
    completed = _json_object(row.pop("completed_hours_monthly", {}))
    months = []
    planned_values = []
    completed_values = []

    for month, label in enumerate(MONTH_LABELS, start=1):
        key = f"{year}-{month:02d}"
        planned_value = _hour_value(planned.get(key))
        completed_value = _hour_value(completed.get(key))
        if planned_value is not None:
            planned_values.append(planned_value)
        if completed_value is not None:
            completed_values.append(completed_value)
        months.append(
            {
                "key": key,
                "label": label,
                "planned": planned_value,
                "completed": completed_value,
            }
        )

    row["months"] = months
    row["planned_total"] = sum(planned_values) if planned_values else None
    row["completed_total"] = sum(completed_values) if completed_values else None
    row["has_hours"] = bool(planned_values or completed_values)
    return row


def _is_test_row(row):
    return any(
        TEST_TOKEN.search(str(row.get(field) or ""))
        for field in ("full_name", "program_name")
    )


def list_monthly_hours(
    page=1,
    search="",
    year="",
    hours_filter="all",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_filter = str(hours_filter or "all").strip().lower()
    if normalized_filter not in {"all", "with-hours", "no-hours"}:
        raise ValueError("Invalid monthly-hours filter.")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH ranked_ilr AS (
                SELECT
                    delivery.id,
                    delivery.learn_ref_number,
                    delivery.given_names,
                    delivery.family_name,
                    delivery.email,
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
                    email
                FROM ranked_ilr
                WHERE learner_row = 1
            )
            SELECT
                ilr.learn_ref_number AS row_key,
                aptem.aptem_id::text AS learner_id,
                ilr.full_name,
                ilr.email,
                aptem.program_name,
                aptem.program_status,
                monthly.planned_hours_monthly,
                monthly.completed_hours_monthly,
                monthly.updated_at
            FROM ilr
            LEFT JOIN LATERAL (
                SELECT
                    learner_match.aptem_id,
                    COALESCE(
                        NULLIF(aptem_user."Program Name", ''),
                        NULLIF(current_document.program_name, '')
                    ) AS program_name,
                    COALESCE(
                        NULLIF(current_document.program_status, ''),
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
                    ORDER BY document.fetched_at DESC NULLS LAST, document.id DESC
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
            LEFT JOIN fetching_evidence.learner_hours_monthly monthly
                ON monthly.learner_id = aptem.aptem_id
            WHERE LOWER(TRIM(COALESCE(aptem.program_name, '')))
                  IS DISTINCT FROM %s
            ORDER BY ilr.full_name ASC, ilr.learn_ref_number ASC
            """
            ,
            [AL_FANAR_PROGRAM],
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, record)) for record in cursor.fetchall()]

    rows = [row for row in rows if not _is_test_row(row)]
    available_years = _available_years(rows)
    active_year = _select_year(year, available_years)
    rows = [_monthly_state(row, active_year) for row in rows]

    search_value = str(search or "").strip().lower()
    if search_value:
        rows = [
            row
            for row in rows
            if search_value in str(row.get("full_name") or "").lower()
            or search_value in str(row.get("program_name") or "").lower()
            or search_value in str(row.get("learner_id") or "").lower()
        ]

    rows = filter_rows_by_program_status(rows, program_status)
    summary = {
        "learners": len(rows),
        "withHours": sum(row["has_hours"] for row in rows),
        "withoutHours": sum(not row["has_hours"] for row in rows),
        "plannedHours": round(sum(row["planned_total"] or 0 for row in rows), 2),
        "completedHours": round(sum(row["completed_total"] or 0 for row in rows), 2),
    }

    if normalized_filter == "with-hours":
        rows = [row for row in rows if row["has_hours"]]
    elif normalized_filter == "no-hours":
        rows = [row for row in rows if not row["has_hours"]]

    total = len(rows)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    safe_page = min(safe_page, pages)
    offset = (safe_page - 1) * PAGE_SIZE

    return {
        "rows": rows[offset : offset + PAGE_SIZE],
        "summary": summary,
        "months": [
            {"key": f"{active_year}-{month:02d}", "label": label}
            for month, label in enumerate(MONTH_LABELS, start=1)
        ],
        "availableYears": available_years,
        "activeYear": active_year,
        "activeFilter": normalized_filter,
        "activeProgramStatus": normalize_program_status(program_status),
        "programStatuses": list_program_statuses(),
        "pagination": {
            "page": safe_page,
            "pageSize": PAGE_SIZE,
            "total": total,
            "pages": pages,
        },
    }
