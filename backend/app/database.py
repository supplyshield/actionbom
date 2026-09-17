"""Database connection and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create database engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database: create the actionbom schema and all tables.

    Idempotent — safe to call on every startup. When Postgres was seeded
    from init.sql (via docker-compose), this is essentially a no-op.
    Included in-app so users running against their own Postgres don't
    have to remember to run init.sql first.
    """
    # Import models so Base.metadata knows about them
    from app.models import Repository, Workflow, OrgAction, RepoScanLog, ScaAlertSent  # noqa: F401

    # Schema must exist before SQLAlchemy tries to create schema-qualified tables
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS actionbom"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
