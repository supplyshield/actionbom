# Architecture

This is a deep-dive for contributors and operators. For the user-facing
overview, see the [root README](../README.md).

## What this is

A GitHub Actions supply-chain security platform. It scans an org's
workflow files, builds a dependency graph (SBOM), checks for known CVEs
via OSV.dev, and runs SAST via Zizmor. Results are stored in PostgreSQL
and displayed in a React dashboard.

Deployed as a **single Docker container**: FastAPI serves both the API
(`/api/*`) and the React SPA (static files) on port 8000. Postgres is a
separate compose service.

## Directory structure

```
actionbom/              Core Python library (SBOM generation + vuln scanning)
backend/                FastAPI service
  app/
    main.py             App entry, lifespan, static file serving, cron startup
    config.py           Settings from env vars (Settings class)
    database.py         SQLAlchemy engine, SessionLocal, Base, get_db(), init_db()
    models.py           All 5 SQLAlchemy models (actionbom schema)
    schemas.py          Pydantic schemas
    import_repos.py     CLI: python -m app.import_repos --org <org>
    api/
      endpoints.py      All REST endpoints (mounted at /api)
    cron/
      workflow_scanner.py     daily_batch_scan_job() — the main cron function
    services/
      github_service.py       GitHubService singleton (github_service)
      scanner_service.py      ScannerService singleton (scanner_service)
      slack_service.py        SlackService (webhook alerts)
      repo_importer.py        import_org_repos() bulk upsert
    repositories/
      repository_repo.py      RepositoryRepository (batch query, touch_scan_log, count)
      workflow_repo.py        WorkflowRepository (latest scan per workflow)
      org_action_repo.py      OrgActionRepository (org-wide actions inventory)
frontend/               React 19 + TypeScript SPA
  src/
    App.tsx             Router + QueryClient setup
    lib/api.ts          API client (all calls use relative /api prefix)
    lib/sbomLayout.ts   Graph layout algorithm
    types/api.ts        TypeScript interfaces for all API responses
    pages/
      RepositoriesPage.tsx      /
      WorkflowsPage.tsx         /repo/:repoId
      WorkflowDetailPage.tsx    /workflow/:workflowId (3 tabs: SBOM, SCA, SAST)
      ActionsInventoryPage.tsx  /actions
      ActionDetailPage.tsx      /actions/* (wildcard for action names with slashes)
    components/
      Layout.tsx, Breadcrumbs.tsx, ThemeToggle.tsx,
      StatusBadge.tsx, SeverityBadge.tsx, PipelineLoader.tsx,
      SbomGraphView.tsx, SbomGraphNode.tsx, SbomDetailPanel.tsx
Dockerfile              Multi-stage: node build → python runtime
docker-compose.yml      app + postgres
init.sql                Canonical DDL, mounted into postgres init hook
```

## Backend conventions

- **Repository pattern.** All DB queries go through static methods in
  `repositories/` classes. They take a `db: Session` parameter. Don't
  write raw queries in endpoints or the cron.
- **Service singletons.** `github_service` and `scanner_service` are
  module-level singletons — import them, don't instantiate.
- **Endpoints return plain dicts**, not Pydantic models. Schemas exist
  but aren't used as `response_model` (except for `HealthResponse`).
- **Cron job is synchronous** (`def daily_batch_scan_job()`). It runs
  in a thread via `run_in_executor` when triggered from the async
  lifespan; APScheduler also calls it directly on schedule.
- **DB sessions in cron.** The cron creates its own `SessionLocal()`
  and closes it in a `finally` block. It does NOT use `get_db()` —
  that's a FastAPI dependency.
- **`sys.path` manipulation.** Both `main.py` and `scanner_service.py`
  do `sys.path.insert(0, ...)` to import the `actionbom` core library
  from the parent directory.

## Frontend conventions

- **API calls** all live in `lib/api.ts`. All URLs use the relative
  `/api` prefix — works in dev (Vite proxies to `:8000`) and production
  (same origin).
- **Data fetching:** TanStack React Query v5. Query keys follow the
  pattern `["repositories", search, pod, subpod, page]`,
  `["workflows", repoId]`, `["workflow", workflowId]`.
- **Routing:** React Router v7 with `BrowserRouter`. All routes inside
  a `Layout` wrapper.
- **Styling:** Tailwind CSS 3.4 with dark mode (class strategy). Custom
  CSS animations in `index.css`. Utility: `cn()` from `lib/utils.ts`
  (`clsx` + `tailwind-merge`).
- **Types:** All API response types in `types/api.ts` — keep in sync
  when changing endpoint response shapes.
- **Path alias:** `@` maps to `./src`.

## Actionbom core library

- **Entry point for backend:** `from actionbom.api import full_scan` →
  returns `(sbom_dict, vulns_dict)`.
- **Re-scan existing SBOM:** `from actionbom.vulns.scanner import
  scan_vulnerabilities` → takes a CycloneDX dict, returns a vulns dict.
