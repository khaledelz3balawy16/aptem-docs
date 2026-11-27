from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0005_written_agreement_funding")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS comparison_apprenticeship_agreement_date DATE NULL
            """,
            reverse_sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS comparison_apprenticeship_agreement_date
            """,
        )
    ]
