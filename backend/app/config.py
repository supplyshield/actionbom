"""Configuration settings for the application."""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        ""
    )
    
    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_API_BASE: str = "https://api.github.com"
    
    # Cron
    CRON_ENABLED: bool = os.getenv("CRON_ENABLED", "true").lower() == "true"
    CRON_SCHEDULE: str = os.getenv("CRON_SCHEDULE", "*/30 * * * *")  # Every 30 min

    # Batch scanning
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "50"))
    RATE_LIMIT_THRESHOLD: int = int(os.getenv("RATE_LIMIT_THRESHOLD", "500"))
    
    # Target organization
    # When set, the app auto-imports repos from this GitHub org on first
    # boot (if the repositories table is empty) and filters first-party
    # actions out of the org-actions inventory. Leave blank to bring your
    # own repositories list.
    TARGET_ORG: str = os.getenv("TARGET_ORG", "")

    # Slack alerts
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    DASHBOARD_BASE_URL: str = os.getenv("DASHBOARD_BASE_URL", "http://localhost:8000")
    # Optional Slack user ID to cc on template-injection alerts (e.g. "U08FVDUN2MS").
    # Leave blank to skip the cc line entirely.
    SLACK_CC_USER_ID: str = os.getenv("SLACK_CC_USER_ID", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
