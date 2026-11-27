from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0004_remove_combined_planned_otj_hours")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS written_agreement_funding JSONB NULL
            """,
            reverse_sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS written_agreement_funding
            """,
        )
    ]
