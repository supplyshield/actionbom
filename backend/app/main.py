"""FastAPI application entry point."""
import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Add parent directory to path to import actionbom
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import settings
from app.database import init_db, SessionLocal
from app.api.endpoints import router
from app.cron.workflow_scanner import daily_batch_scan_job
from app.repositories.repository_repo import RepositoryRepository
from app.services.repo_importer import import_org_repos


# Global scheduler instance
scheduler = None

# Path to built frontend (populated in Docker, absent in local dev)
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global scheduler

    # Startup
    print("🚀 Starting ActionBOM Backend...")

    # Initialize database
    print("📦 Initializing database...")
    init_db()
    print("✓ Database initialized")

    # Bootstrap: auto-import repos from TARGET_ORG on first boot
    _bootstrap_repositories()

    # Start cron scheduler if enabled
    if settings.CRON_ENABLED:
        print("⏰ Starting cron scheduler...")
        scheduler = AsyncIOScheduler()

        # Parse cron schedule (format: "minute hour day month day_of_week")
        parts = settings.CRON_SCHEDULE.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )

            scheduler.add_job(
                daily_batch_scan_job,
                trigger=trigger,
                id="daily_batch_scan",
                name="Daily Batch Scan",
                replace_existing=True
            )

            scheduler.start()
            print(f"✓ Cron scheduler started (schedule: {settings.CRON_SCHEDULE})")
            print(f"  Next run: {scheduler.get_job('daily_batch_scan').next_run_time}")

            # Run the scan immediately on startup (in background so it doesn't block)
            print("🔄 Triggering initial scan on startup...")
            asyncio.create_task(_run_initial_scan())
        else:
            print(f"⚠️  Invalid cron schedule format: {settings.CRON_SCHEDULE}")
    else:
        print("⊘ Cron scheduler disabled")

    print(f"✓ Backend ready on http://0.0.0.0:8000")
    print(f"📚 API docs available at http://0.0.0.0:8000/docs\n")

    yield

    # Shutdown
    if scheduler:
        print("\n⏰ Stopping cron scheduler...")
        scheduler.shutdown()
        print("✓ Cron scheduler stopped")

    print("👋 Backend shutdown complete")


async def _run_initial_scan():
    """Run the batch scan job immediately in a thread (it's synchronous)."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, daily_batch_scan_job)
        print("✓ Initial scan completed")
    except Exception as e:
        print(f"⚠️  Initial scan failed: {e}")


def _bootstrap_repositories():
    """One-time repo import from TARGET_ORG when the table is empty.

    Silent skip if TARGET_ORG is unset (user is bringing their own data)
    or the table already has rows (never re-imports — respects manual
    edits and prior imports). Non-fatal on GitHub errors: log and let the
    app start; user can retry via `python -m app.import_repos`.
    """
    if not settings.TARGET_ORG:
        print("⊘ Repo bootstrap skipped (TARGET_ORG not set)")
        return

    db = SessionLocal()
    try:
        existing = RepositoryRepository.count(db)
        if existing > 0:
            print(f"⊘ Repo bootstrap skipped ({existing} repos already tracked)")
            return

        print(f"📥 Empty repositories table — importing from GitHub org '{settings.TARGET_ORG}'...")
        try:
            result = import_org_repos(db, settings.TARGET_ORG)
            print(f"✓ Imported {result['inserted']} repos (fetched {result['fetched']} from GitHub)")
        except Exception as e:
            print(f"⚠️  Repo bootstrap failed: {e}")
            print("   The app will start anyway. Retry manually with:")
            print("   docker compose exec app python -m app.import_repos --org <org>")
    finally:
        db.close()


# Create FastAPI app
app = FastAPI(
    title="ActionBOM Workflow Scanner",
    description="Backend API for scanning GitHub Actions workflows across organizations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (keep for local dev where frontend runs on :3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes (registered BEFORE static files so /api/* takes priority)
app.include_router(router, prefix="/api", tags=["api"])

# Serve frontend static files if the build exists
if STATIC_DIR.is_dir():
    # Serve static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    # SPA catch-all: any non-API route serves index.html for client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the React SPA for all non-API routes."""
        index = STATIC_DIR / "index.html"
        if not full_path:
            return FileResponse(index)

        static_root = STATIC_DIR.resolve()
        try:
            candidate = (STATIC_DIR / full_path).resolve(strict=False)
        except (OSError, RuntimeError):
            return FileResponse(index)

        # Only serve files that live inside static_root — otherwise fall
        # back to index.html so path traversal (`..`, absolute paths,
        # URL-encoded variants) can't reach files outside the SPA build.
        try:
            candidate.relative_to(static_root)
        except ValueError:
            return FileResponse(index)

        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
else:
    # No frontend build — keep the JSON root endpoint for local backend dev
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "ActionBOM Workflow Scanner API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
