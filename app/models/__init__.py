from app.database import Base, engine
from app.models.user import User
from app.models.creator import Creator
from app.models.task import Task, TaskStatus
from app.models.fingerprint import AudioFingerprint
from app.models.quota import YouTubeQuotaLog
from app.models.analytics import AnalyticsCache
from app.models.log import TaskLog

__all__ = [
    "Base",
    "engine",
    "User",
    "Creator",
    "Task",
    "TaskStatus",
    "AudioFingerprint",
    "YouTubeQuotaLog",
    "AnalyticsCache",
    "TaskLog",
]


def init_db():
    """Create all database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)

