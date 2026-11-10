import re
from urllib.parse import urlparse, urlunparse
from typing import Optional
import httpx


class InvalidTikTokURLError(ValueError):
    """Raised when an incoming string is not a valid TikTok URL."""
    pass


TIKTOK_CANONICAL_PATTERN = re.compile(
    r"^https?://(?:www\.)?tiktok\.com/@([a-zA-Z0-9_\-\.]+)/video/(\d+)",
    re.IGNORECASE
)

SHORT_LINK_PATTERN = re.compile(
    r"^https?://(?:vm|vt)\.tiktok\.com/([a-zA-Z0-9_\-]+)",
    re.IGNORECASE
)


class URLSanitizer:
    """Sanitizes, validates, and normalizes TikTok incoming URLs."""

    @staticmethod
    def strip_tracking_params(url: str) -> str:
        """Strip mobile share tracking tokens like ?_t=..., &is_from_webapp=..., etc."""
        if not url:
            return ""
        parsed = urlparse(url.strip())
        clean_url = urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, "", "", ""))
        return clean_url.rstrip("/")

    @classmethod
    def validate_domain(cls, url: str) -> bool:
        """Assert whether domain is a legit TikTok domain."""
        if not url or not isinstance(url, str):
            return False
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        return bool(netloc.endswith("tiktok.com") or netloc == "tiktok.com")

    @classmethod
    def normalize_url(cls, raw_url: str, client: Optional[httpx.Client] = None) -> str:
        """
        Takes raw string from mobile or web share, strips params, resolves shortened
        redirects (vm.tiktok.com / vt.tiktok.com), and produces a clean canonical URL.
        """
        raw_url = raw_url.strip()
        if not raw_url.startswith(("http://", "https://")):
            raw_url = "https://" + raw_url

        if not cls.validate_domain(raw_url):
            raise InvalidTikTokURLError(f"Invalid domain: '{raw_url}' is not a legitimate TikTok domain.")

        # Check if it's a shortened redirect URL
        if SHORT_LINK_PATTERN.match(raw_url):
            close_client = False
            if client is None:
                client = httpx.Client(follow_redirects=True, timeout=10.0)
                close_client = True
            try:
                response = client.head(raw_url)
                if response.status_code in (301, 302, 303, 307, 308) or response.history:
                    raw_url = str(response.url)
                else:
                    with client.stream("GET", raw_url) as resp:
                        raw_url = str(resp.url)
            except Exception:
                pass
            finally:
                if close_client:
                    client.close()

        cleaned_url = cls.strip_tracking_params(raw_url)
        return cleaned_url

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video numeric ID if present in canonical URL."""
        match = TIKTOK_CANONICAL_PATTERN.search(url)
        if match:
            return match.group(2)
        digits = re.findall(r"/(\d{15,25})", url)
        if digits:
            return digits[0]
        return None

    @staticmethod
    def extract_username(url: str) -> Optional[str]:
        """Extract creator username if present in canonical URL."""
        match = TIKTOK_CANONICAL_PATTERN.search(url)
        if match:
            return match.group(1)
        return None
