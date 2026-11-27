from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0003_separate_planned_otj_hours_sources")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS planned_off_the_job_hours
            """,
            reverse_sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS planned_off_the_job_hours NUMERIC(14, 2) NULL
            """,
        )
    ]
