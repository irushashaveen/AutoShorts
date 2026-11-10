import logging
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.models.quota import YouTubeQuotaLog

logger = logging.getLogger(__name__)


class YouTubeQuotaExceededError(Exception):
    """Raised when daily quota limit (10,000 units) would be exceeded."""
    pass


class QuotaTracker:
    """Monitors and enforces the daily 10,000 unit YouTube API quota ceiling."""

    DAILY_LIMIT = settings.YOUTUBE_DAILY_QUOTA_LIMIT
    UPLOAD_COST = settings.YOUTUBE_UPLOAD_QUOTA_COST

    @classmethod
    def get_today_consumption(cls, db: Session) -> int:
        """Calculate total units consumed by API calls today (UTC)."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        total = db.query(func.sum(YouTubeQuotaLog.quota_units)).filter(
            YouTubeQuotaLog.created_at >= today_start
        ).scalar()
        return int(total or 0)

    @classmethod
    def can_upload(cls, db: Session, cost: int = settings.YOUTUBE_UPLOAD_QUOTA_COST) -> bool:
        """Check if an upload (cost 1600) can be executed without hitting ceiling."""
        consumed = cls.get_today_consumption(db)
        return (consumed + cost) <= cls.DAILY_LIMIT

    @classmethod
    def log_consumption(
        cls,
        db: Session,
        endpoint: str,
        units: int,
        task_id: Optional[str] = None
    ) -> YouTubeQuotaLog:
        """Record quota consumption in the database."""
        entry = YouTubeQuotaLog(
            task_id=task_id,
            endpoint_called=endpoint,
            quota_units=units,
            created_at=datetime.utcnow()
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info(f"Logged YouTube quota: {units} units for {endpoint} (task={task_id})")
        return entry

    @classmethod
    def assert_can_upload(cls, db: Session, cost: int = settings.YOUTUBE_UPLOAD_QUOTA_COST) -> None:
        """Raise YouTubeQuotaExceededError if quota ceiling is reached."""
        consumed = cls.get_today_consumption(db)
        if (consumed + cost) > cls.DAILY_LIMIT:
            remaining = max(0, cls.DAILY_LIMIT - consumed)
            raise YouTubeQuotaExceededError(
                f"YouTube quota ceiling reached: {consumed}/{cls.DAILY_LIMIT} used. "
                f"Requires {cost} units, but only {remaining} units remaining today."
            )

