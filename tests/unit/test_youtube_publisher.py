import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path
from googleapiclient.errors import HttpError
from app.models.quota import YouTubeQuotaLog
from app.services.youtube import (
    QuotaTracker,
    YouTubeQuotaExceededError,
    AnalyticsScheduler,
    ResumableUploader,
    YouTubeUploadError,
)


def test_quota_tracker_consumption_and_ceiling(db_session):
    # Initial consumption should be 0
    assert QuotaTracker.get_today_consumption(db_session) == 0
    assert QuotaTracker.can_upload(db_session, cost=1600) is True

    # Log 5 uploads = 8000 units (task_id=None for generic/unattached calls)
    for i in range(5):
        QuotaTracker.log_consumption(db_session, "videos.insert", 1600, task_id=None)

    assert QuotaTracker.get_today_consumption(db_session) == 8000
    # 8000 + 1600 = 9600 <= 10000 -> can upload 6th
    assert QuotaTracker.can_upload(db_session, cost=1600) is True

    # Log 6th upload = 9600 units
    QuotaTracker.log_consumption(db_session, "videos.insert", 1600, task_id=None)
    assert QuotaTracker.get_today_consumption(db_session) == 9600

    # 7th upload: 9600 + 1600 = 11200 > 10000 -> Cannot upload!
    assert QuotaTracker.can_upload(db_session, cost=1600) is False
    with pytest.raises(YouTubeQuotaExceededError) as exc_info:
        QuotaTracker.assert_can_upload(db_session, cost=1600)
    assert "YouTube quota ceiling reached" in str(exc_info.value)


def test_analytics_scheduler_peak_hour_query():
    mock_analytics = MagicMock()
    mock_request = MagicMock()

    # Sample rows: [hour, views, avgViewDuration]
    mock_request.execute.return_value = {
        "rows": [
            [12, 1200, 32.5],
            [17, 9800, 48.2],  # Peak hour 17 (5 PM UTC)
            [20, 4500, 36.1],
        ]
    }
    mock_analytics.reports().query.return_value = mock_request

    peak_hour, avg_duration, total_views = AnalyticsScheduler.query_peak_engagement_hour(mock_analytics)
    assert peak_hour == 17
    assert total_views == 15500


def test_analytics_scheduler_fallback():
    # If client is None, defaults to 15:00 UTC
    peak_hour, _, _ = AnalyticsScheduler.query_peak_engagement_hour(None)
    assert peak_hour == 15


def test_analytics_scheduler_timestamp_calculation():
    # 1. Base time morning 09:00, peak hour 17:00 -> should schedule today at 17:00
    base_morning = datetime(2026, 11, 10, 9, 0, 0)
    scheduled = AnalyticsScheduler.calculate_publish_timestamp(17, base_time=base_morning)
    assert scheduled == datetime(2026, 11, 10, 17, 0, 0)

    # 2. Base time evening 18:00, peak hour 17:00 -> should schedule tomorrow at 17:00
    base_evening = datetime(2026, 11, 10, 18, 0, 0)
    scheduled_tomorrow = AnalyticsScheduler.calculate_publish_timestamp(17, base_time=base_evening)
    assert scheduled_tomorrow == datetime(2026, 11, 11, 17, 0, 0)


def test_resumable_uploader_success(tmp_path, db_session):
    # Create fake video file
    fake_video = tmp_path / "test_video.mp4"
    fake_video.write_bytes(b"0" * 1024 * 1024)  # 1MB fake video

    mock_youtube = MagicMock()
    mock_insert_request = MagicMock()

    # Simulate next_chunk returning (status, response)
    # 1st chunk progress 0.5, 2nd chunk completed with ID
    mock_status = MagicMock()
    mock_status.progress.return_value = 0.5
    mock_insert_request.next_chunk.side_effect = [
        (mock_status, None),
        (None, {"id": "yt_short_12345abc"})
    ]
    mock_youtube.videos().insert.return_value = mock_insert_request

    progresses = []

    uploader = ResumableUploader(youtube_service=mock_youtube)
    video_id = uploader.upload_short(
        video_path=fake_video,
        title="Epic Shorts Test",
        description="Great video description.\n\nCredit: @tester",
        tags=["shorts", "test", "viral"],
        publish_at=datetime(2026, 11, 10, 18, 0, 0),
        db=db_session,
        task_id=None,
        progress_callback=lambda p: progresses.append(p)
    )

    assert video_id == "yt_short_12345abc"
    assert 0.5 in progresses
    # Verify 1600 quota units logged in db
    assert QuotaTracker.get_today_consumption(db_session) == 1600


def test_resumable_uploader_retries_transient_error(tmp_path, db_session):
    fake_video = tmp_path / "retry_video.mp4"
    fake_video.write_bytes(b"0" * 512)

    mock_youtube = MagicMock()
    mock_insert_request = MagicMock()

    # Simulate 503 error on first attempt, then success on second
    mock_resp_503 = MagicMock()
    mock_resp_503.status = 503
    http_error_503 = HttpError(resp=mock_resp_503, content=b"Service Unavailable")

    mock_insert_request.next_chunk.side_effect = [
        http_error_503,
        (None, {"id": "yt_recovered_video_id"})
    ]
    mock_youtube.videos().insert.return_value = mock_insert_request

    with patch("time.sleep", return_value=None):  # Avoid actual sleep in test
        uploader = ResumableUploader(youtube_service=mock_youtube)
        video_id = uploader.upload_short(
            video_path=fake_video,
            title="Recovered Short",
            description="Description",
            tags=["test"],
            publish_at=None,
            db=db_session
        )
        assert video_id == "yt_recovered_video_id"
