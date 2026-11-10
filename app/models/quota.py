from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class YouTubeQuotaLog(Base):
    __tablename__ = "youtube_quota_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    endpoint_called = Column(String(128), nullable=False)
    quota_units = Column(Integer, nullable=False)  # e.g., 1600 for video upload, 1 for search
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    task = relationship("Task", back_populates="quota_logs")

