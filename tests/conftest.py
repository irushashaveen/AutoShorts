import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Task, Creator, AudioFingerprint, YouTubeQuotaLog, AnalyticsCache, TaskLog
from app.config import Settings


@pytest.fixture
def test_settings(tmp_path):
    """Fixture providing isolated Settings pointing to temporary directories."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    media_dir = tmp_path / "media_staging"
    media_dir.mkdir()
    db_file = data_dir / "test.db"

    return Settings(
        APP_ENV="test",
        DEBUG=True,
        DATA_DIR=data_dir,
        DATABASE_URL=f"sqlite:///{db_file}",
        MEDIA_STAGING_DIR=media_dir,
        TELEGRAM_ALLOWED_USERS=[12345678, 87654321],
    )


@pytest.fixture
def db_session():
    """Fixture providing a fresh in-memory SQLite database session for unit tests."""
    test_engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

