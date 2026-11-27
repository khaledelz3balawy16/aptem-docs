import json
import math
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import connection

from .program_status_services import (
    filter_rows_by_program_status,
    list_program_statuses,
    normalize_program_status,
)


PAGE_SIZE = 20
AL_FANAR_PROGRAM = "project control professional level 6 - al fanar"

COST_ITEMS = (
    ("training_delivery", "Training delivery"),
    ("distance_online_blended", "Distance / online learning"),
    ("english_maths", "English & maths"),
    ("assessment_progress_reviews", "Assessment / reviews"),
    ("registration_exam_certification", "Registration / certification"),
    ("materials", "Materials"),
    ("administration_including_epa", "Administration / EPA"),
    ("subcontractor_training", "Subcontractor training"),
    ("subcontractor_assessment", "Subcontractor assessment"),
    ("subcontractor_support", "Subcontractor support"),
    ("monitoring", "Monitoring"),
    ("end_point_assessment", "End Point Assessment"),
    ("apprenticeship_certification", "Apprenticeship certification"),
    ("external_quality_assurance", "External quality assurance"),
    ("other_non_fundable_costs", "Other non-fundable costs"),
)

REFERENCE_ITEMS = (
    ("funding_band_maximum", "Funding band maximum"),
    ("balance_due", "Balance due"),
    ("actual_funding", "Actual funding"),
)


def _has_display_value(value):
    return value is not None and value != Decimal("0")


def _visible_cost_items(rows):
    return [
        (key, label)
        for key, label in COST_ITEMS
        if any(
            _has_display_value(row.get("cost_items", {}).get(key)) for row in rows
        )
    ]


def _visible_reference_items(rows):
    return [
        (key, label)
        for key, label in REFERENCE_ITEMS
        if any(_has_display_value(row.get(key)) for row in rows)
    ]


def _decimal_value(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _ilr_finance_state(row):
    records = row.pop("app_fin_records", None)
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except json.JSONDecodeError:
            records = None
    records = records if isinstance(records, list) else []

    dated_tnp_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("AFinType") or "").strip().upper() != "TNP":
            continue
        try:
            record_date = date.fromisoformat(str(record.get("AFinDate") or ""))
        except ValueError:
            continue
        dated_tnp_records.append((record_date, record))

    if not dated_tnp_records:
        row["ilr_finance_date"] = None
        row["ilr_finance_items"] = {}
        row["ilr_finance_total"] = None
        return row

    latest_date = max(record_date for record_date, _record in dated_tnp_records)
    breakdown = {}
    for record_date, record in dated_tnp_records:
        if record_date != latest_date:
            continue
        code = str(record.get("AFinCode") or "").strip()
        amount = _decimal_value(record.get("AFinAmount"))
        if not code or amount is None:
            continue
        breakdown[code] = breakdown.get(code, Decimal("0")) + amount

    row["ilr_finance_date"] = latest_date
    row["ilr_finance_items"] = breakdown
    row["ilr_finance_total"] = sum(breakdown.values(), Decimal("0"))
    return row


def _code_sort_key(code):
    normalized = str(code)
    return (0, int(normalized)) if normalized.isdigit() else (1, normalized)


def _visible_ilr_finance_codes(rows):
    codes = {
        code
        for row in rows
        for code, value in row.get("ilr_finance_items", {}).items()
        if _has_display_value(value)
    }
    return sorted(codes, key=_code_sort_key)


