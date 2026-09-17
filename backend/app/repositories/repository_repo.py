"""Repository database operations."""
from datetime import datetime
from typing import List, Tuple, Optional
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Repository, Workflow, RepoScanLog


class RepositoryRepository:
    """Data access layer for Repository operations."""
    
    @staticmethod
    def get_all_with_stats(
        db: Session,
        provider: str = "github.com",
        skip: int = 0,
        limit: int = 100,
        search: str = None,
        pod: str = None,
        subpod: str = None
    ) -> List[Tuple]:
        """Get repositories that have at least 1 scanned workflow, with stats.

        Repos with no scanned workflows are hidden — they carry no useful
        signal until the cron produces at least one workflow row. Ordering
        is most-recently-scanned first.
        """
        query = db.query(
            Repository,
            func.count(Workflow.workflow_id).label('workflow_count'),
            func.max(Workflow.scan_date).label('last_scan')
        ).outerjoin(
            Workflow,
            Repository.id == Workflow.repo_id
        ).filter(
            Repository.provider == provider
        )

        if search:
            query = query.filter(Repository.name.ilike(f"%{search}%"))
        if pod:
            query = query.filter(Repository.pod == pod)
        if subpod:
            query = query.filter(Repository.subpod == subpod)

        return query.group_by(
            Repository.id
        ).having(
            func.count(Workflow.workflow_id) > 0
        ).order_by(
            func.max(Workflow.scan_date).desc(),
            Repository.name
        ).offset(skip).limit(limit).all()

    @staticmethod
    def count_with_workflows(
        db: Session,
        provider: str = "github.com",
        search: str = None,
        pod: str = None,
        subpod: str = None
    ) -> int:
        """Count repositories that have at least 1 scanned workflow, with filters."""
        query = db.query(
            Repository.id
        ).outerjoin(
            Workflow,
            Repository.id == Workflow.repo_id
        ).filter(
            Repository.provider == provider
        )

        if search:
            query = query.filter(Repository.name.ilike(f"%{search}%"))
        if pod:
            query = query.filter(Repository.pod == pod)
        if subpod:
            query = query.filter(Repository.subpod == subpod)

        return query.group_by(
            Repository.id
        ).having(
            func.count(Workflow.workflow_id) > 0
        ).count()

    @staticmethod
    def get_distinct_pods(db: Session, provider: str = "github.com") -> List[str]:
        """Get distinct pod values for filter dropdown."""
        rows = db.query(Repository.pod).filter(
            Repository.provider == provider,
            Repository.pod.isnot(None),
            Repository.pod != ""
        ).distinct().order_by(Repository.pod).all()
        return [r[0] for r in rows]

    @staticmethod
    def get_distinct_subpods(db: Session, provider: str = "github.com") -> List[str]:
        """Get distinct subpod values for filter dropdown."""
        rows = db.query(Repository.subpod).filter(
            Repository.provider == provider,
            Repository.subpod.isnot(None),
            Repository.subpod != ""
        ).distinct().order_by(Repository.subpod).all()
        return [r[0] for r in rows]
    
    @staticmethod
    def get_by_id(db: Session, repo_id: int) -> Optional[Repository]:
        """
        Get repository by ID.
        
        Args:
            db: Database session
            repo_id: Repository ID
        
        Returns:
            Repository object or None
        """
        return db.query(Repository).filter_by(id=repo_id).first()

    @staticmethod
    def get_batch_for_scanning(
        db: Session,
        batch_size: int,
        provider: str = "github.com"
    ) -> List[Tuple]:
        """
        Get the next batch of repos to scan, prioritizing never-visited
        then oldest-visited.

        Orders on actionbom.repo_scan_log.last_attempted (updated by the cron
        on every repo iteration, regardless of whether workflows were found),
        so empty repos cycle out of the NULL bucket after one visit instead
        of livelocking the queue forever.

        Returns:
            List of (Repository, last_attempted) tuples
        """
        return db.query(
            Repository,
            RepoScanLog.last_attempted
        ).outerjoin(
            RepoScanLog,
            Repository.id == RepoScanLog.repo_id
        ).filter(
            Repository.provider == provider
        ).order_by(
            RepoScanLog.last_attempted.asc().nullsfirst()
        ).limit(batch_size).all()

    @staticmethod
    def touch_scan_log(db: Session, repo_id: int) -> None:
        """Mark this repo as visited by the cron right now (upsert)."""
        now = datetime.utcnow()
        stmt = pg_insert(RepoScanLog).values(
            repo_id=repo_id,
            last_attempted=now,
        ).on_conflict_do_update(
            index_elements=['repo_id'],
            set_={'last_attempted': now},
        )
        db.execute(stmt)

    @staticmethod
    def count(db: Session, provider: str = "github.com") -> int:
        """Total number of tracked repositories for a provider.

        Used by the startup bootstrap to detect an empty inventory before
        auto-importing from GitHub.
        """
        return db.query(Repository).filter(Repository.provider == provider).count()
