# Aptem Documents

The project is split into two independent applications:

- `backend/`: Django JSON API connected to PostgreSQL.
- `frontend/`: React application built with Vite.

## Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py runserver
```

The API runs at `http://127.0.0.1:8000`.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The application runs at `http://localhost:5173`. During local development,
Vite proxies `/api` requests to Django.

## Aptem fetch services

The Django backend includes reusable Aptem login, cohort, fetch, and PostgreSQL
upsert logic for future pages. Fetching is not exposed on the Learner Documents
page.

Available management commands:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py fetch_evidence
.\.venv\Scripts\python.exe manage.py fetch_evidence_probe --dry-run
.\.venv\Scripts\python.exe manage.py fetch_cv_contracts_probe --dry-run
.\.venv\Scripts\python.exe manage.py fetch_plr_probe --dry-run
.\.venv\Scripts\python.exe manage.py fetch_skills_radar_probe --dry-run
```

Future Django pages can use `evidence.services.runner.available_fetch_jobs`
and `evidence.services.runner.run_fetch_job`. The runner defaults to dry-run
mode and only permits allowlisted jobs.