- `full_scan()` writes the workflow to a temp file, builds the graph
  via DFS, serializes to CycloneDX JSON, then scans with OSV.dev.
- Graph builder does cycle detection, deduplication by node ID, and
  respects `max_depth=10`.

## Database

Everything lives in the **`actionbom` schema**. The `init.sql` at the
repo root is the canonical DDL — Postgres runs it automatically on
first boot (mounted at `/docker-entrypoint-initdb.d/init.sql` via
`docker-compose.yml`). The app's `init_db()` also runs on every startup
and is idempotent, so users running against their own Postgres don't
have to remember to apply `init.sql` first.

### `actionbom.repositories`

The inventory of repos to scan. Populated by:
- **Auto-import on boot** when `TARGET_ORG` is set and the table is empty
- **The dashboard's welcome card** (POST `/api/repositories/import`)
- **The CLI** (`python -m app.import_repos --org <org>`)
- **Manual `INSERT`s** for exotic cases

Columns: `id`, `provider`, `org`, `name`, `is_public`, `pod`, `subpod`.
`pod`/`subpod` are optional grouping labels — leave NULL if unused, or
repurpose (team, environment, business unit). The UI hides the filters
when both columns are all NULL.

Unique constraint: `(provider, org, name)`.

### `actionbom.workflows`

One row per workflow scan. Key columns:

- **PK:** `workflow_id` (auto-increment)
- **FK:** `repo_id` → `actionbom.repositories.id` (enforced)
- **Unique:** `(repo_name, workflow_path, commit_sha)`
- **JSONB:** `sbom_json`, `vulns_json`, `sarif_result`
- **Commit metadata:**
  - `commit_sha` — file blob SHA from GitHub's contents API (dedup key)
  - `last_commit_sha` — real git commit SHA from the commits API
  - `last_commit_author` — GitHub login, or git author name as fallback
- **Status:** `"completed"` or `"failed"`

### `actionbom.org_actions`

Denormalized inventory of third-party actions used across the org. One
row per `(repo_name, workflow_path, action_name, action_version)`.
`vulnerabilities` is JSONB (or NULL when no findings). Wiped and
reinserted per workflow on every scan via
`OrgActionRepository.replace_actions_for_workflow()` — no history.

Third-party only: `_extract_actions_from_scan` filters out components
without a purl (the workflow root and local actions) and components
owned by `TARGET_ORG`. First-party actions won't appear here.

### `actionbom.repo_scan_log`

One row per repo (`repo_id` PK + `last_attempted`). Records when the
cron last visited the repo, **regardless of whether workflows were
found**. This drives batch ordering — without it, repos with no
`.github/workflows/` directory would livelock the queue (no Workflow
row → NULL `scan_date` → always at top of NULL-FIRST sort). The cron
upserts via `RepositoryRepository.touch_scan_log()` at the end of every
per-repo iteration.

### `actionbom.sca_alerts_sent`

Dedup for Slack alerts. One row per `(action_name, advisory_id)` pair
ever alerted on. Only CRITICAL findings are recorded. Prevents
re-firing an alert when a known-critical action shows up in another
workflow during normal cron rotation.

### JSONB query patterns

Vuln counts:

```python
Workflow.vulns_json['total_vulnerabilities'].astext.cast(Integer)
```

SARIF finding counts:

```python
func.jsonb_array_length(Workflow.sarif_result['runs'][0]['results'])
```

For `org_actions.vulnerabilities`, use the `_has_vulns_condition()`
helper. It case-wraps `jsonb_typeof = 'array'` so non-array JSON
values don't crash `jsonb_array_length`.

## Cron job flow

```
daily_batch_scan_job()
  │
  ├─ Check GitHub rate limit (abort if < RATE_LIMIT_THRESHOLD)
  ├─ SELECT repos ORDER BY repo_scan_log.last_attempted ASC NULLS FIRST LIMIT BATCH_SIZE
  │   (NOT MAX(workflow.scan_date) — see RepoScanLog notes above)
  │
  └─ FOR each repo:
       ├─ Rate limit check (stop batch if low — last_attempted NOT updated for skipped
       │   repos, so they stay at top of next batch)
       ├─ GET /repos/{owner}/{repo} → extract default_branch (1 API call)
       ├─ GET .github/workflows/*.yml listing (using default_branch as ref)
       │
       ├─ IF no workflow files:
       │     touch_scan_log(repo_id) + commit + continue
       │
       ├─ FOR each workflow file:
       │     ├─ GET file content + SHA (using default_branch as ref)
       │     ├─ DB lookup: previous scan for this (repo_name, workflow_path)
       │     │
       │     ├─ SHA unchanged + sbom cached?
       │     │   YES → scan_vulnerabilities(cached_sbom) → UPDATE row (vulns_json, scan_date)
       │     │         + backfill last_commit_sha/author if NULL
       │     │   NO  → full_scan() → SBOM + vulns
       │     │         zizmor CLI → SARIF
       │     │         get_latest_commit_for_file() → author + git SHA (1 extra API call)
       │     │         INSERT new Workflow row
       │     │
       │     ├─ _extract_actions_from_scan() → keep only third-party
       │     │   (purl starts with pkg:github/ or pkg:docker/, AND owner != TARGET_ORG)
       │     ├─ OrgActionRepository.replace_actions_for_workflow() (delete + insert)
       │     └─ Track stats + dispatch Slack alerts for new CRITICAL findings
       │
       └─ touch_scan_log(repo_id) + commit
```

