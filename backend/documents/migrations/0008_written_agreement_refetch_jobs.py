from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0007_apprenticeship_agreement_selected_version")]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS fetching_evidence.written_agreement_refetch_jobs (
                    id UUID PRIMARY KEY,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    total INTEGER NOT NULL DEFAULT 0,
                    processed INTEGER NOT NULL DEFAULT 0,
                    updated_links INTEGER NOT NULL DEFAULT 0,
                    extracted INTEGER NOT NULL DEFAULT 0,
                    skipped INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMPTZ NULL,
                    completed_at TIMESTAMPTZ NULL
                );
                CREATE INDEX IF NOT EXISTS written_agreement_refetch_jobs_scope_status_idx
                ON fetching_evidence.written_agreement_refetch_jobs (scope, status);
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS fetching_evidence.written_agreement_refetch_jobs;
            """,
        )
    ]
