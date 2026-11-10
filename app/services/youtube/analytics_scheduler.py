import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.analytics import AnalyticsCache

logger = logging.getLogger(__name__)


class AnalyticsScheduler:
    """Calculates peak audience engagement hours and optimal publication timestamps."""

    DEFAULT_HOUR = settings.DEFAULT_PUBLISH_HOUR_UTC

    @classmethod
    def query_peak_engagement_hour(
        cls,
        analytics_client: Optional[object] = None,
        db: Optional[Session] = None
    ) -> Tuple[int, float, int]:
        """
        Query YouTube Analytics API for historical 30-day view counts by hour.
        Returns: (peak_hour_utc, avg_view_duration_seconds, total_views)
        """
        if analytics_client is None:
            # Check if recently cached in SQLite
            if db:
                cached = db.query(AnalyticsCache).order_by(AnalyticsCache.calculated_at.desc()).first()
                if cached and (datetime.utcnow() - cached.calculated_at).days < 7:
                    return cached.peak_hour_utc, cached.avg_view_duration, cached.total_views_30d
            return cls.DEFAULT_HOUR, 0.0, 0

        try:
            today = datetime.utcnow().date()
            start_date = (today - timedelta(days=30)).isoformat()
            end_date = today.isoformat()

            # Execute query on YouTube Analytics API
            request = analytics_client.reports().query(  # type: ignore
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,averageViewDuration",
                dimensions="hour",
                filters="trafficSourceType==SHORTS"
            )
            response = request.execute()
            rows = response.get("rows", [])

            if not rows:
                logger.info(f"Insufficient Analytics data. Defaulting to {cls.DEFAULT_HOUR}:00 UTC.")
                return cls.DEFAULT_HOUR, 0.0, 0

            # Find row with maximum views (row format: [hour, views, avgViewDuration])
            # Note: hour dimension in YouTube Analytics is typically 0-23
            best_row = max(rows, key=lambda r: r[1])
            peak_hour = int(best_row[0])
            total_views = sum(int(r[1]) for r in rows)
            avg_duration = sum(float(r[2]) for r in rows) / len(rows)

            # Cache to database if session provided
            if db:
                cache_entry = AnalyticsCache(
                    peak_hour_utc=peak_hour,
                    avg_view_duration=round(avg_duration, 2),
                    total_views_30d=total_views,
                    calculated_at=datetime.utcnow()
                )
                db.add(cache_entry)
                db.commit()

            return peak_hour, avg_duration, total_views
        except Exception as e:
            logger.warning(f"Failed to query YouTube Analytics API ({e}). Defaulting to {cls.DEFAULT_HOUR}:00 UTC.")
            return cls.DEFAULT_HOUR, 0.0, 0

    @classmethod
    def calculate_publish_timestamp(
        cls,
        peak_hour_utc: int,
        base_time: Optional[datetime] = None
    ) -> datetime:
        """
        Calculate next optimal publication slot.
        If today's peak hour is in the past (or within 45 min), schedule for tomorrow.
        """
        now = base_time or datetime.utcnow()
        scheduled = now.replace(hour=peak_hour_utc, minute=0, second=0, microsecond=0)

        # If slot is in the past or within 45 minutes, push to next day
        if scheduled <= now + timedelta(minutes=45):
            scheduled += timedelta(days=1)

        return scheduled

