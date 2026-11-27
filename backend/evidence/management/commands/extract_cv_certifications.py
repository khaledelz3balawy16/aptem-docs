"""Backfill Certifications and Education from Aptem CV documents."""

import json
import re
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from evidence.services.aptem import AptemClient
from evidence.services.cv_certifications import (
    extract_certifications_and_education,
    extract_cv_text,
)


class Command(BaseCommand):
    help = "Extract education and certifications from CV files."

    def add_arguments(self, parser):
        parser.add_argument("--only-missing", action="store_true")
        parser.add_argument("--local-only", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--learner-id", type=int, action="append", dest="learner_ids")
        parser.add_argument("--sleep", type=float, default=0.05)
        parser.add_argument("--progress-every", type=int, default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        documents = self._documents(
            only_missing=options["only_missing"],
            local_only=options["local_only"],
            learner_ids=options["learner_ids"],
            limit=options["limit"],
        )
        if not documents:
            self.stdout.write(self.style.SUCCESS("No CV documents queued."))
            return

        client = AptemClient()
        client.login()
        completed = empty = failed = 0
        for index, document in enumerate(documents, 1):
            try:
                content, file_name, file_type = self._download(client, document[5])
                text = extract_cv_text(content, file_type, file_name)
                results = extract_certifications_and_education(text)
                completed += bool(results)
                empty += not results
                if not options["dry_run"]:
                    self._save(document, results, file_name, file_type, None)
            except Exception as exc:  # noqa: BLE001 - record and continue the backfill.
                failed += 1
                if not options["dry_run"]:
                    self._save(document, [], None, None, str(exc))

            if (
                index == 1
                or index == len(documents)
                or index % max(options["progress_every"], 1) == 0
            ):
                self.stdout.write(
                    f"[{index}/{len(documents)}] extracted={completed}, "
                    f"empty={empty}, failed={failed}"
                )
            if options["sleep"]:
                time.sleep(options["sleep"])

        verb = "found" if options["dry_run"] else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {completed} with results {verb}, {empty} without matching "
                f"sections, {failed} unsupported or failed."
            )
        )

    def _documents(self, only_missing, local_only, learner_ids, limit):
        conditions = [
            "probe.document_category = 'CV'",
            "NULLIF(TRIM(probe.file), '') IS NOT NULL",
        ]
        params = []
        if only_missing:
            conditions.append(
                "(certification.id IS NULL OR "
                "jsonb_array_length(certification.certifications) = 0)"
            )
        if local_only:
            conditions.append(
                "certification.openai_model = 'local-cv-section-parser-v1'"
            )
        if learner_ids:
            conditions.append("probe.learner_id = ANY(%s)")
            params.append(learner_ids)
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT %s"
            params.append(limit)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT probe.id, probe.learner_id, probe.natural_key,
                       probe.fetched_at, probe.document_name, probe.file,
                       probe.full_name
                FROM fetching_evidence.aptem_cv_contracts_probe probe
                LEFT JOIN fetching_evidence.aptem_cv_certifications certification
                  ON certification.source_id = probe.id
                WHERE {' AND '.join(conditions)}
                ORDER BY probe.full_name, probe.id
                {limit_sql}
                """,
                params,
            )
            return cursor.fetchall()

    def _download(self, client, url):
        response = client.session.get(url, timeout=90)
        if response.status_code == 401:
            client.login()
            response = client.session.get(url, timeout=90)
        response.raise_for_status()
        file_type = (response.headers.get("content-type") or "").split(";", 1)[0]
        disposition = response.headers.get("content-disposition") or ""
        match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.I)
        file_name = Path(match.group(1).strip()).name if match else "CV"
        return response.content, file_name, file_type

    def _save(self, document, results, file_name, file_type, error):
        now = timezone.now()
        status = "failed" if error else "completed"
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fetching_evidence.aptem_cv_certifications (
                    source_id, learner_id, source_natural_key, cv_url,
                    certifications, processing_status, error_message,
                    file_name, file_type, openai_model, openai_response_id,
                    source_fetched_at, processed_at, updated_at, row_kind
                ) VALUES (
                    %s, %s, %s, %s, %s::jsonb, %s, %s,
                    %s, %s, 'local-cv-section-parser-v1', NULL,
                    %s, %s, %s, 'cv'
                )
                ON CONFLICT (source_id) DO UPDATE SET
                    learner_id = EXCLUDED.learner_id,
                    source_natural_key = EXCLUDED.source_natural_key,
                    cv_url = EXCLUDED.cv_url,
                    certifications = EXCLUDED.certifications,
                    processing_status = EXCLUDED.processing_status,
                    error_message = EXCLUDED.error_message,
                    file_name = EXCLUDED.file_name,
                    file_type = EXCLUDED.file_type,
                    openai_model = EXCLUDED.openai_model,
                    openai_response_id = NULL,
                    source_fetched_at = EXCLUDED.source_fetched_at,
                    processed_at = EXCLUDED.processed_at,
                    updated_at = EXCLUDED.updated_at,
                    row_kind = 'cv'
                """,
                [
                    document[0],
                    document[1],
                    document[2],
                    document[5],
                    json.dumps(results, ensure_ascii=False),
                    status,
                    error,
                    file_name,
                    file_type,
                    document[3],
                    now,
                    now,
                ],
            )
