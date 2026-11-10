from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExtractionResult:
    """Unified container for extracted media and author metadata."""
    video_id: str
    video_path: Path
    thumbnail_path: Optional[Path]
    audio_path: Optional[Path]
    caption: str
    creator_id: str  # TikTok unique_id (username)
    creator_nickname: str
    creator_bio: str
    duration: float
    width: int
    height: int
    engine_used: str  # "yt-dlp" or "tikwm"

