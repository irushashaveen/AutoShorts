import os
from pathlib import Path
from typing import Any, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General App Config
    APP_NAME: str = "AutoShorts"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "default_development_secret_key_change_in_production"
    BASE_URL: str = "http://localhost:8000"

    # File System & Persistence
    DATA_DIR: Path = Path("./data")
    DATABASE_URL: str = "sqlite:///./data/database/autoshorts.db"
    MEDIA_STAGING_DIR: Path = Path("./data/media_staging")

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # AI Configuration (Primary: Google Gemini 1.5 Flash)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_TIMEOUT_SECONDS: float = 8.0

    # AI Configuration (Fallback: Local Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"

    # YouTube API & Quota
    YOUTUBE_CLIENT_SECRETS_FILE: Path = Path("./data/client_secrets.json")
    YOUTUBE_CREDENTIALS_FILE: Path = Path("./data/youtube_credentials.json")
    YOUTUBE_DAILY_QUOTA_LIMIT: int = 10000
    YOUTUBE_UPLOAD_QUOTA_COST: int = 1600
    DEFAULT_PUBLISH_HOUR_UTC: int = 15

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_USERS: Any = Field(default_factory=list)

    # Deduplication Thresholds
    DUP_RISK_THRESHOLD: float = 0.75
    WEIGHT_AUDIO_MATCH: float = 0.50
    WEIGHT_TFIDF_COSINE: float = 0.30
    WEIGHT_LEVENSHTEIN: float = 0.20

    @field_validator("TELEGRAM_ALLOWED_USERS", mode="before")
    @classmethod
    def parse_allowed_users(cls, v: Union[str, List[int], int]) -> List[int]:
        if isinstance(v, list):
            return [int(x) for x in v if str(x).strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(uid.strip()) for uid in v.split(",") if uid.strip().isdigit()]
        return []

    def ensure_directories(self) -> None:
        """Create necessary data and staging directories if they don't exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        (self.DATA_DIR / "database").mkdir(parents=True, exist_ok=True)
        self.MEDIA_STAGING_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()

