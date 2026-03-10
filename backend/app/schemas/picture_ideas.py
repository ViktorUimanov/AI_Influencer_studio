from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GeneratePictureIdeasRequest(BaseModel):
    influencer_id: str = Field(..., min_length=1, max_length=128)
    platforms: list[str] = Field(default_factory=lambda: ["tiktok", "instagram"])
    limit: int = Field(default=6, ge=1, le=50)
    run_ids: list[int] = Field(default_factory=list)


class PictureIdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    influencer_id: str
    platforms: list[str]
    source_run_ids: list[int] | None = None
    title: str
    prompt: str
    hashtags: list[str] | None = None
    score: float
    rationale: str | None = None
    created_at: datetime

