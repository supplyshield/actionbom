"""API endpoint definitions."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HealthResponse
from app.repositories.repository_repo import RepositoryRepository
from app.repositories.workflow_repo import WorkflowRepository
from app.repositories.org_action_repo import OrgActionRepository
from app.services.repo_importer import import_org_repos

router = APIRouter()


class ImportOrgRequest(BaseModel):
    org: str = Field(..., min_length=1, description="GitHub organization login")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow()
    }


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ActionBOM Workflow Scanner API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "docs": "/docs"
        }
    }


@router.get("/repositories/filters")
async def get_repository_filters(
    provider: str = "github.com",
    db: Session = Depends(get_db)
):
    """Get available filter values for pod and subpod dropdowns."""
    return {
        "pods": RepositoryRepository.get_distinct_pods(db, provider),
        "subpods": RepositoryRepository.get_distinct_subpods(db, provider),
    }


@router.post("/repositories/import")
async def import_repositories(
    payload: ImportOrgRequest,
    db: Session = Depends(get_db)
):
    """Bulk-import repositories from a GitHub org.

    Uses the app's configured GITHUB_TOKEN. Idempotent — already-tracked
    repos are skipped (existing rows and any manual pod/subpod
    annotations are preserved). Blocks until the org's repo list has
    been fully paginated from GitHub (~100 repos/sec).
    """
    org = payload.org.strip()
    if not org:
        raise HTTPException(status_code=400, detail="`org` must be non-empty")

    try:
        result = import_org_repos(db, org)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")

    return {
        "org": org,
        "fetched": result["fetched"],
        "inserted": result["inserted"],
    }


@router.get("/repositories")
async def get_repositories(
    provider: str = "github.com",
    skip: int = 0,
    limit: int = 24,
    search: Optional[str] = Query(None),
    pod: Optional[str] = Query(None),
    subpod: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get repositories with at least 1 scanned workflow, with filtering and pagination.
    """
    results = RepositoryRepository.get_all_with_stats(
        db, provider, skip, limit,
        search=search, pod=pod, subpod=subpod
    )
    total = RepositoryRepository.count_with_workflows(
        db, provider,
        search=search, pod=pod, subpod=subpod
    )

    repositories = []
    for repo, wf_count, last_scan in results:
        repositories.append({
            "id": repo.id,
            "org": repo.org,
            "name": repo.name,
            "provider": repo.provider,
            "pod": repo.pod,
            "subpod": repo.subpod,
            "is_public": repo.is_public,
            "workflow_count": wf_count or 0,
            "last_scan": last_scan.isoformat() if last_scan else None
        })

    return {
        "total": total,
        "total_tracked": RepositoryRepository.count(db, provider),
        "count": len(repositories),
        "skip": skip,
        "limit": limit,
        "repositories": repositories
    }


