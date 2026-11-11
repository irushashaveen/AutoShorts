import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
from app.models import Task, Creator, TaskStatus, TaskLog
from app.services.extraction.models import ExtractionResult
from app.schemas.metadata import AIMetadataOutput
from app.services.verification.risk_evaluator import VerificationResult
from app.tasks.pipeline import process_pipeline_task, publish_video_task


def test_process_pipeline_task_clean_flow(db_session, tmp_path):
    task = Task(
        source_url="https://www.tiktok.com/@coolcoder/video/101010",
        normalized_url="https://www.tiktok.com/@coolcoder/video/101010",
        status=TaskStatus.QUEUED
    )
    db_session.add(task)
    db_session.commit()
    target_id = task.id

    fake_video = tmp_path / "101010.mp4"
    fake_video.write_bytes(b"video")
    fake_thumb = tmp_path / "101010_thumb.jpg"
    fake_thumb.write_bytes(b"thumb")

    mock_extraction = ExtractionResult(
        video_id="101010",
        video_path=fake_video,
        thumbnail_path=fake_thumb,
        audio_path=None,
        caption="Epic Python trick you need to know",
        creator_id="coolcoder",
        creator_nickname="Cool Coder",
        creator_bio="Coding tips and fun",
        duration=25.0,
        width=1080,
        height=1920,
        engine_used="yt-dlp"
    )

    mock_verification = VerificationResult(
        youtube_handle=None,
        has_verified_yt_channel=False,
        audio_match_score=0.0,
        text_cosine_score=0.1,
        levenshtein_score=0.1,
        duplicate_risk_score=0.05,
        is_duplicate_suspect=False,
        recommended_status=TaskStatus.OPTIMIZING
    )

    mock_ai = AIMetadataOutput(
        title="Mind-Blowing Python Trick",
        description="Write clean code in seconds.\n\nCredit: @coolcoder",
        tags=["python", "coding", "dev"]
    )

    # Prevent db.close() in finally from breaking db_session fixture
    mock_session = MagicMock(wraps=db_session)
    mock_session.close = MagicMock()

    with patch("app.tasks.pipeline.SessionLocal", return_value=mock_session), \
         patch("app.tasks.pipeline.MediaExtractor.extract_media", return_value=mock_extraction), \
         patch("app.tasks.pipeline.VerificationPipeline.run_verification", return_value=mock_verification), \
         patch("app.tasks.pipeline.MetadataEngine.generate", return_value=(mock_ai, "gemini-1.5-flash")):

        res = process_pipeline_task(target_id)
        assert res == "READY_FOR_REVIEW"

        updated = db_session.query(Task).filter(Task.id == target_id).first()
        assert updated.status == TaskStatus.READY_FOR_REVIEW
        assert updated.ai_title == "Mind-Blowing Python Trick"
        assert updated.ai_engine_used == "gemini-1.5-flash"
        assert updated.creator_id == "coolcoder"


def test_process_pipeline_task_duplicate_suspect_branch(db_session, tmp_path):
    task = Task(
        source_url="https://www.tiktok.com/@dup/video/202020",
        normalized_url="https://www.tiktok.com/@dup/video/202020",
        status=TaskStatus.QUEUED
    )
    db_session.add(task)
    db_session.commit()
    target_id = task.id

    fake_video = tmp_path / "202020.mp4"
    fake_video.write_bytes(b"video")

    mock_extraction = ExtractionResult(
        video_id="202020",
        video_path=fake_video,
        thumbnail_path=None,
        audio_path=None,
        caption="Already uploaded video",
        creator_id="dup_user",
        creator_nickname="Dup User",
        creator_bio="Bio",
        duration=15.0,
        width=1080,
        height=1920,
        engine_used="tikwm"
    )

    mock_verification = VerificationResult(
        youtube_handle=None,
        has_verified_yt_channel=False,
        audio_match_score=0.9,
        text_cosine_score=0.9,
        levenshtein_score=0.9,
        duplicate_risk_score=0.90,
        is_duplicate_suspect=True,
        recommended_status=TaskStatus.DUPLICATE_SUSPECT
    )

    mock_session = MagicMock(wraps=db_session)
    mock_session.close = MagicMock()

    with patch("app.tasks.pipeline.SessionLocal", return_value=mock_session), \
         patch("app.tasks.pipeline.MediaExtractor.extract_media", return_value=mock_extraction), \
         patch("app.tasks.pipeline.VerificationPipeline.run_verification", return_value=mock_verification):

        res = process_pipeline_task(target_id)
        assert res == "DUPLICATE_SUSPECT"

        updated = db_session.query(Task).filter(Task.id == target_id).first()
        assert updated.status == TaskStatus.DUPLICATE_SUSPECT
        assert updated.duplicate_risk_score == 0.90
        assert updated.ai_title is None


def test_publish_video_task_flow(db_session, tmp_path):
    fake_video = tmp_path / "upload_me.mp4"
    fake_video.write_bytes(b"payload")

    task = Task(
        source_url="https://www.tiktok.com/@user/video/303030",
        normalized_url="https://www.tiktok.com/@user/video/303030",
        status=TaskStatus.SCHEDULED,
        media_path=str(fake_video),
        ai_title="Awesome Short",
        ai_description="Short description",
        ai_tags='["viral", "trend"]'
    )
    db_session.add(task)
    db_session.commit()
    target_id = task.id

    mock_session = MagicMock(wraps=db_session)
    mock_session.close = MagicMock()

    with patch("app.tasks.pipeline.SessionLocal", return_value=mock_session), \
         patch("app.tasks.pipeline.OAuthManager.build_youtube_client", return_value=MagicMock()), \
         patch("app.tasks.pipeline.ResumableUploader.upload_short", return_value="yt_video_999"), \
         patch("app.tasks.pipeline.QuotaTracker.can_upload", return_value=True):

        res = publish_video_task(target_id)
        assert res == "PUBLISHED"

        updated = db_session.query(Task).filter(Task.id == target_id).first()
        assert updated.status == TaskStatus.PUBLISHED
        assert updated.youtube_video_id == "yt_video_999"
        assert updated.published_at is not None
