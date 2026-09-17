"""Workflow database operations."""
from typing import List, Optional, Tuple
from sqlalchemy import func, cast, Integer
from sqlalchemy.orm import Session

from app.models import Workflow


class WorkflowRepository:
    """Data access layer for Workflow operations."""
    
    @staticmethod
    def get_by_repo_id(db: Session, repo_id: int) -> List[Tuple]:
        """
        Get the latest scan per workflow_path for a repository, with summary stats.

        Uses a subquery to find the max scan_date per workflow_path,
        then joins back to get the full row.

        Args:
            db: Database session
            repo_id: Repository ID from actionbom.repositories

        Returns:
            List of (Workflow, vuln_count, sarif_count) tuples — one per unique workflow_path
        """
        # Subquery: latest scan_date per workflow_path for this repo
        latest_subq = db.query(
            Workflow.workflow_path,
            func.max(Workflow.scan_date).label('latest_scan')
        ).filter_by(
            repo_id=repo_id
        ).group_by(
            Workflow.workflow_path
        ).subquery()

        return db.query(
            Workflow,
            func.coalesce(
                func.cast(
                    Workflow.vulns_json['total_vulnerabilities'].astext,
                    Integer
                ),
                0
            ).label('vuln_count'),
            func.coalesce(
                func.jsonb_array_length(
                    Workflow.sarif_result['runs'][0]['results']
                ),
                0
            ).label('sarif_count')
        ).join(
            latest_subq,
            (Workflow.workflow_path == latest_subq.c.workflow_path) &
            (Workflow.scan_date == latest_subq.c.latest_scan)
        ).filter(
            Workflow.repo_id == repo_id
        ).order_by(
            Workflow.scan_date.desc()
        ).all()
    
    @staticmethod
    def count_by_repo_id(db: Session, repo_id: int) -> int:
        """
        Count total workflows for a repository.
        
        Args:
            db: Database session
            repo_id: Repository ID
        
        Returns:
            Total number of workflows
        """
        return db.query(Workflow).filter_by(repo_id=repo_id).count()
    
    @staticmethod
    def get_by_id(db: Session, workflow_id: int) -> Optional[Workflow]:
        """
        Get workflow by ID.
        
        Args:
            db: Database session
            workflow_id: Workflow ID from actionbom.workflows
        
        Returns:
            Workflow object or None
        """
        return db.query(Workflow).filter_by(workflow_id=workflow_id).first()

    @staticmethod
    def get_latest_scan_for_workflow(
        db: Session,
        repo_name: str,
        workflow_path: str
    ) -> Optional[Workflow]:
        """
        Get the most recent scan for a specific workflow file.
        Used for dedup (compare commit_sha) and SBOM reuse.

        Returns:
            Latest Workflow row or None if never scanned.
        """
        return db.query(Workflow).filter_by(
            repo_name=repo_name,
            workflow_path=workflow_path
        ).order_by(
            Workflow.scan_date.desc()
        ).first()
