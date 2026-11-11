import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Task, Creator, TaskStatus, TaskLog, YouTubeQuotaLog
from app.services.extraction.models import ExtractionResult
from app.services.youtube.quota_tracker import QuotaTracker
from app.schemas.metadata import AIMetadataOutput
from app.tasks.pipeline import process_pipeline_task, publish_video_task


def test_full_pipeline_happy_path(db_session: Session, tmp_path: Path):
    """
    End-to-end integration test validating complete pipeline lifecycle:
    1. Task registration with normalized URL
    2. Phase 1-2 Media extraction with fallback awareness
    3. Phase 3 Verification & deduplication (clean creator, low duplicate risk)
    4. Phase 4 AI metadata generation (title, description, tags)
    5. Scheduled publishing status transition
    6. Phase 5 YouTube resumable upload and audit log creation
    """
    sample_video = tmp_path / "sample.mp4"
    sample_video.write_bytes(b"\x00" * 1024)
    sample_audio = tmp_path / "sample.wav"
    sample_audio.write_bytes(b"\x00" * 512)
    # 1. Setup Task Record
    task_id = str(uuid.uuid4())
    test_url = "https://www.tiktok.com/@pro_creator/video/9876543210123456789"
    task = Task(
        id=task_id,
        source_url=test_url,
        normalized_url=test_url,
        status=TaskStatus.QUEUED
    )
    db_session.add(task)
    db_session.commit()

    # 2. Mock External Services for Phase 1-4 Pipeline Processing
    mock_extraction_res = ExtractionResult(
        video_id="9876543210123456789",
        video_path=sample_video,
        thumbnail_path=None,
        audio_path=sample_audio,
        caption="Amazing 3D animation workflow tutorial #blender #art",
        creator_id="pro_creator",
        creator_nickname="Pro Creator",
        creator_bio="Check out my content! No other links.",
        duration=42.0,
        width=1080,
        height=1920,
        engine_used="yt-dlp"
    )

    mock_ai_metadata = AIMetadataOutput(
        title="Mind-Blowing 3D Animation Workflow",
        description="Here is how to create stunning 3D renders quickly. Subscribe for more VFX guides!\n\nOriginal creator: @pro_creator",
        tags=["3danimation", "blendertutorial", "vfxguide"],
        scheduled_delay_hours=4
    )

    with patch("app.tasks.pipeline.SessionLocal", return_value=db_session), \
         patch("app.tasks.pipeline.MediaExtractor") as MockExtractor, \
         patch("app.tasks.pipeline.MetadataEngine") as MockAIEngine:

        # Configure mock extractor instance
        mock_ext_instance = MagicMock()
        mock_ext_instance.extract_media.return_value = mock_extraction_res
        MockExtractor.return_value = mock_ext_instance

        # Configure mock AI engine instance
        mock_ai_instance = MagicMock()
        mock_ai_instance.generate.return_value = (mock_ai_metadata, "gemini")
        MockAIEngine.return_value = mock_ai_instance

        # Execute Celery Task synchronously
        result_status = process_pipeline_task(task_id)
        assert result_status == TaskStatus.READY_FOR_REVIEW.value

    # Refresh task from database
    db_session.expire_all()
    updated_task = db_session.query(Task).filter(Task.id == task_id).first()
    assert updated_task is not None
    assert updated_task.status == TaskStatus.READY_FOR_REVIEW
    assert updated_task.ai_title == "Mind-Blowing 3D Animation Workflow"
    assert "Original creator: @pro_creator" in updated_task.ai_description
    assert updated_task.creator_id is not None

    # Assert TaskLogs were generated
    logs = db_session.query(TaskLog).filter(TaskLog.task_id == task_id).all()
    assert len(logs) >= 3

    # Operator approves task -> transitions to SCHEDULED
    updated_task.status = TaskStatus.SCHEDULED
    db_session.commit()

    # 3. Test Phase 5 Publishing
    def fake_upload(*args, **kwargs):
        if kwargs.get("db"):
            QuotaTracker.log_consumption(
                kwargs["db"],
                endpoint="videos.insert",
                units=1600,
                task_id=task_id
            )
        return "yt_video_id_99999"

    with patch("app.tasks.pipeline.SessionLocal", return_value=db_session), \
         patch("app.tasks.pipeline.OAuthManager.build_youtube_client", return_value=MagicMock()), \
         patch("app.tasks.pipeline.ResumableUploader.upload_short", side_effect=fake_upload):

        pub_result = publish_video_task(task_id)
        assert pub_result == TaskStatus.PUBLISHED.value

    # Refresh task after publishing
    db_session.expire_all()
    published_task = db_session.query(Task).filter(Task.id == task_id).first()
    assert published_task.status == TaskStatus.PUBLISHED
    assert published_task.youtube_video_id == "yt_video_id_99999"
    assert published_task.published_at is not None

    # Assert Quota Log was recorded
    quota_logs = db_session.query(YouTubeQuotaLog).filter(YouTubeQuotaLog.task_id == task_id).all()
    assert len(quota_logs) == 1
    assert quota_logs[0].quota_units == 1600
