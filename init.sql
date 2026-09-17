-- ActionBOM database initialization
--
-- Automatically executed by Postgres on first container boot when this
-- file is mounted at /docker-entrypoint-initdb.d/init.sql (see
-- docker-compose.yml). Also runnable by hand against an existing
-- Postgres: `psql "$DATABASE_URL" -f init.sql`.
--
-- Fully idempotent: safe to re-run against an existing database.

CREATE SCHEMA IF NOT EXISTS actionbom;

-- ─── repositories ───────────────────────────────────────────────────
-- The inventory of repos to scan. On first boot the app auto-imports
-- from GitHub if TARGET_ORG is set; otherwise seed manually via SQL or
-- the /api/repositories/import endpoint.
CREATE TABLE IF NOT EXISTS actionbom.repositories (
    id          SERIAL PRIMARY KEY,
    provider    VARCHAR(200) NOT NULL,          -- e.g. 'github.com'
    org         VARCHAR(200) NOT NULL,
    name        VARCHAR(200) NOT NULL,
    is_public   BOOLEAN,
    pod         VARCHAR(200),                    -- optional grouping label
    subpod      VARCHAR(200),                    -- optional grouping label
    CONSTRAINT unique_repository UNIQUE (provider, org, name)
);
CREATE INDEX IF NOT EXISTS idx_repositories_org ON actionbom.repositories(org);
CREATE INDEX IF NOT EXISTS idx_repositories_pod ON actionbom.repositories(pod);


-- ─── workflows ──────────────────────────────────────────────────────
-- One row per workflow scan. See CLAUDE.md for the two-SHA distinction
-- between `commit_sha` (file blob SHA, dedup key) and `last_commit_sha`
-- (real git commit SHA of the commit that last touched this file).
CREATE TABLE IF NOT EXISTS actionbom.workflows (
    workflow_id         SERIAL PRIMARY KEY,
    repo_id             INTEGER NOT NULL REFERENCES actionbom.repositories(id),
    repo_name           VARCHAR(512) NOT NULL,
    workflow_path       VARCHAR(512) NOT NULL,
    workflow_name       VARCHAR(255),
    commit_sha          VARCHAR(40),
    branch              VARCHAR(100) DEFAULT 'main',

    -- Scan metadata
    scan_date           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at          TIMESTAMP,
    ended_at            TIMESTAMP,

    -- Results (JSONB for flexibility)
    sbom_json           JSONB,
    vulns_json          JSONB,
    sarif_result        JSONB,

    -- Status
    status              VARCHAR(50) DEFAULT 'completed',
    error_message       TEXT,

    -- Real git commit that last touched this file
    last_commit_sha     VARCHAR(40),
    last_commit_author  VARCHAR(255),

    CONSTRAINT unique_workflow UNIQUE (repo_name, workflow_path, commit_sha)
);
CREATE INDEX IF NOT EXISTS idx_workflows_repo_id       ON actionbom.workflows(repo_id);
CREATE INDEX IF NOT EXISTS idx_workflows_repo_name     ON actionbom.workflows(repo_name);
CREATE INDEX IF NOT EXISTS idx_workflows_workflow_path ON actionbom.workflows(workflow_path);
CREATE INDEX IF NOT EXISTS idx_workflows_scan_date     ON actionbom.workflows(scan_date);
CREATE INDEX IF NOT EXISTS idx_workflows_status        ON actionbom.workflows(status);


-- ─── org_actions ────────────────────────────────────────────────────
-- Denormalized inventory of third-party actions used across the org.
-- Wiped + reinserted per workflow on every scan (see
-- OrgActionRepository.replace_actions_for_workflow). No history.
CREATE TABLE IF NOT EXISTS actionbom.org_actions (
    action_id       SERIAL PRIMARY KEY,
    workflow_id     INTEGER NOT NULL REFERENCES actionbom.workflows(workflow_id),
    repo_name       VARCHAR(512) NOT NULL,
    workflow_path   VARCHAR(512) NOT NULL,
    action_name     VARCHAR(512) NOT NULL,
    action_version  VARCHAR(255),
    vulnerabilities JSONB,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_org_action UNIQUE (repo_name, workflow_path, action_name, action_version)
);
CREATE INDEX IF NOT EXISTS idx_org_actions_workflow_id ON actionbom.org_actions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_org_actions_repo_name   ON actionbom.org_actions(repo_name);
CREATE INDEX IF NOT EXISTS idx_org_actions_action_name ON actionbom.org_actions(action_name);


-- ─── repo_scan_log ──────────────────────────────────────────────────
-- One row per repo recording when the cron last visited it. Drives the
-- batch selection ordering (last_attempted ASC NULLS FIRST). Repos with
-- no workflows still get a row so the queue rotates evenly instead of
-- livelocking on the NULL bucket.
CREATE TABLE IF NOT EXISTS actionbom.repo_scan_log (
    repo_id        INTEGER PRIMARY KEY,
    last_attempted TIMESTAMP NOT NULL
);


-- ─── sca_alerts_sent ────────────────────────────────────────────────
-- Dedup for Slack alerts: one row per (action, advisory) pair ever
-- alerted on. Only CRITICAL severity findings are recorded here.
CREATE TABLE IF NOT EXISTS actionbom.sca_alerts_sent (
    action_name       VARCHAR(512) NOT NULL,
    advisory_id       VARCHAR(64)  NOT NULL,
    first_alerted_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (action_name, advisory_id)
);
