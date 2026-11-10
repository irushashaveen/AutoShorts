import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.config import settings
from app.models import Task, Creator, AudioFingerprint, TaskLog, TaskStatus
from app.services.extraction import MediaExtractor, ExtractionFailedError
from app.services.verification import VerificationPipeline
from app.services.ai import MetadataEngine, MetadataGenerationFailedError
from app.services.youtube import (
    ResumableUploader,
    AnalyticsScheduler,
    QuotaTracker,
    YouTubeQuotaExceededError,
    OAuthManager,
)

logger = logging.getLogger(__name__)


def log_task_event(db: Session, task_id: str, stage: str, message: str, level: str = "INFO"):
    """Helper to record task audit events in SQLite."""
    entry = TaskLog(
        task_id=task_id,
        level=level,
        stage=stage,
        message=message,
        created_at=datetime.utcnow()
    )
    db.add(entry)
    db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_pipeline_task(self, task_id: str) -> str:
    """
    Executes Phase 1 through Phase 4 of the autonomous curation pipeline:
    1. Media Extraction (yt-dlp -> TikWM -> FFmpeg)
    2. Verification & Deduplication (Bio Scan -> Chromaprint -> TF-IDF)
    3. AI Metadata Optimization (Gemini 1.5 -> Ollama Qwen 2.5)
    """
    db: Session = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found in database.")
            return "TASK_NOT_FOUND"

        # -------------------------------------------------------------
        # Phase 1 & 2: Watermark-Free Extraction
        # -------------------------------------------------------------
        task.status = TaskStatus.EXTRACTING
        db.commit()
        log_task_event(db, task_id, "EXTRACTION", f"Initiating extraction for {task.normalized_url}")

        extractor = MediaExtractor()
        try:
            extraction_res = extractor.extract_media(task.normalized_url, settings.MEDIA_STAGING_DIR)
        except ExtractionFailedError as e:
            task.status = TaskStatus.FAILED_EXTRACTION
            task.error_message = str(e)
            db.commit()
            log_task_event(db, task_id, "EXTRACTION", f"Extraction failed: {e}", level="ERROR")
            return "FAILED_EXTRACTION"

        # Update or create creator record
        creator = db.query(Creator).filter(Creator.id == extraction_res.creator_id).first()
        if not creator:
            creator = Creator(
                id=extraction_res.creator_id,
                nickname=extraction_res.creator_nickname,
                bio=extraction_res.creator_bio,
                created_at=datetime.utcnow()
            )
            db.add(creator)
            db.commit()

        # Update task with media details
        task.tiktok_video_id = extraction_res.video_id
        task.creator_id = creator.id
        task.raw_caption = extraction_res.caption
        task.media_path = str(extraction_res.video_path)
        task.thumbnail_path = str(extraction_res.thumbnail_path) if extraction_res.thumbnail_path else None
        task.duration = extraction_res.duration
        task.width = extraction_res.width
        task.height = extraction_res.height
        task.status = TaskStatus.EXTRACTED
        db.commit()
        log_task_event(db, task_id, "EXTRACTION", f"Extraction completed via {extraction_res.engine_used}")

        # -------------------------------------------------------------
        # Phase 3: Creator Rights & Deduplication Verification
        # -------------------------------------------------------------
        task.status = TaskStatus.VERIFYING
        db.commit()
        log_task_event(db, task_id, "VERIFICATION", "Running bio scan and deduplication heuristics")

        verifier = VerificationPipeline()
        audio_wav = Path(extraction_res.audio_path) if extraction_res.audio_path else None
        verification_res = verifier.run_verification(
            creator_bio=creator.bio,
            candidate_caption=task.raw_caption or "",
            audio_wav_path=audio_wav,
            db=db
        )

        # Update creator handle info
        if verification_res.youtube_handle:
            creator.youtube_handle = verification_res.youtube_handle
            creator.has_verified_yt_channel = verification_res.has_verified_yt_channel

        task.audio_match_score = verification_res.audio_match_score
        task.text_cosine_score = verification_res.text_cosine_score
        task.levenshtein_score = verification_res.levenshtein_score
        task.duplicate_risk_score = verification_res.duplicate_risk_score

        # Save audio fingerprint if generated
        if audio_wav and audio_wav.exists():
            try:
                _, fp_hash = verifier.hasher.fingerprint_file(audio_wav)
                fp_record = AudioFingerprint(task_id=task.id, fingerprint_hash=fp_hash)
                db.add(fp_record)
            except Exception as fp_err:
                logger.warning(f"Failed to record audio fingerprint: {fp_err}")

        # Evaluate Flagging Conditions
        if verification_res.has_verified_yt_channel:
            task.status = TaskStatus.FLAGGED_CREATOR_CHANNEL
            db.commit()
            log_task_event(
                db, task_id, "VERIFICATION",
                f"Creator has active YouTube channel {creator.youtube_handle}. Flagged for review.",
                level="WARNING"
            )
            return "FLAGGED_CREATOR_CHANNEL"

        if verification_res.is_duplicate_suspect:
            task.status = TaskStatus.DUPLICATE_SUSPECT
            db.commit()
            log_task_event(
                db, task_id, "VERIFICATION",
                f"Duplicate risk score {verification_res.duplicate_risk_score:.2f} > threshold. Flagged for review.",
                level="WARNING"
            )
            return "DUPLICATE_SUSPECT"

        db.commit()

        # -------------------------------------------------------------
        # Phase 4: AI Metadata Optimization
        # -------------------------------------------------------------
        task.status = TaskStatus.OPTIMIZING
        db.commit()
        log_task_event(db, task_id, "AI", "Generating high-CTR YouTube Shorts metadata")

        metadata_engine = MetadataEngine()
        try:
            ai_output, engine_used = metadata_engine.generate(
                caption=task.raw_caption or "",
                creator_username=creator.id,
                creator_nickname=creator.nickname or "",
                duration=task.duration or 0.0
            )
        except MetadataGenerationFailedError as e:
            task.status = TaskStatus.FAILED_OPTIMIZATION
            task.error_message = str(e)
            db.commit()
            log_task_event(db, task_id, "AI", f"Metadata generation failed: {e}", level="ERROR")
            return "FAILED_OPTIMIZATION"

        task.ai_title = ai_output.title
        task.ai_description = ai_output.description
        task.ai_tags = json.dumps(ai_output.tags)
        task.ai_engine_used = engine_used
        task.status = TaskStatus.READY_FOR_REVIEW
        db.commit()

        log_task_event(db, task_id, "AI", f"Metadata generated successfully via {engine_used}")
        return "READY_FOR_REVIEW"

    except Exception as exc:
        logger.error(f"Unhandled exception in pipeline task {task_id}: {exc}", exc_info=True)
        if db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.error_message = str(exc)
                db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=5, default_retry_delay=300)
