from typing import List
from pydantic import BaseModel, Field, field_validator


class AIMetadataOutput(BaseModel):
    """Schema enforced on Gemini 1.5 Flash and Ollama Qwen 2.5 completions."""
    title: str = Field(
        ...,
        description="Punchy, curiosity-inducing YouTube Shorts title under 60 characters with NO hashtags.",
        max_length=60
    )
    description: str = Field(
        ...,
        description="2 contextual sentences packed with search keywords, followed by creator attribution."
    )
    tags: List[str] = Field(
        ...,
        description="Exactly 3 high-volume search tags.",
        min_length=1,
        max_length=5
    )

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, v: str) -> str:
        if not isinstance(v, str):
            v = str(v)
        # Strip trailing/leading whitespace and any '#' symbols if model slipped
        cleaned = v.replace("#", "").strip()
        if len(cleaned) > 60:
            cleaned = cleaned[:57].rstrip() + "..."
        return cleaned

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, tags: List[str]) -> List[str]:
        if not isinstance(tags, list):
            return []
        cleaned = [str(t).lstrip("#").strip().lower() for t in tags if str(t).strip()]
        return cleaned[:3]

