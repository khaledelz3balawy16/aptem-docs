"""Fetch CV and contract metadata for selected learners into a probe table."""

import json
import time
from datetime import datetime, timezone as dt_timezone
from hashlib import sha1

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from evidence.services.aptem import AptemAuthError, AptemClient
from evidence.services.compliance_pdf import (
    download_compliance_pdf,
    extract_planned_hours_with_timeout,
)


DEFAULT_LEARNER_IDS = [
    1455,
    3501,
    3582,
    3598,
    5507,
    6105,
    6121,
    6288,
    8861,
    9117,
    9750,
    18617,
]

CONTRACT_NAMES = (
    "apprenticeship agreement",
    "training plan",
    "individual learning record",
    "written agreement",
    "contract for service",
)


class Command(BaseCommand):
    help = "Fetch CVs and contract/compliance documents into a separate probe table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--learner-id",
            type=int,
            action="append",
            dest="learner_ids",
            help="Learner ID to fetch. Can be repeated. Defaults to the 12 probe learners.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and print a preview without creating/upserting the probe table.",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Clear the probe table before inserting fetched rows.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.2,
            help="Seconds to pause between learners.",
        )

    def handle(self, *args, **opts):
        learner_ids = opts["learner_ids"] or DEFAULT_LEARNER_IDS

        if not opts["dry_run"]:
            self._ensure_probe_table()
            if opts["truncate"]:
                self._truncate_probe_table()

        client = AptemClient()
        self.stdout.write("Logging in to Aptem...")
        client.login()
        self.stdout.write(self.style.SUCCESS("Login OK"))

        total_cvs = 0
        total_contracts = 0
        errors = 0

        for i, learner_id in enumerate(learner_ids, 1):
            try:
                cv_rows = self._fetch_cv_rows(client, learner_id)
                contract_rows = self._fetch_contract_rows(client, learner_id)
                training_plan_hours = self._extract_document_hours(
                    client,
                    contract_rows,
                    {"training plan", "training plan 25/26"},
                )
                agreement_hours = self._extract_document_hours(
                    client,
                    contract_rows,
                    {"apprenticeship agreement"},
                )
                for row in cv_rows + contract_rows:
                    source_id = row.get("source_document_id")
                    row["training_plan_planned_hours"] = training_plan_hours.get(
                        source_id
                    )
                    row["apprenticeship_agreement_planned_hours"] = agreement_hours.get(
                        source_id
                    )
            except Exception as exc:  # noqa: BLE001 - report and continue.
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[{i}/{len(learner_ids)}] learner {learner_id}: {exc}"
                    )
                )
                continue

            total_cvs += len(cv_rows)
            total_contracts += len(contract_rows)
            self._print_preview(i, len(learner_ids), learner_id, cv_rows, contract_rows)

            if not opts["dry_run"]:
                self._upsert_rows(cv_rows + contract_rows)

            time.sleep(opts["sleep"])

        action = "fetched" if opts["dry_run"] else "upserted"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_cvs} CV row(s) and {total_contracts} contract row(s) "
                f"{action}; {errors} learner error(s)."
            )
        )

    def _fetch_json_with_retry(self, client, endpoint, learner_id):
        url = f"{client.base_url}/odata/1.0/{endpoint}"
        params = {"$filter": f"LearnerId eq {learner_id}"}
        resp = client.session.get(
            url, params=params, headers=client._api_headers(), timeout=60
        )
        if resp.status_code == 401:
            client.login()
            resp = client.session.get(
                url, params=params, headers=client._api_headers(), timeout=60
            )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def _fetch_cv_rows(self, client, learner_id):
        rows = []
        seen = set()
        responses = self._fetch_json_with_retry(client, "OnboardingResponses", learner_id)

        for item in responses:
            step = (item.get("Step") or "").lower()
            question = item.get("Question") or ""
            question_lc = question.lower()
            if "cv" not in step and "cv" not in question_lc:
                continue

            answer = item.get("Answer")
            upload = self._parse_upload_answer(answer)
            if "upload an up to date cv" in question_lc and upload:
                document_id = upload.get("id")
                document_name = upload.get("name") or ""
                natural_key = f"cv:{learner_id}:{document_id}"
                if natural_key in seen:
                    continue
                seen.add(natural_key)
                rows.append(
                    {
                        "document_category": "CV",
                        "source": "OnboardingResponses",
                        "source_document_id": document_id,
                        "learner_id": learner_id,
                        "full_name": item.get("FullName") or "",
                        "program_id": item.get("ProgramId"),
                        "program_name": item.get("Programme") or "",
                        "document_name": document_name,
                        "status": "",
                        "date": parse_datetime(item.get("Date"))
                        if isinstance(item.get("Date"), str)
                        else None,
                        "learner_signed_date": None,
                        "fully_signed_date": None,
                        "requested_date": None,
                        "answer_text": "",
                        "file": self._static_document_url(client, document_id),
                        "raw": item,
                    }
                )
            elif "do not have a cv" in question_lc and self._has_meaningful_text(answer):
                answer_key = sha1(answer.strip().encode("utf-8")).hexdigest()
                natural_key = f"cv_text:{learner_id}:{answer_key}"
                if natural_key in seen:
                    continue
                seen.add(natural_key)
                rows.append(
                    {
                        "document_category": "CV_TEXT",
                        "source": "OnboardingResponses",
                        "source_document_id": None,
                        "learner_id": learner_id,
                        "full_name": item.get("FullName") or "",
                        "program_id": item.get("ProgramId"),
                        "program_name": item.get("Programme") or "",
                        "document_name": "CV/Job Description text response",
                        "status": "",
                        "date": parse_datetime(item.get("Date"))
                        if isinstance(item.get("Date"), str)
                        else None,
                        "learner_signed_date": None,
                        "fully_signed_date": None,
                        "requested_date": None,
                        "answer_text": answer,
                        "file": "",
                        "raw": item,
                    }
                )

        return rows

    def _fetch_contract_rows(self, client, learner_id):
        rows = []
        documents = self._fetch_json_with_retry(client, "ComplianceDocuments", learner_id)
        for item in documents:
            name = item.get("Name") or ""
            if not any(contract_name in name.lower() for contract_name in CONTRACT_NAMES):
                continue
            rows.append(
                {
                    "document_category": "CONTRACT",
                    "source": "ComplianceDocuments",
                    "source_document_id": item.get("Id"),
                    "learner_id": learner_id,
                    "full_name": "",
                    "program_id": None,
                    "program_name": item.get("ProgramName") or "",
                    "document_name": name,
                    "status": item.get("Status") or "",
                    "date": parse_datetime(item.get("Date"))
                    if isinstance(item.get("Date"), str)
                    else None,
                    "learner_signed_date": parse_datetime(item.get("LearnerSignedDate"))
                    if isinstance(item.get("LearnerSignedDate"), str)
                    else None,
                    "fully_signed_date": parse_datetime(item.get("FullySignedDate"))
                    if isinstance(item.get("FullySignedDate"), str)
                    else None,
                    "requested_date": parse_datetime(item.get("RequestedDate"))
                    if isinstance(item.get("RequestedDate"), str)
                    else None,
                    "answer_text": "",
                    "file": self._compliance_document_url(
                        client, item.get("Id"), learner_id
                    ),
                    "raw": item,
                }
            )
        return rows

    def _parse_upload_answer(self, answer):
        if not answer:
            return None
        try:
            parsed = json.loads(answer)
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _extract_document_hours(self, client, contract_rows, document_names):
        candidate_documents = [
            row
            for row in contract_rows
            if row["document_name"].strip().lower()
            in document_names
            and row["file"]
        ]
        candidate_documents.sort(
            key=lambda row: (
                row["fully_signed_date"]
                or row["learner_signed_date"]
                or row["date"]
                or datetime.min.replace(tzinfo=dt_timezone.utc),
            ),
            reverse=True,
        )
        extracted = {}
        for row in candidate_documents:
            try:
                pdf = download_compliance_pdf(client, row["file"])
                hours = extract_planned_hours_with_timeout(pdf)
            except Exception:  # noqa: BLE001 - keep metadata fetch resilient.
                continue
            if hours is not None:
                extracted[row["source_document_id"]] = hours
        return extracted

    def _has_meaningful_text(self, answer):
        if not answer:
            return False
        normalized = answer.strip().lower()
        return normalized not in {"n/a", "na", "none", "no", "not applicable"}

    def _static_document_url(self, client, document_id):
        if not document_id:
            return ""
        return (
            f"{client.base_url}/MWS.eDocuments/StaticDocuments/"
            f"GetFile?documentId={document_id}"
        )

    def _compliance_document_url(self, client, document_id, learner_id):
        if not document_id:
            return ""
        return (
            f"{client.base_url}/DownloadFile/Compliance/"
            f"{document_id}?userId={learner_id}"
        )

    def _print_preview(self, index, total, learner_id, cv_rows, contract_rows):
        self.stdout.write(
            f"[{index}/{total}] learner {learner_id}: "
            f"{len(cv_rows)} CV row(s), {len(contract_rows)} contract row(s)"
        )
        for row in cv_rows[:3]:
            self.stdout.write(
                f"  CV - {row['document_name']} "
                f"(source id: {row['source_document_id'] or 'text-only'})"
            )
        for row in contract_rows[:5]:
            self.stdout.write(
                f"  CONTRACT - {row['document_name']} | "
                f"Status={row['status']} | source id: {row['source_document_id']}"
            )

    def _ensure_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('CREATE SCHEMA IF NOT EXISTS "fetching_evidence"')
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS "fetching_evidence"."aptem_cv_contracts_probe" (
                    id BIGSERIAL PRIMARY KEY,
                    document_category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_document_id BIGINT NULL,
                    learner_id BIGINT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    program_id BIGINT NULL,
                    program_name TEXT NOT NULL DEFAULT '',
                    document_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    date TIMESTAMPTZ NULL,
                    learner_signed_date TIMESTAMPTZ NULL,
                    fully_signed_date TIMESTAMPTZ NULL,
                    requested_date TIMESTAMPTZ NULL,
                    answer_text TEXT NOT NULL DEFAULT '',
                    file TEXT NOT NULL DEFAULT '',
                    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
                    fetched_at TIMESTAMPTZ NOT NULL,
                    natural_key TEXT NOT NULL UNIQUE,
                    file_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_to DATE NULL,
                    updated_to_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,
                    training_plan_planned_hours NUMERIC(14, 2) NULL,
                    apprenticeship_agreement_planned_hours NUMERIC(14, 2) NULL,
                    written_agreement_funding JSONB NULL,
                    apprenticeship_agreement_original_file TEXT NULL,
                    apprenticeship_agreement_version_id BIGINT NULL,
                    apprenticeship_agreement_version_created_at TIMESTAMP WITHOUT TIME ZONE NULL,
                    apprenticeship_agreement_version_selected_at TIMESTAMPTZ NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_cv_contracts_probe_learner_id_idx
                ON "fetching_evidence"."aptem_cv_contracts_probe" (learner_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_cv_contracts_probe_category_idx
                ON "fetching_evidence"."aptem_cv_contracts_probe" (document_category)
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS file_manually_edited BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS updated_to DATE NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS updated_to_manually_edited
                BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS training_plan_planned_hours NUMERIC(14, 2) NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_planned_hours
                NUMERIC(14, 2) NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS written_agreement_funding JSONB NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_original_file TEXT NULL;
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_version_id BIGINT NULL;
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_version_created_at
                    TIMESTAMP WITHOUT TIME ZONE NULL;
                ALTER TABLE "fetching_evidence"."aptem_cv_contracts_probe"
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_version_selected_at
                    TIMESTAMPTZ NULL
                """
            )

    def _truncate_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('TRUNCATE TABLE "fetching_evidence"."aptem_cv_contracts_probe"')

    def _upsert_rows(self, rows):
        fetched_at = timezone.now()
        with transaction.atomic(), connection.cursor() as cur:
            for row in rows:
                natural_key = self._natural_key(row)
                cur.execute(
                    """
                    INSERT INTO "fetching_evidence"."aptem_cv_contracts_probe" (
                        document_category,
                        source,
                        source_document_id,
                        learner_id,
                        full_name,
                        program_id,
                        program_name,
                        document_name,
                        status,
                        date,
                        learner_signed_date,
                        fully_signed_date,
                        requested_date,
                        answer_text,
                        file,
                        raw,
                        fetched_at,
                        natural_key,
                        updated_to,
                        training_plan_planned_hours,
                        apprenticeship_agreement_planned_hours
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (natural_key) DO UPDATE SET
                        document_category = EXCLUDED.document_category,
                        source = EXCLUDED.source,
                        source_document_id = EXCLUDED.source_document_id,
                        learner_id = EXCLUDED.learner_id,
                        full_name = COALESCE(
                            NULLIF(EXCLUDED.full_name, ''),
                            "fetching_evidence"."aptem_cv_contracts_probe".full_name
                        ),
                        program_id = COALESCE(
                            EXCLUDED.program_id,
                            "fetching_evidence"."aptem_cv_contracts_probe".program_id
                        ),
                        program_name = COALESCE(
                            NULLIF(EXCLUDED.program_name, ''),
                            "fetching_evidence"."aptem_cv_contracts_probe".program_name
                        ),
                        document_name = EXCLUDED.document_name,
                        status = EXCLUDED.status,
                        date = EXCLUDED.date,
                        learner_signed_date = EXCLUDED.learner_signed_date,
                        fully_signed_date = EXCLUDED.fully_signed_date,
                        requested_date = EXCLUDED.requested_date,
                        answer_text = EXCLUDED.answer_text,
                        file = CASE
                            WHEN "fetching_evidence"."aptem_cv_contracts_probe".file_manually_edited
                              OR "fetching_evidence"."aptem_cv_contracts_probe".apprenticeship_agreement_version_id IS NOT NULL
                            THEN "fetching_evidence"."aptem_cv_contracts_probe".file
                            ELSE EXCLUDED.file
                        END,
                        raw = EXCLUDED.raw,
                        fetched_at = EXCLUDED.fetched_at,
                        updated_to = CASE
                            WHEN "fetching_evidence"."aptem_cv_contracts_probe".updated_to_manually_edited
                            THEN "fetching_evidence"."aptem_cv_contracts_probe".updated_to
                            ELSE EXCLUDED.updated_to
                        END,
                        training_plan_planned_hours = COALESCE(
                            EXCLUDED.training_plan_planned_hours,
                            "fetching_evidence"."aptem_cv_contracts_probe".training_plan_planned_hours
                        ),
                        apprenticeship_agreement_planned_hours = COALESCE(
                            EXCLUDED.apprenticeship_agreement_planned_hours,
                            "fetching_evidence"."aptem_cv_contracts_probe".apprenticeship_agreement_planned_hours
                        )
                    """,
                    [
                        row["document_category"],
                        row["source"],
                        row["source_document_id"],
                        row["learner_id"],
                        row["full_name"],
                        row["program_id"],
                        row["program_name"],
                        row["document_name"],
                        row["status"],
                        row["date"],
                        row["learner_signed_date"],
                        row["fully_signed_date"],
                        row["requested_date"],
                        row["answer_text"],
                        row["file"],
                        json.dumps(row["raw"], ensure_ascii=False),
                        fetched_at,
                        natural_key,
                        row["date"].date() if row["date"] else None,
                        row.get("training_plan_planned_hours"),
                        row.get("apprenticeship_agreement_planned_hours"),
                    ],
                )

    def _natural_key(self, row):
        parts = [
            row["document_category"],
            row["source"],
            str(row["learner_id"]),
            str(row["program_id"] or ""),
            str(row["source_document_id"] or ""),
            row["document_name"],
            str(row["date"] or ""),
        ]
        return "|".join(parts)
