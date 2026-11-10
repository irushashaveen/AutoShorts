import json
import logging
from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config import settings

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


class OAuthAuthenticationError(Exception):
    """Raised when Google OAuth refresh fails or credentials are invalid."""
    pass


class OAuthManager:
    """Manages headless OAuth 2.0 lifecycle and Google API service construction."""

    def __init__(
        self,
        credentials_file: Path = settings.YOUTUBE_CREDENTIALS_FILE,
        client_secrets_file: Path = settings.YOUTUBE_CLIENT_SECRETS_FILE,
    ):
        self.credentials_file = credentials_file
        self.client_secrets_file = client_secrets_file

    def get_credentials(self) -> Optional[Credentials]:
        """Load stored credentials and refresh token if expired."""
        if not self.credentials_file.exists():
            logger.warning(f"YouTube credentials file not found: {self.credentials_file}")
            return None

        try:
            creds = Credentials.from_authorized_user_file(
                str(self.credentials_file),
                scopes=YOUTUBE_SCOPES
            )

            if creds and creds.expired and creds.refresh_token:
                logger.info("YouTube OAuth access token expired. Refreshing token...")
                creds.refresh(Request())
                # Persist refreshed token
                with open(self.credentials_file, "w") as f:
                    f.write(creds.to_json())
                logger.info("OAuth token refreshed and persisted successfully.")

            return creds
        except Exception as e:
            logger.error(f"Failed to refresh or load OAuth credentials: {e}")
            raise OAuthAuthenticationError(f"OAuth credentials error: {e}") from e

    def build_youtube_client(self) -> object:
        """Construct authenticated YouTube Data API v3 client."""
        creds = self.get_credentials()
        if not creds:
            raise OAuthAuthenticationError("Valid YouTube OAuth credentials required.")
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def build_analytics_client(self) -> object:
        """Construct authenticated YouTube Analytics API v2 client."""
        creds = self.get_credentials()
        if not creds:
            raise OAuthAuthenticationError("Valid YouTube OAuth credentials required.")
        return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

