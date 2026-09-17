"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class WorkflowBase(BaseModel):
    """Base workflow schema."""
    repo_id: int
    repo_name: str
    workflow_path: str
    workflow_name: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: str = "master"


class WorkflowCreate(WorkflowBase):
    """Schema for creating a workflow."""
    sbom_json: Optional[Dict[str, Any]] = None
    vulns_json: Optional[Dict[str, Any]] = None
    sarif_result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: str = "completed"
    error_message: Optional[str] = None


class WorkflowResponse(WorkflowBase):
    """Schema for workflow response."""
    workflow_id: int
    scan_date: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    sbom_json: Optional[Dict[str, Any]] = None
    vulns_json: Optional[Dict[str, Any]] = None
    sarif_result: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class RepositoryBase(BaseModel):
    """Base repository schema."""
    provider: str
    org: str
    name: str
    is_public: Optional[bool] = None
    pod: str
    subpod: str


class RepositoryResponse(RepositoryBase):
    """Schema for repository response."""
    id: int
    
    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
