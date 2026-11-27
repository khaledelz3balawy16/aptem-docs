"""Fetch PLR records for selected Aptem users into a probe table."""

import json
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from evidence.services.aptem import AptemClient


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
    help = "Fetch Aptem PLR records into fetching_evidence.aptem_plr_probe."

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
            help="Fetch and print a preview without writing to the probe table.",
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

        total_records = 0
        errors = 0

        for index, learner_id in enumerate(learner_ids, 1):
            try:
                records = self._fetch_plr(client, learner_id)
            except Exception as exc:  # noqa: BLE001 - report and continue.
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[{index}/{len(learner_ids)}] learner {learner_id}: {exc}"
                    )
                )
                continue

            total_records += len(records)
            self._print_preview(index, len(learner_ids), learner_id, records)

            if not opts["dry_run"]:
                self._upsert_records(records)

            time.sleep(opts["sleep"])

        action = "fetched" if opts["dry_run"] else "upserted"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_records} PLR record(s) {action}; "
                f"{errors} learner error(s)."
            )
        )

    def _fetch_plr(self, client, learner_id):
        url = f"{client.base_url}/api/Users/{learner_id}/PLR"
        resp = client.session.get(
            url,
            headers={
                **client._api_headers(),
                "Accept": "application/json, text/plain, */*",
            },
            timeout=60,
        )
        if resp.status_code == 401:
            client.login()
            resp = client.session.get(
                url,
                headers={
                    **client._api_headers(),
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def _print_preview(self, index, total, learner_id, records):
        self.stdout.write(f"[{index}/{total}] learner {learner_id}: {len(records)} PLR record(s)")
        for record in records[:3]:
            self.stdout.write(
                "  - "
                f"Id={record.get('id')} | "
                f"Qualification={record.get('qualificationType') or ''} | "
                f"Subject={record.get('subjectCode') or ''} | "
                f"Grade={record.get('grade') or ''}"
            )

    def _ensure_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('CREATE SCHEMA IF NOT EXISTS "fetching_evidence"')
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS "fetching_evidence"."aptem_plr_probe" (
                    id BIGSERIAL PRIMARY KEY,
                    plr_id BIGINT NOT NULL UNIQUE,
                    learner_id BIGINT NOT NULL,
                    achievement_provider_name TEXT NOT NULL DEFAULT '',
                    qualification_type TEXT NOT NULL DEFAULT '',
                    subject_code TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL DEFAULT '',
                    participation_start_date TIMESTAMPTZ NULL,
                    award_date TIMESTAMPTZ NULL,
                    participation_end_date TIMESTAMPTZ NULL,
                    credits NUMERIC NULL,
                    grade TEXT NOT NULL DEFAULT '',
                    record_type INTEGER NULL,
                    creator_id BIGINT NULL,
                    document_id BIGINT NULL,
                    document_name TEXT NOT NULL DEFAULT '',
                    document_extension TEXT NOT NULL DEFAULT '',
                    document_file_size BIGINT NULL,
                    document_url TEXT NOT NULL DEFAULT '',
                    session_guid TEXT NOT NULL DEFAULT '',
                    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
                    fetched_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_plr_probe_learner_id_idx
                ON "fetching_evidence"."aptem_plr_probe" (learner_id)
                """
            )

    def _truncate_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('TRUNCATE TABLE "fetching_evidence"."aptem_plr_probe"')

    def _upsert_records(self, records):
        fetched_at = timezone.now()
        with transaction.atomic(), connection.cursor() as cur:
            for record in records:
                plr_id = record.get("id")
                if plr_id is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO "fetching_evidence"."aptem_plr_probe" (
                        plr_id,
                        learner_id,
                        achievement_provider_name,
                        qualification_type,
                        subject_code,
                        level,
                        participation_start_date,
                        award_date,
                        participation_end_date,
                        credits,
                        grade,
                        record_type,
                        creator_id,
                        document_id,
                        document_name,
                        document_extension,
                        document_file_size,
                        document_url,
                        session_guid,
                        raw,
                        fetched_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT (plr_id) DO UPDATE SET
                        learner_id = EXCLUDED.learner_id,
                        achievement_provider_name = EXCLUDED.achievement_provider_name,
                        qualification_type = EXCLUDED.qualification_type,
                        subject_code = EXCLUDED.subject_code,
                        level = EXCLUDED.level,
                        participation_start_date = EXCLUDED.participation_start_date,
                        award_date = EXCLUDED.award_date,
                        participation_end_date = EXCLUDED.participation_end_date,
                        credits = EXCLUDED.credits,
                        grade = EXCLUDED.grade,
                        record_type = EXCLUDED.record_type,
                        creator_id = EXCLUDED.creator_id,
                        document_id = EXCLUDED.document_id,
                        document_name = EXCLUDED.document_name,
                        document_extension = EXCLUDED.document_extension,
                        document_file_size = EXCLUDED.document_file_size,
                        document_url = EXCLUDED.document_url,
                        session_guid = EXCLUDED.session_guid,
                        raw = EXCLUDED.raw,
                        fetched_at = EXCLUDED.fetched_at
                    """,
                    [
                        plr_id,
                        record.get("userId"),
                        record.get("achievementProviderName") or "",
                        record.get("qualificationType") or "",
                        record.get("subjectCode") or "",
                        record.get("level") or "",
                        self._parse_date(record.get("participationStartDate")),
                        self._parse_date(record.get("awardDate")),
                        self._parse_date(record.get("participationEndDate")),
                        record.get("credits"),
                        record.get("grade") or "",
                        record.get("recordType"),
                        record.get("creatorId"),
                        record.get("documentId"),
                        record.get("documentName") or "",
                        record.get("documentExtension") or "",
                        record.get("documentFileSize"),
                        record.get("documentUrl") or "",
                        record.get("sessionGuid") or "",
                        json.dumps(record, ensure_ascii=False),
                        fetched_at,
                    ],
                )

    def _parse_date(self, value):
        return parse_datetime(value) if isinstance(value, str) else None