def publish_video_task(self, task_id: str) -> str:
    """
    Executes Phase 5 publication:
    Uploads portrait MP4 video in 5MB resumable chunks with daily quota checks.
    """
    db: Session = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found for upload.")
            return "TASK_NOT_FOUND"

        if not task.media_path or not Path(task.media_path).exists():
            task.status = TaskStatus.FAILED_UPLOAD
            task.error_message = "Staged media file missing from disk."
            db.commit()
            return "MEDIA_MISSING"

        # Check quota availability
        if not QuotaTracker.can_upload(db):
            task.status = TaskStatus.PAUSED_QUOTA
            task.error_message = "Daily YouTube quota ceiling reached. Publishing paused until 00:00 PST."
            db.commit()
            log_task_event(db, task_id, "UPLOAD", "Daily quota exhausted. Task paused.", level="WARNING")
            return "PAUSED_QUOTA"

        task.status = TaskStatus.UPLOADING
        db.commit()
        log_task_event(db, task_id, "UPLOAD", "Starting 5MB chunked resumable upload to YouTube Shorts")

        # Initialize authenticated YouTube Data API client
        oauth_mgr = OAuthManager()
        yt_service = oauth_mgr.build_youtube_client()
        uploader = ResumableUploader(youtube_service=yt_service)

        tags = json.loads(task.ai_tags) if task.ai_tags else ["shorts"]

        def update_progress(p: float):
            # Update progress percent in database
            task.upload_progress_percent = round(p * 100, 1)
            db.commit()

        youtube_id = uploader.upload_short(
            video_path=Path(task.media_path),
            title=task.ai_title or "YouTube Short",
            description=task.ai_description or "",
            tags=tags,
            publish_at=task.scheduled_publish_at,
            db=db,
            task_id=task.id,
            progress_callback=update_progress
        )

        task.youtube_video_id = youtube_id
        task.published_at = datetime.utcnow()
        task.upload_progress_percent = 100.0
        task.status = TaskStatus.PUBLISHED
        db.commit()

        log_task_event(db, task_id, "UPLOAD", f"Published to YouTube Shorts: https://youtube.com/shorts/{youtube_id}")
        return "PUBLISHED"

    except YouTubeQuotaExceededError as q_err:
        task.status = TaskStatus.PAUSED_QUOTA
        task.error_message = str(q_err)
        db.commit()
        return "PAUSED_QUOTA"
    except Exception as exc:
        logger.error(f"Upload failed for task {task_id}: {exc}", exc_info=True)
        if db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.error_message = str(exc)
                db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()

