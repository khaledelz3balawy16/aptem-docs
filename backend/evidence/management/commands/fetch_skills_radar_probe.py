"""Fetch Aptem skills radar competency progress into a probe table."""

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
    help = "Fetch skills radar progress into fetching_evidence.aptem_skills_radar_probe."

    def add_arguments(self, parser):
        parser.add_argument(
            "--learner-id",
            type=int,
            action="append",
            dest="learner_ids",
            help="Learner ID to fetch. Can be repeated. Defaults to the 12 probe learners.",
        )
        parser.add_argument(
            "--competency-id",
            type=int,
            default=None,
            help="Specific competency ID to fetch. If omitted, all assigned competencies are fetched per learner.",
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
        parser.add_argument(
            "--preview",
            type=int,
            default=3,
            help="Number of radar items to preview per learner.",
        )

    def handle(self, *args, **opts):
        learner_ids = opts["learner_ids"] or DEFAULT_LEARNER_IDS
        requested_competency_id = opts["competency_id"]

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

        for index, learner_id in enumerate(learner_ids, 1):
            try:
                competencies = (
                    [{"id": requested_competency_id, "name": "", "isAssessed": None}]
                    if requested_competency_id
                    else self._fetch_assigned_competencies(client, learner_id)
                )
                learner_total = 0
                all_items = []
                for competency in competencies:
                    items = self._fetch_skills_radar(
                        client, learner_id, competency["id"]
                    )
                    learner_total += len(items)
                    all_items.append((competency, items))
            except Exception as exc:  # noqa: BLE001 - report and continue.
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[{index}/{len(learner_ids)}] learner {learner_id}: {exc}"
                    )
                )
                continue

            total_items += learner_total
            self._print_preview(index, len(learner_ids), learner_id, all_items, opts["preview"])

            if not opts["dry_run"]:
                for competency, items in all_items:
                    self._upsert_items(learner_id, competency, items)

            time.sleep(opts["sleep"])

        action = "fetched" if opts["dry_run"] else "upserted"
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_items} skills radar item(s) {action}; "
                f"{errors} learner error(s)."
            )
        )

    def _fetch_assigned_competencies(self, client, learner_id):
        url = f"{client.base_url}/MWS.LM/Competence/AssignedCompetencies"
        resp = client.session.get(
            url,
            params={"userId": learner_id},
            headers={"Accept": "application/json, text/plain, */*"},
            timeout=60,
        )
        if resp.status_code == 401:
            client.login()
            resp = client.session.get(
                url,
                params={"userId": learner_id},
                headers={"Accept": "application/json, text/plain, */*"},
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def _fetch_skills_radar(self, client, learner_id, competency_id):
        url = f"{client.base_url}/api/MWS.LM/Competency/Progress"
        headers = {
            **client._api_headers(),
            "Accept": "application/json, text/plain, */*",
        }
        params = {"competencyId": competency_id, "userId": learner_id}
        resp = client.session.get(url, params=params, headers=headers, timeout=60)
        if resp.status_code == 401:
            client.login()
            resp = client.session.get(url, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def _print_preview(self, index, total, learner_id, all_items, preview_count):
        total_items = sum(len(items) for _, items in all_items)
        self.stdout.write(
            f"[{index}/{total}] learner {learner_id}: "
            f"{len(all_items)} competenc{('y' if len(all_items) == 1 else 'ies')}, "
            f"{total_items} skills radar item(s)"
        )
        remaining = preview_count
        for competency, items in all_items:
            self.stdout.write(
                f"  competency {competency.get('id')}: "
                f"{competency.get('name') or ''} ({len(items)} item(s))"
            )
            for item in items[:remaining]:
                assessed_level = item.get("assessedLevel") or {}
                self.stdout.write(
                    "    - "
                    f"Id={item.get('id')} | "
                    f"Level={assessed_level.get('level') or ''} | "
                    f"Color={assessed_level.get('color') or ''} | "
                    f"Name={item.get('name') or ''}"
                )
            remaining = max(0, remaining - len(items[:remaining]))

    def _ensure_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('CREATE SCHEMA IF NOT EXISTS "fetching_evidence"')
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS "fetching_evidence"."aptem_skills_radar_probe" (
                    id BIGSERIAL PRIMARY KEY,
                    learner_id BIGINT NOT NULL,
                    competency_id BIGINT NOT NULL,
                    competency_name TEXT NOT NULL DEFAULT '',
                    competency_is_assessed BOOLEAN NULL,
                    competency_need_dates_selector BOOLEAN NULL,
                    competency_read_only BOOLEAN NULL,
                    characteristic_id BIGINT NOT NULL,
                    characteristic_name TEXT NOT NULL DEFAULT '',
                    assessed_characteristics_level_id BIGINT NULL,
                    assessed_level INTEGER NULL,
                    assessed_color TEXT NOT NULL DEFAULT '',
                    assessed_short_description TEXT NOT NULL DEFAULT '',
                    latest_assessment_id BIGINT NULL,
                    latest_user_competence_characteristic_id BIGINT NULL,
                    latest_assessment_level_id BIGINT NULL,
                    latest_completed_date TIMESTAMPTZ NULL,
                    latest_assessor_id BIGINT NULL,
                    latest_assessment_type TEXT NOT NULL DEFAULT '',
                    notes TEXT NULL,
                    levels JSONB NOT NULL DEFAULT '[]'::jsonb,
                    assessments JSONB NOT NULL DEFAULT '[]'::jsonb,
                    actions JSONB NOT NULL DEFAULT '[]'::jsonb,
                    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
                    fetched_at TIMESTAMPTZ NOT NULL,
                    natural_key TEXT NOT NULL UNIQUE
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_skills_radar_probe_learner_id_idx
                ON "fetching_evidence"."aptem_skills_radar_probe" (learner_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS aptem_skills_radar_probe_competency_id_idx
                ON "fetching_evidence"."aptem_skills_radar_probe" (competency_id)
                """
            )

    def _truncate_probe_table(self):
        with connection.cursor() as cur:
            cur.execute('TRUNCATE TABLE "fetching_evidence"."aptem_skills_radar_probe"')

    def _upsert_items(self, learner_id, competency, items):
        competency_id = competency.get("id")
        fetched_at = timezone.now()
        with transaction.atomic(), connection.cursor() as cur:
            for item in items:
                characteristic_id = item.get("id")
                if characteristic_id is None:
                    continue

                assessed_level = item.get("assessedLevel") or {}
                assessments = item.get("assessments") or []
                latest_assessment = assessments[-1] if assessments else {}
                natural_key = f"{learner_id}|{competency_id}|{characteristic_id}"

                cur.execute(
                    """
                    INSERT INTO "fetching_evidence"."aptem_skills_radar_probe" (
                        learner_id,
                        competency_id,
                        competency_name,
                        competency_is_assessed,
                        competency_need_dates_selector,
                        competency_read_only,
                        characteristic_id,
                        characteristic_name,
                        assessed_characteristics_level_id,
                        assessed_level,
                        assessed_color,
                        assessed_short_description,
                        latest_assessment_id,
                        latest_user_competence_characteristic_id,
                        latest_assessment_level_id,
                        latest_completed_date,
                        latest_assessor_id,
                        latest_assessment_type,
                        notes,
                        levels,
                        assessments,
                        actions,
                        raw,
                        fetched_at,
                        natural_key
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                        %s::jsonb, %s::jsonb, %s, %s
                    )
                    ON CONFLICT (natural_key) DO UPDATE SET
                        competency_name = EXCLUDED.competency_name,
                        competency_is_assessed = EXCLUDED.competency_is_assessed,
                        competency_need_dates_selector = EXCLUDED.competency_need_dates_selector,
                        competency_read_only = EXCLUDED.competency_read_only,
                        characteristic_name = EXCLUDED.characteristic_name,
                        assessed_characteristics_level_id = EXCLUDED.assessed_characteristics_level_id,
                        assessed_level = EXCLUDED.assessed_level,
                        assessed_color = EXCLUDED.assessed_color,
                        assessed_short_description = EXCLUDED.assessed_short_description,
                        latest_assessment_id = EXCLUDED.latest_assessment_id,
                        latest_user_competence_characteristic_id = EXCLUDED.latest_user_competence_characteristic_id,
                        latest_assessment_level_id = EXCLUDED.latest_assessment_level_id,
                        latest_completed_date = EXCLUDED.latest_completed_date,
                        latest_assessor_id = EXCLUDED.latest_assessor_id,
                        latest_assessment_type = EXCLUDED.latest_assessment_type,
                        notes = EXCLUDED.notes,
                        levels = EXCLUDED.levels,
                        assessments = EXCLUDED.assessments,
                        actions = EXCLUDED.actions,
                        raw = EXCLUDED.raw,
                        fetched_at = EXCLUDED.fetched_at
                    """,
                    [
                        learner_id,
                        competency_id,
                        competency.get("name") or "",
                        competency.get("isAssessed"),
                        competency.get("needDatesSelector"),
                        competency.get("readOnly"),
                        characteristic_id,
                        item.get("name") or "",
                        assessed_level.get("characteristicsLevelId"),
                        assessed_level.get("level"),
                        assessed_level.get("color") or "",
                        assessed_level.get("shortDescription") or "",
                        latest_assessment.get("userCompetenceCharacteristicAssesmentId"),
                        latest_assessment.get("userCompetenceCharacteristicId"),
                        latest_assessment.get("characteristicsLevelId"),
                        self._parse_date(latest_assessment.get("completedDate")),
                        latest_assessment.get("assessorId"),
                        latest_assessment.get("assessmentType") or "",
                        item.get("notes"),
                        json.dumps(item.get("levels") or [], ensure_ascii=False),
                        json.dumps(assessments, ensure_ascii=False),
                        json.dumps(item.get("actions") or [], ensure_ascii=False),
                        json.dumps(item, ensure_ascii=False),
                        fetched_at,
                        natural_key,
                    ],
                )

    def _parse_date(self, value):
        return parse_datetime(value) if isinstance(value, str) else None
