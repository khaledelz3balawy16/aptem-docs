"""Fetch evidence for a fixed learner list into a separate probe table."""

import json
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from evidence.services.aptem import AptemAuthError, AptemClient


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


class Command(BaseCommand):
    help = "Fetch evidence for selected learners into fetching_evidence.aptem_evidence_probe."

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
            default=0.3,
            help="Seconds to pause between learners.",
        )
        parser.add_argument(
            "--preview",
            type=int,
            default=3,
            help="Number of evidence items to preview per learner.",
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

        total_items = 0
        errors = 0
        for i, learner_id in enumerate(learner_ids, 1):
            try:
                items = self._fetch_with_retry(client, learner_id)
            except Exception as exc:  # noqa: BLE001 - keep the probe moving.
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[{i}/{len(learner_ids)}] learner {learner_id}: {exc}"
                    )
                )
                continue

            total_items += len(items)
            self._print_preview(i, len(learner_ids), learner_id, items, opts["preview"])

            if not opts["dry_run"]:
                self._upsert_items(client, learner_id, items)

            time.sleep(opts["sleep"])

        action = "fetched" if opts["dry_run"] else "upserted"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_items} evidence item(s) {action}; {errors} learner error(s)."
            )
        )

    def _fetch_with_retry(self, client, learner_id):
        try:
            return client.fetch_evidence(learner_id)
        except AptemAuthError:
            client.login()
            return client.fetch_evidence(learner_id)

    def _print_preview(self, index, total, learner_id, items, preview_count):
        self.stdout.write(f"[{index}/{total}] learner {learner_id}: {len(items)} evidence")
        for ev in items[:preview_count]:
            self.stdout.write(
                "  - "
                f"Id={ev.get('Id')} | "
                f"Name={ev.get('EvidenceName') or ''} | "
                f"Kind={ev.get('EvidenceKind') or ''} | "
                f"Status={ev.get('LatestStatus') or ''}"
            )

    def _ensure_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('CREATE SCHEMA IF NOT EXISTS "fetching_evidence"')
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS "fetching_evidence"."aptem_evidence_probe" (
                    id BIGSERIAL PRIMARY KEY,
                    evidence_id BIGINT NOT NULL UNIQUE,
                    learner_id BIGINT NOT NULL,
                    component_id BIGINT NULL,
                    evidence_name TEXT NOT NULL DEFAULT '',
                    evidence_kind TEXT NOT NULL DEFAULT '',
                    latest_status TEXT NOT NULL DEFAULT '',
                    created_date TIMESTAMPTZ NULL,
                    file TEXT NOT NULL DEFAULT '',
                    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
                    fetched_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_evidence_probe_learner_id_idx
                ON "fetching_evidence"."aptem_evidence_probe" (learner_id)
                """
            )

    def _truncate_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('TRUNCATE TABLE "fetching_evidence"."aptem_evidence_probe"')

    def _upsert_items(self, client, learner_id, items):
        fetched_at = timezone.now()
        with transaction.atomic(), connection.cursor() as cur:
            for ev in items:
                ev_id = ev.get("Id")
                if ev_id is None:
                    continue

                created = ev.get("CreatedDate") or ev.get("SubmissionDate")
                created_date = parse_datetime(created) if isinstance(created, str) else None
                cur.execute(
                    """
                    INSERT INTO "fetching_evidence"."aptem_evidence_probe" (
                        evidence_id,
                        learner_id,
                        component_id,
                        evidence_name,
                        evidence_kind,
                        latest_status,
                        created_date,
                        file,
                        raw,
                        fetched_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (evidence_id) DO UPDATE SET
                        learner_id = EXCLUDED.learner_id,
                        component_id = EXCLUDED.component_id,
                        evidence_name = EXCLUDED.evidence_name,
                        evidence_kind = EXCLUDED.evidence_kind,
                        latest_status = EXCLUDED.latest_status,
                        created_date = EXCLUDED.created_date,
                        file = EXCLUDED.file,
                        raw = EXCLUDED.raw,
                        fetched_at = EXCLUDED.fetched_at
                    """,
                    [
                        ev_id,
                        learner_id,
                        ev.get("ComponentId"),
                        ev.get("EvidenceName") or "",
                        ev.get("EvidenceKind") or "",
                        ev.get("LatestStatus") or "",
                        created_date,
                        client.document_url(ev_id),
                        json.dumps(ev, ensure_ascii=False),
                        fetched_at,
                    ],
                )
