"""Backfill the complete costs table from Aptem Written Agreement PDFs."""

import json
import re
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from evidence.services.aptem import AptemClient
from evidence.services.written_agreement_funding import (
    extract_written_agreement_funding,
)


DOCUMENT_NAMES = ("written agreement", "written agreement 25/26")


class Command(BaseCommand):
    help = (
        "Extract all monetary values from Written Agreement PDFs and sync them "
        "to aptem_cv_contracts_probe and aptem_cv_certifications."
    )

    def add_arguments(self, parser):
        parser.add_argument("--learner-id", type=int, action="append", dest="learner_ids")
        parser.add_argument("--only-missing", action="store_true")
        parser.add_argument("--after-id", type=int)
        parser.add_argument("--limit", type=int)
        parser.add_argument("--learner-modulo", type=int)
        parser.add_argument("--learner-remainder", type=int)
        parser.add_argument("--sleep", type=float, default=0.1)
        parser.add_argument("--progress-every", type=int, default=1)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        documents = self._candidate_documents(
            learner_ids=options["learner_ids"],
            only_missing=options["only_missing"],
            after_id=options["after_id"],
            limit=options["limit"],
            learner_modulo=options["learner_modulo"],
            learner_remainder=options["learner_remainder"],
        )
        if not documents:
            self.stdout.write(self.style.SUCCESS("No Written Agreement documents queued."))
            return

        client = AptemClient()
        self.stdout.write(f"Logging in to Aptem; {len(documents)} document(s) queued...")
        client.login()

        completed = skipped = errors = 0
        for index, document in enumerate(documents, 1):
            now = timezone.now()
            try:
                pdf_bytes, file_name, file_type = self._download(client, document[5])
                funding = extract_written_agreement_funding(pdf_bytes)
                if funding is None:
                    skipped += 1
                    entry = self._entry(
                        document,
                        now,
                        funding=None,
                        file_name=file_name,
                        file_type=file_type,
                        status="skipped",
                        error="Costs table was not found in the PDF",
                    )
                else:
                    completed += 1
                    entry = self._entry(
                        document,
                        now,
                        funding=funding,
                        file_name=file_name,
                        file_type=file_type,
                        status="completed",
                    )
                if not options["dry_run"]:
                    self._save(document, funding, entry, file_name, file_type, now)
                summary = (
                    funding.get("total_price_of_apprenticeship", {}).get("value")
                    if funding
                    else None
                )
                if (
                    index == 1
                    or index == len(documents)
                    or index % max(options["progress_every"], 1) == 0
                    or entry["processing_status"] != "completed"
                ):
                    self.stdout.write(
                        f"[{index}/{len(documents)}] learner {document[1]}, "
                        f"document {document[2]}: {entry['processing_status']}"
                        + (f" (total GBP {summary})" if summary is not None else "")
                    )
            except Exception as exc:  # noqa: BLE001 - continue the backfill.
                errors += 1
                entry = self._entry(
                    document,
                    now,
                    funding=None,
                    status="skipped",
                    error=str(exc),
                    retryable=self._retryable(exc),
                )
                if not options["dry_run"]:
                    self._save(document, None, entry, None, None, now)
                self.stdout.write(
                    self.style.ERROR(
                        f"[{index}/{len(documents)}] learner {document[1]}, "
                        f"document {document[2]}: {exc}"
                    )
                )
            if options["sleep"]:
                time.sleep(options["sleep"])

        verb = "found" if options["dry_run"] else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {completed} completed {verb}, {skipped} without a costs "
                f"table, {errors} download/parser error(s)."
            )
        )

    def _candidate_documents(
        self,
        learner_ids,
        only_missing,
        after_id,
        limit,
        learner_modulo=None,
        learner_remainder=None,
    ):
        conditions = ["LOWER(TRIM(document_name)) = ANY(%s)", "NULLIF(file, '') IS NOT NULL"]
        params = [list(DOCUMENT_NAMES)]
        if learner_ids:
            conditions.append("learner_id = ANY(%s)")
            params.append(learner_ids)
        if only_missing:
            conditions.append("written_agreement_funding IS NULL")
        if after_id is not None:
            conditions.append("id > %s")
            params.append(after_id)
        if learner_modulo is not None:
            if learner_modulo < 1:
                raise ValueError("--learner-modulo must be greater than zero")
            if learner_remainder is None or not 0 <= learner_remainder < learner_modulo:
                raise ValueError(
                    "--learner-remainder must be between zero and learner-modulo - 1"
                )
            conditions.append("MOD(learner_id, %s) = %s")
            params.extend([learner_modulo, learner_remainder])
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT %s"
            params.append(limit)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, learner_id, source_document_id, document_name,
                       natural_key, file, fetched_at, full_name
                FROM fetching_evidence.aptem_cv_contracts_probe
                WHERE {' AND '.join(conditions)}
                ORDER BY id
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
        if "pdf" not in file_type.lower() and not response.content.startswith(b"%PDF"):
            raise ValueError("Aptem returned a non-PDF response")
        disposition = response.headers.get("content-disposition") or ""
        match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.I)
        file_name = Path(match.group(1).strip()).name if match else "Written-Agreement.pdf"
        return response.content, file_name, file_type or "application/pdf"

    def _entry(
        self,
        document,
        processed_at,
        funding,
        file_name=None,
        file_type=None,
        status="completed",
        error=None,
        retryable=False,
    ):
        normalized_name = re.sub(r"\s+", " ", document[3].strip().lower())
        return {
            "funding": funding,
            "file_name": file_name,
            "file_type": file_type,
            "source_id": str(document[0]),
            "openai_model": None,
            "processed_at": self._iso(processed_at),
            "document_name": document[3],
            "error_message": error,
            "processing_status": status,
            "source_fetched_at": self._iso(document[6]),
            "openai_response_id": None,
            "source_natural_key": document[4],
            "document_name_match": {
                "score": 1,
                "method": "exact",
                "matched": True,
                "normalized": normalized_name,
            },
            "extraction_method": "pypdf",
            "parser_version": "1.0",
            **({"retryable": retryable} if error else {}),
        }

    def _save(self, document, funding, entry, file_name, file_type, now):
        row_id, learner_id = document[0], document[1]
        entry_json = json.dumps(entry, ensure_ascii=False)
        funding_json = json.dumps(funding, ensure_ascii=False) if funding else None
        with transaction.atomic(), connection.cursor() as cursor:
            if funding_json is not None:
                cursor.execute(
                    """
                    UPDATE fetching_evidence.aptem_cv_contracts_probe
                    SET written_agreement_funding = %s::jsonb
                    WHERE id = %s
                    """,
                    [funding_json, row_id],
                )

            cursor.execute(
                """
                SELECT id, written_agreements
                FROM fetching_evidence.aptem_cv_certifications
                WHERE learner_id = %s
                FOR UPDATE
                """,
                [learner_id],
            )
            certification = cursor.fetchone()
            if certification:
                agreements = certification[1] or []
                if isinstance(agreements, str):
                    agreements = json.loads(agreements)
                source_id = str(row_id)
                agreements = [
                    current
                    for current in agreements
                    if str(current.get("source_id")) != source_id
                    and current.get("source_natural_key") != document[4]
                ]
                agreements.append(entry)
                cursor.execute(
                    """
                    UPDATE fetching_evidence.aptem_cv_certifications
                    SET written_agreements = %s::jsonb,
                        written_agreements_updated_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    [json.dumps(agreements, ensure_ascii=False), now, now, certification[0]],
                )
                return

            cursor.execute(
                """
                INSERT INTO fetching_evidence.aptem_cv_certifications (
                    source_id, learner_id, source_natural_key, cv_url,
                    certifications, processing_status, source_fetched_at,
                    processed_at, written_agreements,
                    written_agreements_updated_at, row_kind,
                    file_name, file_type, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, '[]'::jsonb, 'completed', %s, %s,
                    %s::jsonb, %s, 'written_agreement_host', %s, %s, %s, %s
                )
                """,
                [
                    -row_id,
                    learner_id,
                    f"WRITTEN_AGREEMENT_HOST|{learner_id}",
                    document[5],
                    document[6] or now,
                    now,
                    f"[{entry_json}]",
                    now,
                    file_name,
                    file_type,
                    now,
                    now,
                ],
            )

    @staticmethod
    def _iso(value):
        if value is None:
            return None
        return value.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _retryable(exc):
        response = getattr(exc, "response", None)
        return response is None or response.status_code >= 500
