import logging
from pathlib import Path
from typing import Optional, Dict, Any
import yt_dlp
from app.services.extraction.models import ExtractionResult

logger = logging.getLogger(__name__)


class YtDlpExtractionError(Exception):
    """Raised when yt-dlp encounters 403, 429, or scraping failure."""
    pass


class YtDlpExtractor:
    """Primary extraction engine utilizing yt-dlp for watermark-free media retrieval."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def extract(self, url: str, staging_dir: Path) -> ExtractionResult:
        """Download media and metadata using yt-dlp."""
        staging_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(staging_dir / "%(id)s.%(ext)s")

        ydl_opts: Dict[str, Any] = {
            "format": "bv*[vcodec^=avc]+ba/b/b",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self.timeout,
            "writethumbnail": True,
            "postprocessors": [{
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
            }],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise YtDlpExtractionError("No metadata returned by yt-dlp.")

                video_id = str(info.get("id") or "unknown_id")
                caption = info.get("title") or info.get("description") or ""
                duration = float(info.get("duration") or 0.0)
                width = int(info.get("width") or 0)
                height = int(info.get("height") or 0)

                creator_id = (
                    info.get("uploader_id") or
                    info.get("uploader") or
                    info.get("channel_id") or
                    "unknown_creator"
                )
                creator_nickname = info.get("uploader") or info.get("channel") or creator_id
                creator_bio = (
                    info.get("channel_description") or
                    info.get("uploader_description") or
                    ""
                )

                # Locate downloaded video file
                video_path = staging_dir / f"{video_id}.mp4"
                if not video_path.exists():
                    # Fallback lookup in case ext differs
                    candidates = list(staging_dir.glob(f"{video_id}.*"))
                    mp4_candidates = [c for c in candidates if c.suffix in (".mp4", ".mkv", ".webm")]
                    if mp4_candidates:
                        video_path = mp4_candidates[0]
                    else:
                        raise YtDlpExtractionError(f"Video file not found on disk after yt-dlp download: {video_id}")

                # Locate thumbnail if saved
                thumb_candidates = list(staging_dir.glob(f"{video_id}.jpg")) + list(staging_dir.glob(f"{video_id}*.webp"))
                thumbnail_path = thumb_candidates[0] if thumb_candidates else None

                return ExtractionResult(
                    video_id=video_id,
                    video_path=video_path,
                    thumbnail_path=thumbnail_path,
                    audio_path=None,
                    caption=caption,
                    creator_id=creator_id,
                    creator_nickname=creator_nickname,
                    creator_bio=creator_bio,
                    duration=duration,
                    width=width,
                    height=height,
                    engine_used="yt-dlp"
                )
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for {url}: {e}")
            raise YtDlpExtractionError(f"yt-dlp error: {e}") from e

