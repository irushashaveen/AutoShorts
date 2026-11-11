import uuid
from datetime import datetime
from sqlalchemy import text
from app.models import Task, Creator, AudioFingerprint, YouTubeQuotaLog, AnalyticsCache, TaskLog, TaskStatus
from app.database import engine


def test_sqlite_wal_pragmas():
    """Verify that SQLite connection applies WAL mode and concurrency PRAGMAs."""
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA journal_mode;")).scalar()
        # In-memory or file databases set to WAL return either 'wal' or 'memory' (for :memory:)
        assert res.lower() in ("wal", "memory")
        busy_timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        assert busy_timeout == 5000


def test_create_task_and_creator_relationship(db_session):
    """Verify creating a Task with associated Creator and state transitions."""
    creator = Creator(
        id="creative_coder",
        nickname="Creative Coder",
        bio="Official YouTube: youtube.com/@creative_coder",
        youtube_handle="@creative_coder",
        has_verified_yt_channel=True
    )
    db_session.add(creator)
    db_session.commit()

    task = Task(
        source_url="https://www.tiktok.com/@creative_coder/video/71234567890",
        normalized_url="https://www.tiktok.com/@creative_coder/video/71234567890",
        status=TaskStatus.QUEUED,
        creator_id=creator.id,
        raw_caption="Amazing new coding trick you must see #code #tech",
        duplicate_risk_score=0.15
    )
    db_session.add(task)
    db_session.commit()

    retrieved = db_session.query(Task).filter(Task.id == task.id).first()
    assert retrieved is not None
    assert retrieved.creator.nickname == "Creative Coder"
    assert retrieved.status == TaskStatus.QUEUED

    # Update status transition
    retrieved.status = TaskStatus.EXTRACTING
    db_session.commit()

    updated = db_session.query(Task).filter(Task.id == task.id).first()
    assert updated.status == TaskStatus.EXTRACTING


def test_audio_fingerprint_relationship(db_session):
    """Verify audio fingerprint cascade persistence."""
    task = Task(
        source_url="https://www.tiktok.com/@sample/video/1111",
        normalized_url="https://www.tiktok.com/@sample/video/1111",
        status=TaskStatus.EXTRACTED
    )
    db_session.add(task)
    db_session.commit()

    fp = AudioFingerprint(
        task_id=task.id,
        fingerprint_hash="AQAAZEqUJUmSZEkSZk-WHE8e_BwePEce..."
    )
    db_session.add(fp)
    db_session.commit()

    retrieved_fps = db_session.query(AudioFingerprint).filter(AudioFingerprint.task_id == task.id).all()
    assert len(retrieved_fps) == 1
    assert retrieved_fps[0].fingerprint_hash.startswith("AQAA")


def test_quota_log_and_analytics_cache(db_session):
    """Verify quota usage logging and analytics caching."""
    q_log = YouTubeQuotaLog(
        endpoint_called="videos.insert",
        quota_units=1600
    )
    db_session.add(q_log)

    cache = AnalyticsCache(
        peak_hour_utc=17,
        avg_view_duration=42.5,
        total_views_30d=154200
    )
    db_session.add(cache)
    db_session.commit()

    assert db_session.query(YouTubeQuotaLog).count() == 1
    cached_entry = db_session.query(AnalyticsCache).first()
    assert cached_entry.peak_hour_utc == 17
    assert cached_entry.total_views_30d == 154200

