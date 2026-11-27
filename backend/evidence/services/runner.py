"""Safe entry point for future pages that need to run Aptem fetch jobs.

The Documents page does not call this module. Future pages can import
``available_fetch_jobs`` to render their own controls and ``run_fetch_job`` to
execute a selected job. Only commands in the allowlist can be executed.
"""

from io import StringIO

from django.core.management import call_command


FETCH_JOBS = {
    "learning-plan-evidence": {
        "label": "Learning Plan Evidence",
        "command": "fetch_evidence_probe",
    },
    "cv-and-contracts": {
        "label": "CV and Contract Documents",
        "command": "fetch_cv_contracts_probe",
    },
    "plr": {
        "label": "Prior Learning Records",
        "command": "fetch_plr_probe",
    },
    "skills-radar": {
        "label": "Skills Radar",
        "command": "fetch_skills_radar_probe",
    },
}


class UnknownFetchJob(ValueError):
    pass


def available_fetch_jobs():
    return [
        {"key": key, "label": job["label"]}
        for key, job in FETCH_JOBS.items()
    ]


def run_fetch_job(job_key, learner_ids=None, dry_run=True, **options):
    """Run an allowlisted fetch command and return its console output.

    ``dry_run`` defaults to ``True`` so a future page must explicitly opt in
    before writing fetched data to PostgreSQL.
    """
    job = FETCH_JOBS.get(job_key)
    if not job:
        raise UnknownFetchJob(f"Unknown fetch job: {job_key}")

    stdout = StringIO()
    command_options = {
        "stdout": stdout,
        "dry_run": dry_run,
        **options,
    }
    if learner_ids:
        command_options["learner_ids"] = [int(value) for value in learner_ids]

    call_command(job["command"], **command_options)
    return stdout.getvalue()
