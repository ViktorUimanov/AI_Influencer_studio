from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InfluencerUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)
    hashtags: list[str] = Field(default_factory=list)
    video_suggestions_requirement: str = Field(..., min_length=1)
    reference_image_path: str | None = None


class InfluencerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    influencer_id: str
    name: str
    reference_image_path: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    video_suggestions_requirement: str | None = None
    created_at: datetime
    updated_at: datetime


class InfluencerStatusOut(InfluencerOut):
    onboarding_complete: bool
