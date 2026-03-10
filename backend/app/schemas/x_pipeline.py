from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.x_content import XDraftOut, XPostOut, XTrendRunDetailOut


class XPipelineRunRequest(BaseModel):
    influencer_id: str = Field(..., min_length=1, max_length=128)
    mode: Literal["base_hashtags", "trending_hashtags"] = "base_hashtags"
    location_woeid: int = Field(default=1, ge=1)
    max_trending_topics: int = Field(default=100, ge=1, le=100)
    selected_topics_limit: int = Field(default=6, ge=1, le=20)
    max_posts_per_topic: int = Field(default=10, ge=1, le=50)
    max_total_posts: int = Field(default=30, ge=1, le=100)
    draft_limit: int = Field(default=3, ge=1, le=10)
    image_mode: Literal["any", "prefer", "required"] = "any"
    lang: str | None = Field(default="en", min_length=2, max_length=16)
    model: str = Field(default="gemini-3.1-flash-lite-preview", min_length=1, max_length=128)


class XPipelineRunOut(BaseModel):
    influencer_id: str
    mode: str
    candidate_topics: list[str] = Field(default_factory=list)
    selected_topics: list[str] = Field(default_factory=list)
    selection_rationale: str | None = None
    run: XTrendRunDetailOut
    top_posts: list[XPostOut] = Field(default_factory=list)
    drafts: list[XDraftOut] = Field(default_factory=list)
