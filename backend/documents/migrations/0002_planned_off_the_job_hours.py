from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_written_agreement_date_override")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS planned_off_the_job_hours NUMERIC(14, 2) NULL
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
