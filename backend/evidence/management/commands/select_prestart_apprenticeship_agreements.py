from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from evidence.services.apprenticeship_versions import (
    agreement_version_url,
    best_agreement_version_for_start,
    parse_version_datetime,
)
from evidence.services.aptem import AptemClient


class Command(BaseCommand):
    help = (
        "Select the latest Apprenticeship Agreement version on/before each "
        "learner's ILR start date, or the closest version after it as a fallback, "
        "and replace only that document's file URL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and preview selections without updating the database.",
        )
        parser.add_argument(
            "--learner-id",
            type=int,
            action="append",
            dest="learner_ids",
            help="Limit the operation to one or more Aptem learner IDs.",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help="Number of concurrent Aptem requests (default: 8).",
        )

    def handle(self, *args, **options):
        targets = self._load_targets(options.get("learner_ids"))
        if not targets:
            self.stdout.write(
                self.style.WARNING("No eligible Apprenticeship Agreement rows found.")
            )
            return

        workers = max(1, min(int(options["workers"]), 16))
        client = AptemClient()
        self.stdout.write("Logging in to Aptem...")
        client.login()
        self.stdout.write(
            self.style.SUCCESS(f"Login OK. Reviewing {len(targets)} learners.")
        )

        endpoint = (
            f"{client.base_url}/MWS.eDocuments/DynamicDocuments/"
            "ReadAllUserComplianceDocuments"
        )

        def fetch_versions(target):
            response = client.session.post(
                endpoint,
                data={"userId": target["learner_id"], "skip": 0, "take": 500},
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get("Data", [])

        selections = []
        no_prestart_version = []
        errors = []
        processed = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_targets = {
                pool.submit(fetch_versions, target): target for target in targets
            }
            for future in as_completed(future_targets):
                processed += 1
                target = future_targets[future]
                try:
                    documents = future.result()
                    version = best_agreement_version_for_start(
                        documents,
                        target["program_id"],
                        target["learn_start_date"],
                        reference_document_id=target["source_document_id"],
                    )
                    if version is None:
                        no_prestart_version.append(target)
                    else:
                        created_at = parse_version_datetime(version["CreateDateTime"])
                        selections.append(
                            {
                                **target,
                                "version_id": int(version["Id"]),
                                "version_created_at": created_at,
                                "is_after_start": (
                                    created_at.date() > target["learn_start_date"]
                                ),
                                "selected_file": agreement_version_url(
                                    client.base_url,
                                    version["Id"],
                                    target["learner_id"],
                                ),
                            }
                        )
                except Exception as exc:  # noqa: BLE001 - report individual failures.
                    errors.append((target, str(exc)))

                if processed % 25 == 0 or processed == len(targets):
                    self.stdout.write(f"Reviewed {processed}/{len(targets)} learners...")

        selections.sort(key=lambda item: item["full_name"])
        changed_links = sum(
            selection["current_file"] != selection["selected_file"]
            for selection in selections
        )
        already_selected = len(selections) - changed_links

        self.stdout.write("")
        self.stdout.write(f"Eligible database rows: {len(targets)}")
        after_start_selections = sum(
            selection["is_after_start"] for selection in selections
        )
        on_or_before_selections = len(selections) - after_start_selections
        self.stdout.write(
            f"On/before-start versions selected: {on_or_before_selections}"
        )
        self.stdout.write(
            f"Closest after-start fallbacks selected: {after_start_selections}"
        )
        self.stdout.write(f"Links that will change: {changed_links}")
        self.stdout.write(f"Links already on the selected version: {already_selected}")
        self.stdout.write(f"No matching programme version: {len(no_prestart_version)}")
        self.stdout.write(f"Fetch errors: {len(errors)}")

        for selection in selections[:12]:
            self.stdout.write(
                "  "
                f"{selection['full_name']} | start {selection['learn_start_date']} | "
                f"version {selection['version_id']} at "
                f"{selection['version_created_at'].isoformat(sep=' ')}"
            )

        if errors:
            for target, message in errors[:10]:
                self.stdout.write(
                    self.style.ERROR(
                        f"  {target['full_name']} ({target['learner_id']}): {message}"
                    )
                )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("Dry run complete. No database links were changed.")
            )
            return
        if errors:
            raise CommandError(
                "No links were changed because one or more Aptem requests failed."
            )

        with transaction.atomic(), connection.cursor() as cursor:
            for selection in selections:
                cursor.execute(
                    """
                    UPDATE fetching_evidence.aptem_cv_contracts_probe
                    SET apprenticeship_agreement_original_file = CASE
                            WHEN file IS DISTINCT FROM %s
                            THEN COALESCE(apprenticeship_agreement_original_file, file)
                            ELSE apprenticeship_agreement_original_file
                        END,
                        file = %s,
                        apprenticeship_agreement_version_id = %s,
                        apprenticeship_agreement_version_created_at = %s,
                        apprenticeship_agreement_version_selected_at = NOW()
                    WHERE id = %s
                      AND LOWER(TRIM(document_name)) = 'apprenticeship agreement'
                    """,
                    [
                        selection["selected_file"],
                        selection["selected_file"],
                        selection["version_id"],
                        selection["version_created_at"],
                        selection["row_id"],
                    ],
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {len(selections)} Apprenticeship Agreement rows; "
                f"{changed_links} file links were replaced."
            )
        )

    def _load_targets(self, learner_ids=None):
        learner_filter = ""
        params = []
        if learner_ids:
            learner_filter = "AND target.learner_id = ANY(%s)"
            params.append(learner_ids)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH ranked_ilr AS (
                    SELECT
                        delivery.learn_ref_number,
                        CONCAT_WS(' ', delivery.given_names, delivery.family_name) AS full_name,
                        delivery.email,
                        delivery.learn_start_date,
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
                    SELECT * FROM ranked_ilr
                    WHERE learner_row = 1 AND learn_start_date IS NOT NULL
                )
                SELECT
                    target.id AS row_id,
                    target.learner_id,
                    target.program_id,
                    target.source_document_id,
                    ilr.full_name,
                    ilr.email,
                    ilr.learn_start_date,
                    target.file AS current_file
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
                    SELECT document.*
                    FROM fetching_evidence.aptem_cv_contracts_probe document
                    WHERE document.learner_id = learner.aptem_id
                      AND LOWER(TRIM(document.document_name)) = 'apprenticeship agreement'
                    ORDER BY document.date DESC NULLS LAST, document.id DESC
                    LIMIT 1
                ) target ON TRUE
                WHERE target.id IS NOT NULL
                  AND (
                      target.source_document_id IS NOT NULL
                      OR target.program_id IS NOT NULL
                  )
                  {learner_filter}
                ORDER BY ilr.full_name ASC
                """,
                params,
            )
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, record)) for record in cursor.fetchall()]
