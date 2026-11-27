from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("documents", "0006_apprenticeship_agreement_date_override")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_original_file TEXT NULL;

                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_version_id BIGINT NULL;

                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_version_created_at
                    TIMESTAMP WITHOUT TIME ZONE NULL;

                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                ADD COLUMN IF NOT EXISTS apprenticeship_agreement_version_selected_at
                    TIMESTAMPTZ NULL;
            """,
            reverse_sql="""
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS apprenticeship_agreement_version_selected_at;
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS apprenticeship_agreement_version_created_at;
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS apprenticeship_agreement_version_id;
                ALTER TABLE fetching_evidence.aptem_cv_contracts_probe
                DROP COLUMN IF EXISTS apprenticeship_agreement_original_file;
            """,
        )
    ]