def _funding_validation_state(row):
    funding = row.pop("written_agreement_funding", None)
    if isinstance(funding, str):
        try:
            funding = json.loads(funding)
        except json.JSONDecodeError:
            funding = None

    breakdown = funding.get("cost_breakdown") if isinstance(funding, dict) else None
    breakdown = breakdown if isinstance(breakdown, dict) else {}
    cost_values = {}
    missing_items = []
    calculated_total = Decimal("0")

    for key, label in COST_ITEMS:
        item = breakdown.get(key)
        if not isinstance(item, dict):
            missing_items.append(label)
            cost_values[key] = None
            continue
        value = _decimal_value(item.get("value"))
        cost_values[key] = value
        # A blank currency cell in the agreement is an explicit zero-value item.
        calculated_total += value if value is not None else Decimal("0")

    total_item = funding.get("total_price_of_apprenticeship") if isinstance(funding, dict) else None
    json_total = (
        _decimal_value(total_item.get("value"))
        if isinstance(total_item, dict)
        else None
    )
    funding_band_item = (
        funding.get("funding_band_maximum_value")
        if isinstance(funding, dict)
        else None
    )
    balance_item = funding.get("balance_due") if isinstance(funding, dict) else None
    actual_item = funding.get("actual_funding") if isinstance(funding, dict) else None

    row["cost_items"] = cost_values
    row["calculated_total"] = calculated_total if breakdown else None
    row["json_total"] = json_total
    row["funding_band_maximum"] = (
        _decimal_value(funding_band_item.get("value"))
        if isinstance(funding_band_item, dict)
        else None
    )
    row["balance_due"] = (
        _decimal_value(balance_item.get("value"))
        if isinstance(balance_item, dict)
        else None
    )
    row["actual_funding"] = (
        _decimal_value(actual_item.get("value"))
        if isinstance(actual_item, dict)
        else None
    )
    row["difference"] = (
        calculated_total - json_total
        if breakdown and json_total is not None and not missing_items
        else None
    )

    if not funding:
        row["comparison_status"] = "missing"
        row["comparison_reason"] = "Funding JSON is missing"
    elif not breakdown:
        row["comparison_status"] = "missing"
        row["comparison_reason"] = "Cost breakdown is missing"
    elif missing_items:
        row["comparison_status"] = "missing"
        row["comparison_reason"] = f"Missing cost item: {missing_items[0]}"
    elif json_total is None:
        row["comparison_status"] = "missing"
        row["comparison_reason"] = "JSON total is missing"
    elif calculated_total == json_total:
        row["comparison_status"] = "matched"
        row["comparison_reason"] = "Calculated items equal the JSON total"
    else:
        row["comparison_status"] = "mismatched"
        row["comparison_reason"] = "Calculated items do not equal the JSON total"
    row["agreement_comparison_status"] = row["comparison_status"]
    row["agreement_comparison_reason"] = row["comparison_reason"]
    return row


def _ilr_agreement_comparison_state(row):
    ilr_total = row.get("ilr_finance_total")
    agreement_total = row.get("json_total")
    row["ilr_agreement_difference"] = (
        ilr_total - agreement_total
        if ilr_total is not None and agreement_total is not None
        else None
    )

    if ilr_total is None:
        row["ilr_agreement_status"] = "missing"
        row["ilr_agreement_reason"] = "ILR TNP total is missing"
    elif agreement_total is None:
        row["ilr_agreement_status"] = "missing"
        row["ilr_agreement_reason"] = "Written Agreement total is missing"
    elif ilr_total == agreement_total:
        row["ilr_agreement_status"] = "matched"
        row["ilr_agreement_reason"] = "ILR and Written Agreement totals match"
    else:
        row["ilr_agreement_status"] = "mismatched"
        row["ilr_agreement_reason"] = "ILR and Written Agreement totals differ"
    return row