@router.get("/workflows/{repo_id}")
async def get_workflows(
    repo_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all workflows for a specific repository.
    
    Path Parameters:
        repo_id: Repository ID from actionbom.repositories
    
    Returns:
        JSON with repository info and list of workflows with stats
    """
    
    # Get repository info
    repo = RepositoryRepository.get_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository with ID {repo_id} not found")
    
    # Get workflows with stats
    results = WorkflowRepository.get_by_repo_id(db, repo_id) # need to return only the latest scan date one 
    
    # Format response
    workflows = []
    for wf, vuln_count, sarif_count in results:
        workflows.append({
            "workflow_id": wf.workflow_id,
            "workflow_name": wf.workflow_name,
            "workflow_path": wf.workflow_path,
            "branch": wf.branch,
            "commit_sha": wf.commit_sha[:8] if wf.commit_sha else None,
            "scan_date": wf.scan_date.isoformat() if wf.scan_date else None,
            "started_at": wf.started_at.isoformat() if wf.started_at else None,
            "ended_at": wf.ended_at.isoformat() if wf.ended_at else None,
            "status": wf.status,
            "vulnerability_count": vuln_count,
            "sarif_findings": sarif_count,
            "error_message": wf.error_message if wf.error_message else None
        })
    
    return {
        "repository": {
            "id": repo.id,
            "org": repo.org,
            "name": repo.name,
            "full_name": f"{repo.org}/{repo.name}",
            "provider": repo.provider,
            "pod": repo.pod,
            "subpod": repo.subpod
        },
        "total_workflows": len(workflows),
        "workflows": workflows
    }



@router.get("/workflow/{workflow_id}")
async def get_workflow_details(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Get complete details of a specific workflow including all scan results.
    
    Path Parameters:
        workflow_id: Workflow ID from actionbom.workflows
    
    Returns:
        JSON with complete workflow details, SBOM, vulnerabilities, and SARIF results
    """
    
    # Get workflow
    workflow = WorkflowRepository.get_by_id(db, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    # Get repository info
    repo = RepositoryRepository.get_by_id(db, workflow.repo_id)
    
    # Calculate scan duration
    scan_duration = None
    if workflow.started_at and workflow.ended_at:
        duration_seconds = (workflow.ended_at - workflow.started_at).total_seconds()
        scan_duration = f"{duration_seconds:.2f}s"
    
    # Transform vulns_json into the shape the frontend expects
    vulns_transformed = None
    if workflow.vulns_json:
        raw = workflow.vulns_json
        flat_findings = []
        for finding in raw.get("findings", []):
            comp = finding.get("component", {})
            action_name = comp.get("name", "")
            action_version = comp.get("version", "")
            for v in finding.get("vulnerabilities", []):
                # Extract affected range and fixed version from the first affected entry
                affected_range = None
                fixed_version = None
                for aff in v.get("affected", []):
                    for rng in aff.get("ranges", []):
                        events = rng.get("events", [])
                        introduced = next((e.get("introduced") for e in events if "introduced" in e), None)
                        fixed = next((e.get("fixed") for e in events if "fixed" in e), None)
                        if introduced:
                            affected_range = f">= {introduced}" + (f", < {fixed}" if fixed else "")
                        if fixed and not fixed_version:
                            fixed_version = fixed

                # Pick first reference URL
                refs = v.get("references", [])
                reference_url = refs[0]["url"] if refs else None

                flat_findings.append({
                    "action": action_name,
                    "version": action_version,
                    "advisory_id": v.get("id", ""),
                    "severity": v.get("database_specific", {}).get("severity", "UNKNOWN"),
                    "summary": v.get("summary", ""),
                    "aliases": v.get("aliases", []),
                    "affected_range": affected_range,
                    "fixed_version": fixed_version,
                    "reference_url": reference_url,
                })

        vulns_transformed = {
            "total_vulnerabilities": raw.get("total_vulnerabilities", 0),
            "severity_counts": raw.get("summary", {}),
            "scanned_actions": raw.get("components_scanned", 0),
            "vulnerable_actions": raw.get("vulnerable_components", 0),
            "findings": flat_findings,
        }

    # Build response
    return {
        "workflow_id": workflow.workflow_id,
        "repository": {
            "id": repo.id if repo else None,
            "org": repo.org if repo else None,
            "name": repo.name if repo else None,
            "full_name": f"{repo.org}/{repo.name}" if repo else workflow.repo_name
        },
        "workflow_info": {
            "name": workflow.workflow_name,
            "path": workflow.workflow_path,
            "branch": workflow.branch,
            "commit_sha": workflow.commit_sha,
            "repo_name": workflow.repo_name
        },
        "scan_info": {
            "scan_date": workflow.scan_date.isoformat() if workflow.scan_date else None,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "ended_at": workflow.ended_at.isoformat() if workflow.ended_at else None,
            "duration": scan_duration,
            "status": workflow.status,
            "error_message": workflow.error_message
        },
        "commit_info": {
            "sha": workflow.last_commit_sha,
            "author": workflow.last_commit_author,
        },
        "results": {
            "sbom": workflow.sbom_json,
            "vulnerabilities": vulns_transformed,
            "sarif": workflow.sarif_result
        }
    }


@router.get("/actions")
async def get_actions_inventory(
    search: Optional[str] = Query(None),
    vulnerable_only: bool = Query(False),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all unique actions used across the org with aggregate stats."""
    actions, total = OrgActionRepository.get_all_actions_summary(
        db,
        search=search,
        vulnerable_only=vulnerable_only,
        skip=skip,
        limit=limit,
    )
    return {
        "total": total,
        "count": len(actions),
        "skip": skip,
        "limit": limit,
        "actions": actions,
    }


@router.get("/actions/{action_name:path}")
async def get_action_detail(
    action_name: str,
    db: Session = Depends(get_db)
):
    """Get full detail for a specific action: versions, workflows, vulnerabilities."""
    detail = OrgActionRepository.get_action_detail(db, action_name)
    if not detail["workflows"]:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")
    return detail
