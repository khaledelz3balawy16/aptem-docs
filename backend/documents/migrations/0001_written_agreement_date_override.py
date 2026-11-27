from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS comparison_written_agreement_date DATE NULL
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
