"""SQLAlchemy database models.

All tables live in the `actionbom` schema. The Repository table was
previously read-only in an external `libinv` schema — it's now owned by
this app and populated either by the auto-import at startup or by a
manual SQL/API call.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, UniqueConstraint, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Repository(Base):
    """Repositories to scan. Populated by the org-import on first boot,
    or by manual INSERT / the import endpoint.

    `pod` / `subpod` are optional generic grouping labels — leave NULL if
    unused, or repurpose them (team, environment, business unit, etc).
    The UI hides both filters when their columns are all NULL.
    """

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(200), nullable=False)  # e.g., "github.com"
    org = Column(String(200), nullable=False, index=True)
    name = Column(String(200), nullable=False)  # repo name
    is_public = Column(Boolean)
    pod = Column(String(200), index=True)
    subpod = Column(String(200))

    # Relationship
    workflows = relationship("Workflow", back_populates="repository")

    __table_args__ = (
        UniqueConstraint('provider', 'org', 'name', name='unique_repository'),
        {'schema': 'actionbom'}
    )


class Workflow(Base):
    """Workflow scan results."""

    __tablename__ = "workflows"

    workflow_id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey('actionbom.repositories.id'), nullable=False, index=True)
    repo_name = Column(String(512), nullable=False, index=True)
    workflow_path = Column(String(512), nullable=False, index=True)
    workflow_name = Column(String(255))
    commit_sha = Column(String(40))
    branch = Column(String(100), default="main")

    # Scan metadata
    scan_date = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    started_at = Column(TIMESTAMP)
    ended_at = Column(TIMESTAMP)

    # Results
    sbom_json = Column(JSONB)
    vulns_json = Column(JSONB)
    sarif_result = Column(JSONB)

    # Status
    status = Column(String(50), default="completed", index=True)
    error_message = Column(Text)

    # Last commit that touched this workflow file (populated by cron)
    last_commit_sha = Column(String(40))
    last_commit_author = Column(String(255))

    # Relationships
    repository = relationship("Repository", back_populates="workflows")
    org_actions = relationship("OrgAction", back_populates="workflow")

    __table_args__ = (
        UniqueConstraint('repo_name', 'workflow_path', 'commit_sha', name='unique_workflow'),
        {'schema': 'actionbom'}
    )


class OrgAction(Base):
    """Tracks individual GitHub Actions used across the org."""

    __tablename__ = "org_actions"

    action_id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey('actionbom.workflows.workflow_id'), nullable=False, index=True)
    repo_name = Column(String(512), nullable=False, index=True)
    workflow_path = Column(String(512), nullable=False)
    action_name = Column(String(512), nullable=False, index=True)
    action_version = Column(String(255))
    vulnerabilities = Column(JSONB)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationship
    workflow = relationship("Workflow", back_populates="org_actions")

    __table_args__ = (
        UniqueConstraint('repo_name', 'workflow_path', 'action_name', 'action_version',
                         name='unique_org_action'),
        {'schema': 'actionbom'}
    )


class RepoScanLog(Base):
    """One row per repo recording when the cron last visited it.

    Independent of actionbom.workflows — repos with no .github/workflows directory
    still get a row here, so the batch query can rotate evenly through all repos
    instead of livelocking on the NULL-last_scan bucket.
    """

    __tablename__ = "repo_scan_log"

    repo_id = Column(Integer, primary_key=True)
    last_attempted = Column(TIMESTAMP, nullable=False)

    __table_args__ = {'schema': 'actionbom'}


class ScaAlertSent(Base):
    """Dedup: one row per (action_name, advisory_id) ever alerted on.

    Prevents re-firing a Slack alert when a known-CRITICAL action+advisory
    pair shows up in another workflow during normal cron rotation. Only
    CRITICAL severity pairs are inserted — non-critical findings are
    filtered out before this table is touched.
    """

    __tablename__ = "sca_alerts_sent"

    action_name = Column(String(512), primary_key=True)
    advisory_id = Column(String(64), primary_key=True)
    first_alerted_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = {'schema': 'actionbom'}
