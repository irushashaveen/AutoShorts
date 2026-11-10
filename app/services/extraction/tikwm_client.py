import logging
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from app.services.extraction.models import ExtractionResult

logger = logging.getLogger(__name__)


class TikWMAPIError(Exception):
    """Raised when TikWM returns an error or non-zero status."""
    pass


class TikWMClient:
    """Fallback client interacting with the TikWM REST API for watermark-free TikTok media."""

    BASE_URL = "https://www.tikwm.com/api/"

    def __init__(self, client: Optional[httpx.Client] = None, timeout: float = 30.0):
        self._client = client
        self.timeout = timeout

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            },
            timeout=self.timeout
        )

    def fetch_metadata(self, tiktok_url: str) -> Dict[str, Any]:
        """Fetch video metadata and stream links from TikWM REST API."""
        client = self._get_client()
        should_close = self._client is None

        try:
            response = client.post(
                self.BASE_URL,
                data={"url": tiktok_url, "hd": 1}
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                msg = data.get("msg", "Unknown error from TikWM")
                raise TikWMAPIError(f"TikWM API failed (code {data.get('code')}): {msg}")

            return data.get("data", {})
        finally:
            if should_close:
                client.close()

    def download_stream(self, stream_url: str, target_path: Path) -> Path:
        """Download binary video or image stream to target path in 64KB chunks."""
        client = self._get_client()
        should_close = self._client is None

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with client.stream("GET", stream_url) as resp:
                resp.raise_for_status()
                with open(target_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
            return target_path
        finally:
            if should_close:
                client.close()

    def extract(self, tiktok_url: str, staging_dir: Path) -> ExtractionResult:
        """Full extraction workflow: query TikWM, download video and thumbnail."""
        data = self.fetch_metadata(tiktok_url)

        video_id = str(data.get("id") or "unknown_id")
        video_url = data.get("hdplay") or data.get("play")
        if not video_url:
            raise TikWMAPIError("No playable video CDN stream returned by TikWM")

        # Destination paths
        video_path = staging_dir / f"{video_id}.mp4"
        thumbnail_path = staging_dir / f"{video_id}_thumb.jpg"

        # Download raw media
        self.download_stream(video_url, video_path)

        # Download thumbnail if available
        cover_url = data.get("cover")
        if cover_url:
            try:
                self.download_stream(cover_url, thumbnail_path)
            except Exception as e:
                logger.warning(f"Failed to download thumbnail from TikWM: {e}")
                thumbnail_path = None
        else:
            thumbnail_path = None

        author = data.get("author", {})

        return ExtractionResult(
            video_id=video_id,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            audio_path=None,  # Will be populated by FFmpegNormalizer
            caption=data.get("title", ""),
            creator_id=author.get("unique_id", "unknown_creator"),
            creator_nickname=author.get("nickname", ""),
            creator_bio=author.get("signature", ""),
            duration=float(data.get("duration", 0)),
            width=0,  # Will be inspected by FFmpegNormalizer
            height=0,
            engine_used="tikwm"
        )

