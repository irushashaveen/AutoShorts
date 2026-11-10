import os
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Callable
from sqlalchemy.orm import Session
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from app.config import settings
from app.services.youtube.quota_tracker import QuotaTracker

logger = logging.getLogger(__name__)

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB resumable chunks (5,242,880 bytes)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
MAX_RETRIES = 5


class YouTubeUploadError(Exception):
    """Raised when YouTube Shorts upload fails permanently."""
    pass


class ResumableUploader:
    """Manages 5MB chunked resumable video uploads to YouTube Data API v3 with exponential backoff."""

    def __init__(self, youtube_service: Optional[object] = None):
        self.youtube = youtube_service

    def upload_short(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        publish_at: Optional[datetime],
        db: Optional[Session] = None,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        """
        Uploads portrait MP4 video in 5MB resumable chunks with exponential backoff.
        Returns: YouTube Video ID
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not self.youtube:
            raise YouTubeUploadError("Authenticated YouTube Data API client is required.")

        # Check quota availability before initiating insertion
        if db:
            QuotaTracker.assert_can_upload(db, cost=settings.YOUTUBE_UPLOAD_QUOTA_COST)

        # Build video metadata body
        body = {
            "snippet": {
                "title": title[:100],  # YouTube max title is 100
                "description": description,
                "tags": tags[:15],
                "categoryId": "22",  # Default category
            },
            "status": {
                "selfDeclaredMadeForKids": False,
            }
        }

        # Schedule publication if publish_at provided
        if publish_at:
            body["status"]["privacyStatus"] = "private"
            # Format: YYYY-MM-DDTHH:MM:SSZ
            body["status"]["publishAt"] = publish_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            body["status"]["privacyStatus"] = "public"

        media_body = MediaFileUpload(
            str(video_path),
            chunksize=CHUNK_SIZE,
            resumable=True,
            mimetype="video/mp4"
        )

        request = self.youtube.videos().insert(  # type: ignore
            part="snippet,status",
            body=body,
            media_body=media_body
        )

        response = None
        retry_count = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = float(status.progress())
                    logger.info(f"Upload progress for {video_path.name}: {progress * 100:.1f}%")
                    if progress_callback:
                        try:
                            progress_callback(progress)
                        except Exception as cb_err:
                            logger.warning(f"Progress callback error: {cb_err}")
                retry_count = 0  # Reset retry on successful chunk
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES and retry_count < MAX_RETRIES:
                    retry_count += 1
                    sleep_seconds = 2 ** retry_count
                    logger.warning(
                        f"Transient HTTP {e.resp.status} on chunk upload. "
                        f"Retrying in {sleep_seconds}s (attempt {retry_count}/{MAX_RETRIES})..."
                    )
                    time.sleep(sleep_seconds)
                else:
                    logger.error(f"Fatal YouTube HTTP error during upload: {e}")
                    raise YouTubeUploadError(f"YouTube upload failed: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error during resumable chunk upload: {e}")
                raise YouTubeUploadError(f"Unexpected upload failure: {e}") from e

        youtube_video_id = response.get("id")
        if not youtube_video_id:
            raise YouTubeUploadError(f"Upload succeeded but no video ID was returned: {response}")

        logger.info(f"Successfully uploaded YouTube Short: https://youtube.com/shorts/{youtube_video_id}")

        # Log quota usage (1600 units)
        if db:
            QuotaTracker.log_consumption(
                db=db,
                endpoint="videos.insert",
                units=settings.YOUTUBE_UPLOAD_QUOTA_COST,
                task_id=task_id
            )

        return youtube_video_id

