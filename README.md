# ActionBOM

**A GitHub Actions supply-chain security dashboard for your org.**

Recursive SBOM generation, CVE scanning via OSV.dev, static analysis via Zizmor,
and org-wide action inventory — in a single self-hosted dashboard.

---

## Quick start

```bash
git clone https://github.com/YOUR_ORG/actionbom.git
cd actionbom
cp .env.example .env      # add GITHUB_TOKEN (and optionally TARGET_ORG)
docker compose up
```

Open **http://localhost:8000**.

- If you set `TARGET_ORG`, repos auto-import from GitHub on first boot.
- Otherwise, type your org name into the dashboard's welcome card.

The first workflow scan lands within one cron tick (default: 30 minutes).

## What it does

**Recursive SBOM per workflow.** Follows every `uses:` reference, expands
composite actions and reusable workflows, resolves floating refs (`v4`,
`main`) to concrete commit SHAs. Emits CycloneDX 1.4.

**CVE scanning.** Queries OSV.dev for every third-party action, matches
against affected version ranges, and surfaces severity-graded findings
with fix versions and advisory links.

**Static analysis.** Runs [Zizmor](https://github.com/woodruffw/zizmor) on
every workflow. Detects template injection, unpinned refs, dangerous
triggers, and other common misconfigurations. Findings are shown as SARIF
in the workflow detail view.

**Org-wide action inventory.** Which repos use `tj-actions/changed-files`?
Which versions? Which of those versions are vulnerable? One click.

**Optional Slack alerts.** New CRITICAL SCA findings and new
template-injection SAST findings can post to a Slack webhook. Dedup is
per (action, advisory) — no repeat noise across cron runs.

## Configuration

All configuration lives in `.env` (copy `.env.example` to start). Most
users only need the first two.

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | *(empty)* | PAT or fine-grained token with `repo` read scope. Lifts API rate limit from 60/hr → 5000/hr and enables private repo scanning. |
| `TARGET_ORG` | *(empty)* | GitHub org to auto-import on first boot. Leave blank to import via the dashboard's welcome card. |
| `CRON_SCHEDULE` | `*/30 * * * *` | Standard 5-field cron in UTC. Bump to `0 */3 * * *` or slower for orgs with >1000 repos. |
| `CRON_ENABLED` | `true` | Set to `false` to run API-only (no background scanning). |
| `BATCH_SIZE` | `50` | Repos scanned per cron tick. |
| `RATE_LIMIT_THRESHOLD` | `500` | Abort a cron run if fewer than this many GitHub API requests remain. |
| `SLACK_WEBHOOK_URL` | *(empty)* | Incoming webhook URL. Leave blank to disable alerts. |
| `SLACK_CC_USER_ID` | *(empty)* | Slack user ID to cc on template-injection alerts (e.g. `U08FVDUN2MS`). |
| `DASHBOARD_BASE_URL` | `http://localhost:8000` | Used in Slack alert links. |
| `LOG_LEVEL` | `INFO` | uvicorn log level. |
| `DATABASE_URL` | *(compose-managed)* | When running via docker-compose, ignore this — compose injects it. Set only for standalone dev against your own Postgres. |

## Architecture

Single container, port 8000. FastAPI serves both the REST API (`/api/*`)
and the built React SPA. PostgreSQL sits alongside via docker-compose,
persisted in a named volume.

```
docker-compose ──┬── app (Python 3.11 + Node build → uvicorn on :8000)
                 │     ├── FastAPI + APScheduler cron
                 │     ├── actionbom library (SBOM + OSV scanning)
                 │     └── zizmor binary (SAST)
                 │
                 └── db (postgres:16-alpine, mounted init.sql)
```

- Cron picks up the least-recently-scanned repos each tick, respects
  rate limit budget, dedups unchanged workflows by file blob SHA.
- Frontend: React 19 + Vite + Tailwind. React Query for state.
- All app data lives in the `actionbom` schema (see [init.sql](init.sql)).

For a deeper look at data flow, batch selection, and gotchas, see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Managing repositories

**Auto-import on boot.** Set `TARGET_ORG` in `.env`, restart. Any repos
not yet tracked are inserted. Idempotent — existing rows (and any
manual annotations) are preserved.

**On-demand from the dashboard.** When the repositories table is empty,
the dashboard shows a welcome card with an input for your org name.

**On-demand from the CLI.** For pulling in newly-created repos or
importing a second org:

```bash
docker compose exec app python -m app.import_repos --org your-org
```

**On-demand from the API.** For scripting/CI:

```bash
curl -X POST http://localhost:8000/api/repositories/import \
  -H "Content-Type: application/json" \
  -d '{"org": "your-org"}'
```

## Advanced: standalone CLI

The core `actionbom` Python package can also run as a standalone CLI —
useful for ad-hoc scans without the dashboard.

```bash
python -m actionbom scan --workflow .github/workflows/ci.yml
```

See [docs/CLI.md](docs/CLI.md) for full usage.

## Development

Run the backend directly (auto-reload) against your own Postgres:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run the frontend dev server (proxies `/api` to `localhost:8000`):

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

After frontend changes, rebuild the Docker image:

```bash
docker compose build
```

See [backend/README.md](backend/README.md) for development-specific notes.

## Contributing

Issues and PRs welcome. Please:

- Run the type-check (`cd frontend && npx tsc --noEmit`) before opening a PR.
- Include repro steps for bugs.
- For larger changes, open an issue first to discuss the approach.

## Acknowledgments

- [CycloneDX](https://cyclonedx.org/) for the SBOM specification
- [OSV.dev](https://osv.dev/) for the vulnerability database
- [Zizmor](https://github.com/woodruffw/zizmor) for SAST analysis
- The GitHub Actions community

## License

See the [LICENSE](LICENSE) file for details.
