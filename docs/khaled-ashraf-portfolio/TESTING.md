# Testing and validation

## Preparation checks completed

- Captured source at the recorded commit.
- Checked archive paths, symlinks, and file inclusion rules.
- Replaced detected credential literals, connection strings, and contact addresses with placeholders.
- Removed data exports, runtime environments, private keys, generated output, and internal assistant artifacts.
- Re-scanned the prepared text for the supported sensitive-value patterns.
- Parsed generated JSON documents and package manifests.

## Application validation

Dependencies were not installed. Application tests, servers, migrations, seeders, and database or external-service requests were not run. Runtime correctness after configuration and data removal remains to be verified by the project maintainer.

## Existing test sources

- `backend/documents/tests/test_endpoint_assessment.py`
- `backend/documents/tests/test_funding_comparison.py`
- `backend/documents/tests/test_hours_comparison.py`
- `backend/documents/tests/test_monthly_hours_services.py`
- `backend/documents/tests/test_prior_learning.py`
- `backend/documents/tests/test_program_status_services.py`
- `backend/documents/tests/test_skills_radar.py`
- `backend/documents/tests/test_start_date_comparison.py`
- `backend/documents/tests/test_written_agreement_refetch.py`
- `backend/evidence/tests/test_apprenticeship_versions.py`
- `backend/evidence/tests/test_compliance_pdf.py`
- `backend/evidence/tests/test_cv_certifications.py`
- `backend/evidence/tests/test_written_agreement_funding.py`
