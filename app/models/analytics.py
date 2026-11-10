from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime
from app.database import Base


class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    peak_hour_utc = Column(Integer, default=15, nullable=False)  # 0 to 23
    avg_view_duration = Column(Float, default=0.0)
    total_views_30d = Column(Integer, default=0)
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

