"""OrgAction database operations."""
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import func, case, text
from sqlalchemy.orm import Session

from app.models import OrgAction, Workflow


def _has_vulns_condition():
    """Safe check: vulnerabilities column is a non-empty JSON array.
    Uses CASE to protect jsonb_array_length from non-array values."""
    return func.jsonb_array_length(
        case(
            (func.jsonb_typeof(OrgAction.vulnerabilities) == 'array',
             OrgAction.vulnerabilities),
            else_=text("'[]'::jsonb")
        )
    ) > 0


class OrgActionRepository:
    """Data access layer for OrgAction operations."""

    @staticmethod
    def replace_actions_for_workflow(
        db: Session,
        workflow_id: int,
        repo_name: str,
        workflow_path: str,
        actions: List[Dict[str, Any]]
    ):
        """
        Delete existing org_actions for this (repo_name, workflow_path)
        and insert the fresh set.

        Args:
            db: Database session
            workflow_id: Current workflow_id (latest scan)
            repo_name: e.g. "org/repo"
            workflow_path: e.g. ".github/workflows/ci.yml"
            actions: List of dicts with keys: action_name, action_version, vulnerabilities
        """
        # Delete old rows (catches rows from any previous workflow_id)
        db.query(OrgAction).filter_by(
            repo_name=repo_name,
            workflow_path=workflow_path
        ).delete()

        # Insert fresh set
        for action in actions:
            vulns = action.get("vulnerabilities")
            # Ensure we store SQL NULL (not JSON null) when there are no vulns
            if not vulns:
                vulns = None
            db.add(OrgAction(
                workflow_id=workflow_id,
                repo_name=repo_name,
                workflow_path=workflow_path,
                action_name=action["action_name"],
                action_version=action.get("action_version"),
                vulnerabilities=vulns,
                updated_at=datetime.utcnow(),
            ))

    @staticmethod
    def get_all_actions_summary(
        db: Session,
        search: Optional[str] = None,
        vulnerable_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get all unique actions with aggregate stats.
        Returns list of dicts with action_name, version_count, workflow_count,
        repo_count, vulnerable_count.
        """
        vuln_case = case(
            (_has_vulns_condition(), 1),
            else_=0
        )

        query = db.query(
            OrgAction.action_name,
            func.count(func.distinct(OrgAction.action_version)).label("version_count"),
            func.count(func.distinct(OrgAction.workflow_id)).label("workflow_count"),
            func.count(func.distinct(OrgAction.repo_name)).label("repo_count"),
            func.sum(vuln_case).label("vulnerable_count"),
        ).group_by(OrgAction.action_name)

        if search:
            query = query.filter(OrgAction.action_name.ilike(f"%{search}%"))

        if vulnerable_only:
            query = query.having(func.sum(vuln_case) > 0)

        total_query = db.query(func.count(func.distinct(OrgAction.action_name)))
        if search:
            total_query = total_query.filter(OrgAction.action_name.ilike(f"%{search}%"))
        if vulnerable_only:
            # For total count with vulnerable_only, use a subquery
            sub = db.query(OrgAction.action_name).filter(
                _has_vulns_condition()
            ).distinct()
            if search:
                sub = sub.filter(OrgAction.action_name.ilike(f"%{search}%"))
            total = sub.count()
        else:
            total = total_query.scalar()

        rows = query.order_by(
            func.sum(vuln_case).desc(),
            func.count(func.distinct(OrgAction.workflow_id)).desc()
        ).offset(skip).limit(limit).all()

        actions = []
        for row in rows:
            actions.append({
                "action_name": row.action_name,
                "version_count": row.version_count,
                "workflow_count": row.workflow_count,
                "repo_count": row.repo_count,
                "vulnerable_count": row.vulnerable_count or 0,
            })

        return actions, total

    @staticmethod
    def get_action_usage_count(db: Session, action_name: str) -> Dict:
        """Total workflows + repos that use this action (regardless of vuln status)."""
        row = db.query(
            func.count(func.distinct(OrgAction.workflow_id)).label("workflow_count"),
            func.count(func.distinct(OrgAction.repo_name)).label("repo_count"),
        ).filter(OrgAction.action_name == action_name).one()
        return {"workflow_count": row.workflow_count, "repo_count": row.repo_count}

    @staticmethod
    def get_action_detail(
        db: Session,
        action_name: str,
    ) -> Dict:
        """
        Get full detail for a specific action: versions breakdown and
        all workflows using it.
        """
        # Version breakdown
        vuln_case = case(
            (_has_vulns_condition(), 1),
            else_=0
        )

        version_rows = db.query(
            OrgAction.action_version,
            func.count(func.distinct(OrgAction.workflow_id)).label("workflow_count"),
            func.count(func.distinct(OrgAction.repo_name)).label("repo_count"),
            func.sum(vuln_case).label("vulnerable_count"),
        ).filter(
            OrgAction.action_name == action_name
        ).group_by(
            OrgAction.action_version
        ).order_by(
            func.sum(vuln_case).desc(),
            OrgAction.action_version
        ).all()

        versions = []
        for v in version_rows:
            # Get vulns for this version (from any row that has them)
            sample = db.query(OrgAction.vulnerabilities).filter(
                OrgAction.action_name == action_name,
                OrgAction.action_version == v.action_version,
                _has_vulns_condition(),
            ).first()

            versions.append({
                "version": v.action_version,
                "workflow_count": v.workflow_count,
                "repo_count": v.repo_count,
                "vulnerable_count": v.vulnerable_count or 0,
                "vulnerabilities": sample[0] if sample else None,
            })

        # Workflows using this action
        workflow_rows = db.query(
            OrgAction, Workflow
        ).join(
            Workflow, OrgAction.workflow_id == Workflow.workflow_id
        ).filter(
            OrgAction.action_name == action_name
        ).order_by(
            OrgAction.repo_name, OrgAction.workflow_path
        ).all()

        workflows = []
        for oa, wf in workflow_rows:
            workflows.append({
                "workflow_id": wf.workflow_id,
                "repo_name": oa.repo_name,
                "workflow_path": oa.workflow_path,
                "workflow_name": wf.workflow_name,
                "branch": wf.branch,
                "action_version": oa.action_version,
                "vulnerabilities": oa.vulnerabilities,
                "scan_date": wf.scan_date.isoformat() if wf.scan_date else None,
                "status": wf.status,
            })

        return {
            "action_name": action_name,
            "versions": versions,
            "workflows": workflows,
        }
