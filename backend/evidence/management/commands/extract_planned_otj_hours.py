"""Backfill planned OTJ hours from Aptem agreement and training-plan PDFs."""

import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from evidence.services.aptem import AptemClient
from evidence.services.compliance_pdf import (
    download_compliance_pdf,
    extract_planned_hours_with_timeout,
)


class Command(BaseCommand):
    help = (
        "Extract planned OTJ hours from each learner's Apprenticeship Agreement "
        "or Training Plan PDF."
    )

    def add_arguments(self, parser):
        parser.add_argument("--learner-id", type=int, action="append", dest="learner_ids")
        parser.add_argument("--only-missing", action="store_true")
        parser.add_argument("--after-learner-id", type=int)
        parser.add_argument("--multi-program-only", action="store_true")
        parser.add_argument(
            "--document-type",
            choices=("training-plan", "apprenticeship-agreement"),
            default="training-plan",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--sleep", type=float, default=0.1)

    def handle(self, *args, **options):
        self.document_type = options["document_type"]
        self.target_column = {
            "training-plan": "training_plan_planned_hours",
            "apprenticeship-agreement": "apprenticeship_agreement_planned_hours",
        }[self.document_type]
        self.document_names = {
            "training-plan": ["training plan", "training plan 25/26"],
            "apprenticeship-agreement": ["apprenticeship agreement"],
        }[self.document_type]
        documents = self._candidate_documents(
            options["learner_ids"],
            options["only_missing"],
            options["after_learner_id"],
            options["multi_program_only"],
        )
        client = AptemClient()
        self.stdout.write(
            f"Logging in to Aptem; {len(documents)} document(s) queued for "
            f"{self.document_type}..."
        )
        client.login()

        extracted = missing = errors = 0
        for index, (row_id, learner_id, document_id, url) in enumerate(documents, 1):
            try:
                pdf = download_compliance_pdf(client, url)
                hours = extract_planned_hours_with_timeout(pdf)
                if hours is None:
                    missing += 1
                    self.stdout.write(
                        f"[{index}/{len(documents)}] learner {learner_id}, "
                        f"document {document_id}: value not found"
                    )
                else:
                    extracted += 1
                    if not options["dry_run"]:
                        self._save(row_id, hours)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{index}/{len(documents)}] learner {learner_id}: "
                            f"{hours} hours (document {document_id})"
                        )
                    )
            except Exception as exc:  # noqa: BLE001 - continue the backfill.
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[{index}/{len(documents)}] learner {learner_id}, "
                        f"document {document_id}: {exc}"
                    )
                )
            time.sleep(options["sleep"])

        verb = "found" if options["dry_run"] else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {extracted} value(s) {verb}, {missing} not found, {errors} error(s)."
            )
        )

    def _candidate_documents(
        self,
        learner_ids,
        only_missing,
        after_learner_id=None,
        multi_program_only=False,
    ):
        conditions = ["LOWER(document_name) = ANY(%s)"]
        if not learner_ids:
            conditions.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM fetching_evidence.aptem_cv_contracts_probe excluded
                    WHERE excluded.learner_id = aptem_cv_contracts_probe.learner_id
                      AND LOWER(TRIM(COALESCE(
                            NULLIF(excluded.current_programme, ''),
                            NULLIF(excluded.program_name, '')
                      ))) = 'project control professional level 6 - al fanar'
                )
                """
            )
        params = [self.document_names]
        if learner_ids:
            conditions.append("learner_id = ANY(%s)")
            params.append(learner_ids)
        if only_missing:
            conditions.append(f"{self.target_column} IS NULL")
        if after_learner_id is not None:
            conditions.append("learner_id > %s")
            params.append(after_learner_id)
        if multi_program_only:
            conditions.append(
                """
                learner_id IN (
                    SELECT multi.learner_id
                    FROM fetching_evidence.aptem_cv_contracts_probe multi
                    WHERE multi.document_category = 'CONTRACT'
                      AND NULLIF(TRIM(multi.program_name), '') IS NOT NULL
                    GROUP BY multi.learner_id
                    HAVING COUNT(DISTINCT LOWER(TRIM(multi.program_name))) > 1
                )
                """
            )

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, learner_id, source_document_id, file
                FROM fetching_evidence.aptem_cv_contracts_probe
                WHERE {' AND '.join(conditions)}
                  AND NULLIF(file, '') IS NOT NULL
                  AND source_document_id IS NOT NULL
                ORDER BY learner_id,
                         COALESCE(fully_signed_date, learner_signed_date, date) DESC NULLS LAST,
                         id DESC
                """,
                params,
            )
            return cursor.fetchall()

    def _save(self, row_id, hours):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE fetching_evidence.aptem_cv_contracts_probe
                SET {self.target_column} = %s
                WHERE id = %s
                """,
                [hours, row_id],
            )
