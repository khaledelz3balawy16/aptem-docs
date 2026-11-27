"""Fetch evidence for active learners from Aptem and store it in Neon.

Workflow:
  1. Read active learners (ID + Program Name) from LMS.Aptem_users.
  2. Log in to Aptem.
  3. For each learner, fetch ALL their evidence (no filter).
  4. Tag each evidence item with the learner id + programme name, and store
     the raw Aptem document URL in the `file` column.
  5. Upsert into the aptem_evidence table.

Usage:
  python manage.py fetch_evidence               # all active learners
  python manage.py fetch_evidence --limit 3     # test on first 3 learners
  python manage.py fetch_evidence --program PCP  # only programmes matching "PCP"
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils.dateparse import parse_datetime

from evidence.models import AptemEvidence
from evidence.services.aptem import AptemAuthError, AptemClient
from evidence.services.cohort import get_active_learners


class Command(BaseCommand):
    help = "Fetch all evidence for active learners from Aptem into Neon."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Process only the first N learners (for testing).",
        )
        parser.add_argument(
            "--program", type=str, default=None,
            help="Only learners whose Program Name contains this text.",
        )
        parser.add_argument(
            "--sleep", type=float, default=0.3,
            help="Seconds to pause between learners (rate limiting).",
        )

    def handle(self, *args, **opts):
        self._ensure_table()
        learners = get_active_learners(program_contains=opts["program"])
        if opts["limit"]:
            learners = learners[: opts["limit"]]

        self.stdout.write(f"Active learners to process: {len(learners)}")
        if not learners:
            self.stdout.write(self.style.WARNING("Nothing to do."))
            return

        client = AptemClient()
        self.stdout.write("Logging in to Aptem...")
        client.login()
        self.stdout.write(self.style.SUCCESS("Login OK"))

        total_ev = 0
        errors = 0
        for i, lr in enumerate(learners, 1):
            lid = lr["id"]
            try:
                items = self._fetch_with_retry(client, lid)
            except Exception as exc:  # noqa: BLE001 - report and continue
                errors += 1
                self.stdout.write(self.style.ERROR(f"  [{i}/{len(learners)}] learner {lid}: {exc}"))
                continue

            for ev in items:
                self._upsert(client, ev, lr)
            total_ev += len(items)
            self.stdout.write(
                f"  [{i}/{len(learners)}] learner {lid} "
                f"({lr['program_name']}): {len(items)} evidence"
            )
            time.sleep(opts["sleep"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_ev} evidence rows upserted; {errors} learner error(s)."
            )
        )

    def _ensure_table(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE SCHEMA IF NOT EXISTS "fetching_evidence"')
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "fetching_evidence"."aptem_evidence" (
                    id BIGSERIAL PRIMARY KEY,
                    evidence_id BIGINT NOT NULL UNIQUE,
                    component_id BIGINT NULL,
                    evidence_name TEXT NOT NULL DEFAULT '',
                    evidence_kind TEXT NOT NULL DEFAULT '',
                    latest_status TEXT NOT NULL DEFAULT '',
                    created_date TIMESTAMPTZ NULL,
                    file TEXT NOT NULL DEFAULT '',
                    learner_id BIGINT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    program_name TEXT NULL,
                    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_evidence_learner_id_idx
                ON "fetching_evidence"."aptem_evidence" (learner_id)
                """
            )

    def _fetch_with_retry(self, client, learner_id):
        """Fetch, re-logging-in once if the session token expired mid-run."""
        try:
            return client.fetch_evidence(learner_id)
        except AptemAuthError:
            client.login()
            return client.fetch_evidence(learner_id)

    def _upsert(self, client, ev, lr):
        ev_id = ev.get("Id")
        if ev_id is None:
            return

        created = ev.get("CreatedDate") or ev.get("SubmissionDate")
        AptemEvidence.objects.update_or_create(
            evidence_id=ev_id,
            defaults={
                "component_id": ev.get("ComponentId"),
                "evidence_name": ev.get("EvidenceName") or "",
                "evidence_kind": ev.get("EvidenceKind") or "",
                "latest_status": ev.get("LatestStatus") or "",
                "created_date": parse_datetime(created) if isinstance(created, str) else None,
                "file": client.document_url(ev_id),
                "learner_id": lr["id"],
                "full_name": lr.get("full_name") or "",
                "program_name": lr.get("program_name"),
                "raw": ev,
            },
        )
