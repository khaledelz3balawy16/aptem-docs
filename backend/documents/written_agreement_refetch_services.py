import threading
import uuid
from datetime import datetime, timezone as dt_timezone

from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from evidence.management.commands.extract_written_agreement_funding import (
    Command as ExtractFundingCommand,
)
from evidence.management.commands.fetch_cv_contracts_probe import (
    Command as FetchContractsCommand,
)
from evidence.services.aptem import AptemClient
from evidence.services.written_agreement_funding import (
    extract_written_agreement_funding,
)

from .prior_learning_services import PRIOR_LEARNING_LEARNERS


VALID_SCOPES = {"funding", "prior-learning"}
WRITTEN_AGREEMENT_NAMES = {"written agreement", "written agreement 25/26"}
JOB_COLUMNS = (
    "id",
    "scope",
    "status",
    "total",
    "processed",
    "updated_links",
    "extracted",
    "skipped",
    "errors",
    "message",
    "created_at",
    "started_at",
    "completed_at",
)


def _normalized(value):
    return " ".join(str(value or "").strip().lower().split())


def select_latest_written_agreement(contract_rows, program_name):
    candidates = [
        row
        for row in contract_rows
        if _normalized(row.get("document_name")) in WRITTEN_AGREEMENT_NAMES
    ]
    normalized_program = _normalized(program_name)
    if normalized_program:
        candidates = [
            row
            for row in candidates
            if _normalized(row.get("program_name")) == normalized_program
        ]
    if not candidates:
        return None

    minimum = datetime.min.replace(tzinfo=dt_timezone.utc)
    return max(
        candidates,
        key=lambda row: (
            row.get("fully_signed_date")
            or row.get("learner_signed_date")
            or row.get("date")
            or minimum,
            int(row.get("source_document_id") or 0),
        ),
    )


def _job_dict(record):
    if record is None:
        return None
    return dict(zip(JOB_COLUMNS, record))


def get_refetch_job(job_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {', '.join(JOB_COLUMNS)}
            FROM fetching_evidence.written_agreement_refetch_jobs
            WHERE id = %s
            """,
            [job_id],
        )
        return _job_dict(cursor.fetchone())


def start_written_agreement_refetch(scope):
    normalized_scope = _normalized(scope)
    if normalized_scope not in VALID_SCOPES:
        raise ValueError("Invalid Written Agreement refetch scope.")

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {', '.join(JOB_COLUMNS)}
            FROM fetching_evidence.written_agreement_refetch_jobs
            WHERE scope = %s AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            """,
            [normalized_scope],
        )
        existing = _job_dict(cursor.fetchone())
        if existing:
            return existing

        job_id = uuid.uuid4()
        cursor.execute(
            """
            INSERT INTO fetching_evidence.written_agreement_refetch_jobs (
                id, scope, status, message
            ) VALUES (%s, %s, 'queued', 'Waiting to start')
            """,
            [job_id, normalized_scope],
        )

    thread = threading.Thread(
        target=_run_refetch_job,
        args=(job_id, normalized_scope),
        name=f"written-agreement-refetch-{normalized_scope}",
        daemon=True,
    )
    thread.start()
    return get_refetch_job(job_id)


def _target_learners(scope):
    name_condition = ""
    params = []
    if scope == "prior-learning":
        name_condition = "WHERE LOWER(ilr.full_name) = ANY(%s)"
        params.append([name.lower() for name in PRIOR_LEARNING_LEARNERS])

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH ranked_ilr AS (
                SELECT
                    CONCAT_WS(' ', delivery.given_names, delivery.family_name) AS full_name,
                    delivery.email,
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
                SELECT full_name, email
                FROM ranked_ilr
                WHERE learner_row = 1
            )
            SELECT
                learner.aptem_id,
                ilr.full_name,
                COALESCE(
                    NULLIF(current_document.current_programme, ''),
                    NULLIF(current_document.program_name, ''),
                    NULLIF(aptem_user."Program Name", '')
                ) AS program_name,
                current_document.program_id,
                COALESCE(
                    NULLIF(current_document.current_programme, ''),
                    NULLIF(current_document.program_name, ''),
                    NULLIF(aptem_user."Program Name", '')
                ) AS current_programme,
                COALESCE(
                    NULLIF(current_document.program_status, ''),
                    NULLIF(aptem_user."Program-Status", '')
                ) AS program_status,
                current_document.minimum,
                current_document.planned
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
            LEFT JOIN "LMS"."Aptem_users" aptem_user
                ON aptem_user."ID" = learner.aptem_id
            LEFT JOIN LATERAL (
                SELECT document.current_programme, document.program_name,
                       document.program_id, document.program_status,
                       document.minimum, document.planned
                FROM fetching_evidence.aptem_cv_contracts_probe document
                WHERE document.learner_id = learner.aptem_id
                ORDER BY document.fetched_at DESC NULLS LAST,
                         document.date DESC NULLS LAST,
                         document.id DESC
                LIMIT 1
            ) current_document ON TRUE
            {name_condition}
            ORDER BY ilr.full_name
            """,
            params,
        )
        return [
            {
                "learner_id": row[0],
                "full_name": row[1],
                "program_name": row[2],
                "program_id": row[3],
                "current_programme": row[4],
                "program_status": row[5],
                "minimum": row[6],
                "planned": row[7],
            }
            for row in cursor.fetchall()
            if row[0] is not None
            and _normalized(row[2])
            != "project control professional level 6 - al fanar"
        ]


def _set_job(job_id, **values):
    if not values:
        return
    assignments = ", ".join(f"{column} = %s" for column in values)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE fetching_evidence.written_agreement_refetch_jobs
            SET {assignments}
            WHERE id = %s
            """,
            [*values.values(), job_id],
        )


