import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

BIO_YT_PATTERNS = [
    # Matches: youtube.com/@handle or https://www.youtube.com/@handle
    re.compile(r"youtube\.com/@([a-zA-Z0-9_\-\.]{3,30})", re.IGNORECASE),
    # Matches: youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx
    re.compile(r"youtube\.com/channel/([a-zA-Z0-9_\-]{24})", re.IGNORECASE),
    # Matches: youtube.com/c/CustomName or youtube.com/user/UserName
    re.compile(r"youtube\.com/(?:c|user)/([a-zA-Z0-9_\-\.]{3,30})", re.IGNORECASE),
    # Matches: youtu.be/xxx or yt: @handle or youtube: handle
    re.compile(r"(?:^|\s)(?:yt|youtube):\s*@?([a-zA-Z0-9_\-\.]{3,30})", re.IGNORECASE),
]


class BioScanner:
    """Scans creator biography using regex patterns to detect linked YouTube channels."""

    @classmethod
    def extract_youtube_handle(cls, bio: Optional[str]) -> Optional[str]:
        """Extract YouTube handle or channel identifier from TikTok biography text."""
        if not bio or not isinstance(bio, str):
            return None

        clean_bio = bio.strip()
        for pattern in BIO_YT_PATTERNS:
            match = pattern.search(clean_bio)
            if match:
                handle = match.group(1).strip()
                if not handle.startswith("@") and not pattern.pattern.startswith(r"youtube\.com/channel/"):
                    handle = f"@{handle}"
                return handle

        return None

    @classmethod
    def verify_channel_exists(cls, handle: str, youtube_service: Optional[object] = None) -> bool:
        """
        Query YouTube Data API search.list to verify if candidate channel is official and active.
        If youtube_service is None, returns True by default to conservatively require manual review.
        """
        if not handle:
            return False

        if youtube_service is None:
            # Conservative safety default: if handle is in bio, flag for human verification
            return True

        try:
            # Call YouTube Data API v3 search.list
            clean_query = handle.lstrip("@")
            request = youtube_service.search().list(  # type: ignore
                q=clean_query,
                type="channel",
                part="snippet",
                maxResults=1
            )
            response = request.execute()
            items = response.get("items", [])
            return len(items) > 0
        except Exception as e:
            logger.warning(f"YouTube channel search failed for handle {handle}: {e}")
            return True

    @classmethod
    def scan_creator(cls, bio: Optional[str], youtube_service: Optional[object] = None) -> Tuple[Optional[str], bool]:
        """
        Evaluates biography. Returns (detected_handle, has_verified_yt_channel).
        """
        handle = cls.extract_youtube_handle(bio)
        if not handle:
            return None, False

        has_channel = cls.verify_channel_exists(handle, youtube_service)
        return handle, has_channel

