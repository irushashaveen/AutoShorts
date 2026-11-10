from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Creator(Base):
    __tablename__ = "creators"

    id = Column(String(64), primary_key=True)  # TikTok unique_id (username)
    nickname = Column(String(128), nullable=True)
    bio = Column(Text, nullable=True)
    youtube_handle = Column(String(128), nullable=True, index=True)
    youtube_channel_id = Column(String(64), nullable=True)
    has_verified_yt_channel = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tasks = relationship("Task", back_populates="creator")

