from pathlib import Path
from app.config import Settings


def test_default_settings():
    """Verify default settings values and constraints."""
    s = Settings()
    assert s.APP_NAME == "AutoShorts"
    assert s.DEFAULT_PUBLISH_HOUR_UTC == 15
    assert s.DUP_RISK_THRESHOLD == 0.75
    assert s.YOUTUBE_DAILY_QUOTA_LIMIT == 10000
    assert s.YOUTUBE_UPLOAD_QUOTA_COST == 1600


def test_telegram_allowed_users_parser():
    """Verify that string, list, and integer user IDs are correctly normalized."""
    s1 = Settings(TELEGRAM_ALLOWED_USERS="12345, 67890, 111213")
    assert s1.TELEGRAM_ALLOWED_USERS == [12345, 67890, 111213]

    s2 = Settings(TELEGRAM_ALLOWED_USERS=[999, 888])
    assert s2.TELEGRAM_ALLOWED_USERS == [999, 888]

    s3 = Settings(TELEGRAM_ALLOWED_USERS="")
    assert s3.TELEGRAM_ALLOWED_USERS == []


def test_ensure_directories(tmp_path):
    """Verify directory generation for database and media staging."""
    data_dir = tmp_path / "custom_data"
    media_dir = tmp_path / "custom_staging"
    s = Settings(DATA_DIR=data_dir, MEDIA_STAGING_DIR=media_dir)
    s.ensure_directories()

    assert data_dir.exists()
    assert (data_dir / "database").exists()
    assert media_dir.exists()