def _database_document(learner_id, source_document_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, learner_id, source_document_id, document_name,
                   natural_key, file, fetched_at, full_name
            FROM fetching_evidence.aptem_cv_contracts_probe
            WHERE learner_id = %s
              AND source_document_id = %s
              AND LOWER(TRIM(document_name)) = ANY(%s)
            ORDER BY date DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            [learner_id, source_document_id, list(WRITTEN_AGREEMENT_NAMES)],
        )
        return cursor.fetchone()


def _apply_program_metadata(target, source_document_id):
    """Keep newly discovered agreements attached to the learner's current programme."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE fetching_evidence.aptem_cv_contracts_probe
            SET full_name = COALESCE(NULLIF(%s, ''), full_name),
                program_id = COALESCE(%s, program_id),
                current_programme = COALESCE(
                    NULLIF(%s, ''), current_programme, program_name
                ),
                program_status = COALESCE(NULLIF(%s, ''), program_status),
                minimum = COALESCE(%s, minimum),
                planned = COALESCE(%s, planned)
            WHERE learner_id = %s
              AND source_document_id = %s
              AND LOWER(TRIM(document_name)) = ANY(%s)
            """,
            [
                target["full_name"],
                target["program_id"],
                target["current_programme"],
                target["program_status"],
                target["minimum"],
                target["planned"],
                target["learner_id"],
                source_document_id,
                list(WRITTEN_AGREEMENT_NAMES),
            ],
        )


def _run_refetch_job(job_id, scope):
    close_old_connections()
    counters = {
        "processed": 0,
        "updated_links": 0,
        "extracted": 0,
        "skipped": 0,
        "errors": 0,
    }
    try:
        targets = _target_learners(scope)
        _set_job(
            job_id,
            status="running",
            total=len(targets),
            started_at=timezone.now(),
            message="Logging in to Aptem",
        )

        client = AptemClient()
        client.login()
        fetcher = FetchContractsCommand()
        extractor = ExtractFundingCommand()

        for target in targets:
            try:
                contract_rows = fetcher._fetch_contract_rows(
                    client, target["learner_id"]
                )
                latest = select_latest_written_agreement(
                    contract_rows, target["program_name"]
                )
                if latest is None:
                    counters["skipped"] += 1
                else:
                    latest["full_name"] = target["full_name"]
                    latest["program_id"] = target["program_id"]
                    previous = _database_document(
                        target["learner_id"], latest["source_document_id"]
                    )
                    previous_file = previous[5] if previous else None
                    fetcher._upsert_rows([latest])
                    _apply_program_metadata(target, latest["source_document_id"])
                    document = _database_document(
                        target["learner_id"], latest["source_document_id"]
                    )
                    if document is None:
                        raise ValueError("Latest Written Agreement was not saved")
                    if previous_file != document[5]:
                        counters["updated_links"] += 1

                    now = timezone.now()
                    pdf_bytes, file_name, file_type = extractor._download(
                        client, document[5]
                    )
                    funding = extract_written_agreement_funding(pdf_bytes)
                    if funding is None:
                        counters["skipped"] += 1
                        entry = extractor._entry(
                            document,
                            now,
                            funding=None,
                            file_name=file_name,
                            file_type=file_type,
                            status="skipped",
                            error="Costs table was not found in the PDF",
                        )
                    else:
                        counters["extracted"] += 1
                        entry = extractor._entry(
                            document,
                            now,
                            funding=funding,
                            file_name=file_name,
                            file_type=file_type,
                            status="completed",
                        )
                    extractor._save(
                        document, funding, entry, file_name, file_type, now
                    )
            except Exception:  # noqa: BLE001 - continue remaining learners.
                counters["errors"] += 1

            counters["processed"] += 1
            _set_job(
                job_id,
                **counters,
                message=(
                    f"Processed {counters['processed']} of {len(targets)} learners"
                ),
            )

        _set_job(
            job_id,
            status="completed",
            completed_at=timezone.now(),
            message=(
                f"Extracted {counters['extracted']} agreement(s); "
                f"{counters['errors']} error(s)"
            ),
            **counters,
        )
    except Exception as exc:  # noqa: BLE001 - persist terminal job failure.
        _set_job(
            job_id,
            status="failed",
            completed_at=timezone.now(),
            message=str(exc),
            **counters,
        )
    finally:
        close_old_connections()