**Rotation.** Orders by `last_attempted ASC NULLS FIRST`. Repos never
visited come first, then oldest-visited. After the queue saturates, all
repos have a `last_attempted` and the queue rotates evenly.

**Branch handling.** The cron fetches each repo's actual default branch
via `github_service.get_default_branch()` (`GET /repos/{owner}/{repo}`).
This branch is used consistently for listing workflows, fetching
content, and storing in the DB. Only the default branch is scanned —
workflows on feature branches are transient and not the canonical CI
config. Costs 1 extra API call per repo but prevents 404s from branch
mismatches (e.g., listing from `main` but fetching from `master`).

## Static file serving

In `main.py`:

1. API router registered first at `/api` prefix.
2. If `static/` dir exists (Docker build): mount `/assets` as
   `StaticFiles`, then a catch-all `/{path}` serves `index.html`.
3. If no `static/` dir (local dev): JSON root endpoint at `/`.

The catch-all enables SPA client-side routing — e.g., `/repo/5` serves
`index.html` and React Router handles the route.

## How to add a new API endpoint

1. Add route in `backend/app/api/endpoints.py` on the `router`.
2. If new DB query needed: add a static method to the appropriate
   `repositories/` class.
3. If new response shape: update Pydantic schema in `schemas.py`
   (optional — most endpoints return raw dicts).
4. Update frontend `lib/api.ts` with a new fetch function.
5. Add TypeScript types in `types/api.ts`.
6. Add a React Query hook in the consuming page/component.

## How to add a new frontend page

1. Create the page component in `frontend/src/pages/`.
2. Add a route in `App.tsx` inside the `<Route element={<Layout />}>` wrapper.
3. Add a navigation link from existing pages.
4. Use `useQuery` from React Query for data fetching.

## How to modify the cron job

- Function is in `backend/app/cron/workflow_scanner.py`.
- Synchronous — runs in a thread on startup, directly by APScheduler on
  schedule.
- Uses its own DB session (`SessionLocal()`), not the FastAPI dependency.
- GitHub API calls go through `github_service` singleton.
- Scanning goes through `scanner_service` singleton.
- Batch selection is in `RepositoryRepository.get_batch_for_scanning()`.

## Gotchas

- **Two different "commit SHAs" on `actionbom.workflows`.** `commit_sha`
  is the file blob SHA from GitHub's contents API (changes whenever
  file content changes — used as the dedup key). `last_commit_sha` is
  the real git commit SHA from the commits API (the commit that last
  touched the file — shown in the workflow detail page). Don't
  conflate them.

- **Batch query orders on `repo_scan_log.last_attempted`, NOT
  `workflow.scan_date`.** `scan_date` only exists for repos that have
  at least one Workflow row, which excludes any repo without a
  `.github/workflows/` directory. Using `MAX(scan_date)` for ordering
  would livelock the queue on those NULL-scan empty repos forever. The
  cron must `touch_scan_log()` on every per-repo iteration (not just
  successful scans) for rotation to work.

- **`org_actions` is third-party only.** `_extract_actions_from_scan`
  filters out components without a purl (workflow root + local actions)
  and components owned by `settings.TARGET_ORG`. First-party actions
  from your own org won't appear in the inventory.

- **Zizmor returns non-zero exit codes when findings exist**, not just
  on errors. The scanner parses stdout regardless of return code.

- **Zizmor binary install.** The Dockerfile downloads the `.tar.gz`
  release archive (not a raw binary), extracts the `zizmor` binary
  into `/usr/local/bin`, and runs `--version` as a build-time sanity
  check. Architecture is auto-detected via `uname -m` so the same
  Dockerfile works on x86_64 and aarch64. Uses `curl -fsSL` (not
  `-sSL`) so HTTP 4xx fails the build instead of silently saving 404 HTML.

- **The `unique_workflow` constraint** `(repo_name, workflow_path,
  commit_sha)` means you can't insert two scans of the same file at
  the same blob SHA. The SCA-only re-scan path UPDATEs the existing
  row instead.

- **Frontend uses `sessionStorage`** to track if the pipeline loader
  animation has been shown (only shows on first visit per tab). It's
  also skipped on empty installs so first-time users land on the
  welcome card immediately.

- **Branch is dynamic, not hardcoded.** `get_default_branch()` resolves
  each repo's actual default branch. The `branch` column in
  `actionbom.workflows` stores the real value (could be `main`,
  `master`, `develop`, etc.). Never hardcode `"master"` in cron or
  service calls.
