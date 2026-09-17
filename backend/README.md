# backend

Development-mode notes for the ActionBOM backend.

For the normal path (docker-compose, one command), see the [root README](../README.md).

## Running without Docker

Useful when iterating on the backend and you want auto-reload.

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ running somewhere you control
- (Optional) [Zizmor](https://github.com/woodruffw/zizmor) for SAST scanning:

  ```bash
  cargo install zizmor
  # or download from https://github.com/woodruffw/zizmor/releases
  ```

  If Zizmor isn't installed, SAST scans are skipped; SBOM + SCA still work.

### Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` from the repo root and fill in `DATABASE_URL` and
`GITHUB_TOKEN`:

```bash
cp ../.env.example .env
```

Initialize the schema against your Postgres:

```bash
psql "$DATABASE_URL" -f ../init.sql
```

The app will also auto-create the schema on startup, so this step is
optional — but it's the fastest way to verify your connection string
works.

### Running

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

### Manual cron trigger

The cron scheduler runs automatically on startup (if `CRON_ENABLED=true`).
To trigger a scan manually without waiting for the schedule:

```bash
python -m app.cron.workflow_scanner
```

### Manual repo import

```bash
python -m app.import_repos --org your-org
```

## Layout

```
backend/app/
├── main.py              FastAPI entry, lifespan, static-file serving
├── config.py            Settings (env vars)
├── database.py          SQLAlchemy engine, SessionLocal, init_db()
├── models.py            All 5 SQLAlchemy models (actionbom schema)
├── schemas.py           Pydantic request/response schemas
├── import_repos.py      CLI: python -m app.import_repos --org <org>
├── api/endpoints.py     REST routes (mounted at /api)
├── cron/workflow_scanner.py    daily_batch_scan_job()
├── services/
│   ├── github_service.py       GitHub REST wrapper (singleton)
│   ├── scanner_service.py      actionbom + zizmor integration
│   ├── slack_service.py        Slack webhook alerts
│   └── repo_importer.py        Bulk-import from a GitHub org
└── repositories/
    ├── repository_repo.py      Repository CRUD + batch selection
    ├── workflow_repo.py        Workflow queries
    └── org_action_repo.py      Org-wide action inventory
```

For a deeper look at data flow and architecture, see
[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Troubleshooting

**Database connection error.** Verify `DATABASE_URL` points at a running
Postgres. Test with `psql "$DATABASE_URL" -c "SELECT 1;"`.

**GitHub rate limit.** Check your remaining quota:

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/rate_limit
```

**No repos found.** The repositories table is populated via
`TARGET_ORG` auto-import, the dashboard's welcome card, or the
`import_repos` CLI. See the [root README](../README.md) for details.

**Zizmor missing.** SAST scans are skipped when the `zizmor` binary
isn't on `PATH`. Install it, or ignore — SBOM + SCA still work.
