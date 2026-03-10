from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateImageRequest(BaseModel):
    influencer_id: str = Field(..., min_length=1, max_length=128)
    prompt: str = Field(default="", max_length=8000)
    picture_idea_id: int | None = Field(default=None, ge=1)
    reference_image_path: str | None = None
    model: str = "gemini-2.5-flash-image"
    api_key_env: str = Field(default="GEMINI_API_KEY", min_length=1, max_length=128)
    aspect_ratio: str = "9:16"
    hashtag_strategy: str = Field(default="mixed", pattern="^(base|trending|mixed)$")
    hashtag_platforms: list[str] = Field(default_factory=lambda: ["instagram"])
    trend_run_ids: list[int] = Field(default_factory=list)
    trend_window_days: int = Field(default=7, ge=1, le=365)
    max_hashtags: int = Field(default=6, ge=1, le=20)
    mock: bool = False


class GeneratedImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    influencer_id: str
    picture_idea_id: int | None = None
    model: str
    prompt: str
    hashtags: list[str] | None = None
    reference_image_path: str | None = None
    output_image_path: str
    mime_type: str | None = None
    created_at: datetime
