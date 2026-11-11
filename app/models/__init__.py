from app.database import Base, engine
from app.models.user import User, UserRole
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
    "UserRole",
    "Creator",
    "Task",
    "TaskStatus",
    "AudioFingerprint",
    "YouTubeQuotaLog",
    "AnalyticsCache",
    "TaskLog",
]


def init_db():
    """Create all database tables if they do not exist and ensure schema integrity."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        try:
            tables = [r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            if "users" in tables:
                cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users);").fetchall()]
                if "role" not in cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'operator' NOT NULL;")
        except Exception:
            pass

