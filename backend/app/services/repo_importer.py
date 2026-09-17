"""Bulk-import repositories from a GitHub organization.

Runs on startup (via main.py lifespan) when TARGET_ORG is set and the
repositories table is empty, and is also callable as a CLI for manual
re-syncs (see app/import_repos.py).
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Repository
from app.services.github_service import github_service


def import_org_repos(db: Session, org: str) -> Dict[str, int]:
    """List every repo in `org` via the GitHub API and upsert into the
    repositories table.

    Idempotent: rerunning inserts only repos we haven't seen before,
    leaving existing rows (and any manual `pod`/`subpod` annotations)
    untouched. Archived and disabled repos are skipped — they're not
    interesting to scan and would just clog the batch queue.

    Args:
        db: SQLAlchemy session
        org: GitHub organization login (e.g. "actions")

    Returns:
        {"fetched": N, "inserted": M} — N total repos returned by the
        API (after filtering archived/disabled), M newly inserted rows.
    """
    api_repos: List[Dict] = github_service.list_org_repos(org)
    if not api_repos:
        return {"fetched": 0, "inserted": 0}

    rows = [
        {
            "provider": "github.com",
            "org": org,
            "name": r["name"],
            "is_public": not r.get("private", True),
            # pod / subpod intentionally NULL — user can annotate later
        }
        for r in api_repos
        if not r.get("archived") and not r.get("disabled")
    ]

    if not rows:
        return {"fetched": 0, "inserted": 0}

    stmt = pg_insert(Repository).values(rows).on_conflict_do_nothing(
        index_elements=["provider", "org", "name"]
    )
    result = db.execute(stmt)
    db.commit()

    return {"fetched": len(rows), "inserted": result.rowcount or 0}
