from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field
from app.models.task import TaskStatus


class TaskSubmitRequest(BaseModel):
    """Payload received when submitting a TikTok link via Web UI or API."""
    url: str = Field(..., description="Raw TikTok link (desktop or mobile share URL)")


class TaskMetadataUpdateRequest(BaseModel):
    """Payload for operator inline editing of title and description."""
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class CreatorResponse(BaseModel):
    id: str
    nickname: Optional[str] = None
    bio: Optional[str] = None
    youtube_handle: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    has_verified_yt_channel: bool = False

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: str
    source_url: str
    normalized_url: str
    status: TaskStatus
    tiktok_video_id: Optional[str] = None
    creator: Optional[CreatorResponse] = None
    raw_caption: Optional[str] = None
    media_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duplicate_risk_score: float = 0.0
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[str] = None
    ai_engine_used: Optional[str] = None
    youtube_video_id: Optional[str] = None
    upload_progress_percent: float = 0.0
    scheduled_publish_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

