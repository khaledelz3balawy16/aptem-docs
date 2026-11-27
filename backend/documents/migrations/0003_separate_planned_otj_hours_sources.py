from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0002_planned_off_the_job_hours")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS training_plan_planned_hours NUMERIC(14, 2) NULL;

                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_planned_hours
                NUMERIC(14, 2) NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
