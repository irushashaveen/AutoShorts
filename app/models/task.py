import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class TaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    VERIFYING = "VERIFYING"
    FLAGGED_CREATOR_CHANNEL = "FLAGGED_CREATOR_CHANNEL"
    DUPLICATE_SUSPECT = "DUPLICATE_SUSPECT"
    OPTIMIZING = "OPTIMIZING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    SCHEDULED = "SCHEDULED"
    UPLOADING = "UPLOADING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    FAILED_EXTRACTION = "FAILED_EXTRACTION"
    FAILED_OPTIMIZATION = "FAILED_OPTIMIZATION"
    FAILED_UPLOAD = "FAILED_UPLOAD"
    PAUSED_QUOTA = "PAUSED_QUOTA"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_url = Column(Text, nullable=False)
    normalized_url = Column(Text, nullable=False, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.QUEUED, nullable=False, index=True)

    # TikTok Media & Creator Info
    tiktok_video_id = Column(String(64), nullable=True, index=True)
    creator_id = Column(String(64), ForeignKey("creators.id"), nullable=True)
    raw_caption = Column(Text, nullable=True)

    # Staged Files
    media_path = Column(Text, nullable=True)
    thumbnail_path = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Verification & Risk
    duplicate_risk_score = Column(Float, default=0.0)
    audio_match_score = Column(Float, default=0.0)
    text_cosine_score = Column(Float, default=0.0)
    levenshtein_score = Column(Float, default=0.0)

    # AI Generated Metadata
    ai_title = Column(String(100), nullable=True)
    ai_description = Column(Text, nullable=True)
    ai_tags = Column(Text, nullable=True)  # JSON-encoded array: ["tag1", "tag2", "tag3"]
    ai_engine_used = Column(String(32), nullable=True)  # "gemini-1.5-flash" or "ollama-qwen2.5:3b"

    # YouTube Publishing
    youtube_video_id = Column(String(64), nullable=True, index=True)
    upload_progress_percent = Column(Float, default=0.0)
    scheduled_publish_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True)

    # Audit & Errors
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    creator = relationship("Creator", back_populates="tasks")
    fingerprints = relationship("AudioFingerprint", back_populates="task", cascade="all, delete-orphan")
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    quota_logs = relationship("YouTubeQuotaLog", back_populates="task")

