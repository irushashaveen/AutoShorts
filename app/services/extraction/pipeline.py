import logging
from pathlib import Path
from typing import Optional
from app.services.extraction.models import ExtractionResult
from app.services.extraction.ytdlp_extractor import YtDlpExtractor, YtDlpExtractionError
from app.services.extraction.tikwm_client import TikWMClient, TikWMAPIError
from app.services.extraction.ffmpeg_normalizer import FFmpegNormalizer

logger = logging.getLogger(__name__)


class ExtractionFailedError(Exception):
    """Raised when both primary (yt-dlp) and fallback (TikWM) extraction engines fail."""
    pass


class MediaExtractor:
    """Orchestrates resilient media extraction with primary-secondary fallback and FFmpeg standardization."""

    def __init__(
        self,
        ytdlp_extractor: Optional[YtDlpExtractor] = None,
        tikwm_client: Optional[TikWMClient] = None,
        normalizer: Optional[FFmpegNormalizer] = None
    ):
        self.ytdlp = ytdlp_extractor or YtDlpExtractor()
        self.tikwm = tikwm_client or TikWMClient()
        self.normalizer = normalizer or FFmpegNormalizer()

    def extract_media(self, url: str, staging_dir: Path) -> ExtractionResult:
        """
        Extract video and metadata using yt-dlp first.
        If yt-dlp fails (e.g. 403, 429, anti-scraping), switch to TikWM REST API.
        Then normalize video dimensions and extract 16kHz audio for deduplication.
        """
        staging_dir.mkdir(parents=True, exist_ok=True)
        result: Optional[ExtractionResult] = None
        ytdlp_err: Optional[Exception] = None

        # 1. Primary Engine: yt-dlp
        try:
            logger.info(f"Attempting primary extraction with yt-dlp for {url}")
            result = self.ytdlp.extract(url, staging_dir)
            logger.info(f"yt-dlp extraction succeeded for video_id={result.video_id}")
        except Exception as e:
            ytdlp_err = e
            logger.warning(f"Primary yt-dlp failed ({e}). Transitioning to fallback TikWM REST API.")

        # 2. Fallback Engine: TikWM REST API
        if result is None:
            try:
                logger.info(f"Attempting fallback extraction with TikWM API for {url}")
                result = self.tikwm.extract(url, staging_dir)
                logger.info(f"TikWM extraction succeeded for video_id={result.video_id}")
            except Exception as tikwm_err:
                logger.error(f"Both extraction engines failed. yt-dlp: {ytdlp_err} | TikWM: {tikwm_err}")
                raise ExtractionFailedError(
                    f"Extraction failed across all engines. Primary: {ytdlp_err} | Fallback: {tikwm_err}"
                ) from tikwm_err

        # 3. Post-Processing & Standardization via FFmpeg
        try:
            # Normalize video to 1080x1920 portrait if needed
            normalized_video = self.normalizer.normalize_video(result.video_path)
            result.video_path = normalized_video

            # Extract 16kHz mono WAV for Chromaprint deduplication
            audio_path = self.normalizer.extract_audio_wav(normalized_video)
            result.audio_path = audio_path

            # Probe final video dimensions & duration
            probe_info = self.normalizer.probe_video(normalized_video)
            result.width = probe_info.get("width", 1080)
            result.height = probe_info.get("height", 1920)
            if not result.duration or result.duration == 0:
                result.duration = probe_info.get("duration", 0.0)

            # Ensure thumbnail exists
            if not result.thumbnail_path or not result.thumbnail_path.exists():
                thumb_path = self.normalizer.extract_thumbnail_frame(normalized_video)
                result.thumbnail_path = thumb_path

        except Exception as e:
            logger.warning(f"FFmpeg normalization encountered non-fatal issue: {e}")

        return result