def list_funding_comparisons(
    page=1,
    search="",
    comparison_filter="all",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_filter = str(comparison_filter or "all").strip().lower()
    normalized_filter = {
        "matched": "agreement-matched",
        "mismatched": "agreement-mismatched",
    }.get(normalized_filter, normalized_filter)
    if normalized_filter not in {
        "all",
        "agreement-matched",
        "agreement-mismatched",
        "totals-matched",
        "totals-mismatched",
        "missing",
    }:
        raise ValueError("Invalid comparison filter.")

    params = [AL_FANAR_PROGRAM]
    search_condition = ""
    if search.strip():
        pattern = f"%{search.strip()}%"
        search_condition = """
            AND (
                ilr.full_name ILIKE %s
                OR ilr.email ILIKE %s
                OR COALESCE(
                    aptem.program_name,
                    ''
                ) ILIKE %s
                OR document.source_document_id::text ILIKE %s
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
                    delivery.standard_code,
                    delivery.programme_type,
                    delivery.app_fin_records,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(delivery.email))
                        ORDER BY (delivery.aim_type = 1) DESC,
                                 delivery.learn_start_date DESC NULLS LAST,
                                 (jsonb_array_length(COALESCE(
                                    delivery.app_fin_records,
                                    '[]'::jsonb
                                 )) > 0) DESC,
                                 delivery.updated_at DESC NULLS LAST,
                                 delivery.id DESC
                    ) AS learner_row
                FROM "Audit".ilr_learning_deliveries delivery
                WHERE NULLIF(TRIM(delivery.email), '') IS NOT NULL
            ),
            ilr AS (
                SELECT *
                FROM ranked_ilr
                WHERE learner_row = 1
            )
            SELECT
                COALESCE(document.id::text, 'ilr:' || ilr.learn_ref_number) AS row_key,
                document.id AS document_id,
                COALESCE(aptem.aptem_id::text, ilr.learn_ref_number) AS learner_id,
                ilr.learn_ref_number,
                ilr.full_name,
                ilr.email,
                aptem.program_name,
                aptem.program_status,
                ilr.learn_start_date AS ilr_program_start_date,
                ilr.standard_code AS ilr_standard_code,
                ilr.programme_type AS ilr_programme_type,
                document.document_name,
                document.source_document_id,
                document.file,
                COALESCE(
                    document.fully_signed_date,
                    document.learner_signed_date,
                    document.date
                ) AS agreement_date,
                document.written_agreement_funding,
                ilr.app_fin_records
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
                            NULLIF(candidate.current_programme, ''),
                            NULLIF(candidate.program_name, '')
                        ) AS program_name,
                        NULLIF(candidate.program_status, '') AS program_status
                    FROM fetching_evidence.aptem_cv_contracts_probe candidate
                    WHERE candidate.learner_id = learner_match.aptem_id
                    ORDER BY COALESCE(
                        candidate.fully_signed_date,
                        candidate.learner_signed_date,
                        candidate.date
                    ) DESC NULLS LAST,
                    candidate.id DESC
                    LIMIT 1
                ) current_document ON TRUE
                WHERE LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                   OR LOWER(REGEXP_REPLACE(
                        TRIM(learner_match.learner_name),
                        '\\s+', ' ', 'g'
                      )) = LOWER(REGEXP_REPLACE(
                        TRIM(ilr.full_name),
                        '\\s+', ' ', 'g'
                      ))
                ORDER BY (
                    LOWER(TRIM(learner_match.learner_email)) = LOWER(TRIM(ilr.email))
                ) DESC,
                learner_match.aptem_id DESC
                LIMIT 1
            ) aptem ON TRUE
            LEFT JOIN LATERAL (
                SELECT agreement.*
                FROM fetching_evidence.aptem_cv_contracts_probe agreement
                WHERE agreement.learner_id = aptem.aptem_id
                  AND LOWER(TRIM(agreement.document_name)) IN (
                    'written agreement', 'written agreement 25/26'
                  )
                ORDER BY COALESCE(
                    agreement.fully_signed_date,
                    agreement.learner_signed_date,
                    agreement.date
                ) DESC NULLS LAST,
                agreement.id DESC
                LIMIT 1
            ) document ON TRUE
            WHERE LOWER(TRIM(COALESCE(aptem.program_name, '')))
                    IS DISTINCT FROM %s
              {search_condition}
            ORDER BY ilr.full_name ASC,
                     ilr.learn_ref_number ASC
            """,
            params,
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, record)) for record in cursor.fetchall()]

    rows = [
        _ilr_agreement_comparison_state(
            _funding_validation_state(_ilr_finance_state(row))
        )
        for row in rows
    ]
    rows = filter_rows_by_program_status(rows, program_status)
    summary = {
        "learners": len(rows),
        "agreementMatched": sum(
            row["agreement_comparison_status"] == "matched" for row in rows
        ),
        "agreementMismatched": sum(
            row["agreement_comparison_status"] == "mismatched" for row in rows
        ),
        "totalsMatched": sum(
            row["ilr_agreement_status"] == "matched" for row in rows
        ),
        "totalsMismatched": sum(
            row["ilr_agreement_status"] == "mismatched" for row in rows
        ),
        "missingValues": sum(
            row["agreement_comparison_status"] == "missing"
            or row["ilr_agreement_status"] == "missing"
            for row in rows
        ),
    }

    if normalized_filter != "all":
        filter_checks = {
            "agreement-matched": lambda row: row["agreement_comparison_status"] == "matched",
            "agreement-mismatched": lambda row: row["agreement_comparison_status"] == "mismatched",
            "totals-matched": lambda row: row["ilr_agreement_status"] == "matched",
            "totals-mismatched": lambda row: row["ilr_agreement_status"] == "mismatched",
            "missing": lambda row: (
                row["agreement_comparison_status"] == "missing"
                or row["ilr_agreement_status"] == "missing"
            ),
        }
        rows = [row for row in rows if filter_checks[normalized_filter](row)]

    total = len(rows)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    safe_page = min(safe_page, pages)
    offset = (safe_page - 1) * PAGE_SIZE
    page_rows = rows[offset : offset + PAGE_SIZE]
    visible_cost_items = _visible_cost_items(page_rows)
    visible_reference_items = _visible_reference_items(page_rows)
    visible_ilr_codes = _visible_ilr_finance_codes(page_rows)

    return {
        "rows": page_rows,
        "itemColumns": [
            {"key": key, "label": label} for key, label in visible_cost_items
        ],
        "referenceColumns": [
            {"key": key, "label": label}
            for key, label in visible_reference_items
        ],
        "ilrColumns": [
            {"key": code, "label": f"TNP code {code}"}
            for code in visible_ilr_codes
        ],
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
