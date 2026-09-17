"""Manual repository import CLI.

Usage:
    python -m app.import_repos --org actions
    docker compose exec app python -m app.import_repos --org your-org

The startup bootstrap in main.py only runs once (when the table is
empty). Use this command to pull in newly-created repos afterwards,
or to import from an org other than TARGET_ORG.
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal, init_db
from app.services.repo_importer import import_org_repos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.import_repos",
        description="Import a GitHub org's repositories into the actionbom database.",
    )
    parser.add_argument(
        "--org",
        required=True,
        help="GitHub organization login (e.g. 'actions')",
    )
    args = parser.parse_args(argv)

    # Ensure schema + tables exist before we try to insert into them
    init_db()

    db = SessionLocal()
    try:
        result = import_org_repos(db, args.org)
        print(f"✓ Imported {result['inserted']} new repos "
              f"(fetched {result['fetched']} from GitHub, "
              f"skipped {result['fetched'] - result['inserted']} already-tracked)")
        return 0
    except Exception as e:
        print(f"❌ Import failed: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
