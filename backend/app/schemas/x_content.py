from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class XCollectRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    location_woeid: int = Field(default=1, ge=1)
    max_topics: int = Field(default=10, ge=1, le=50)
    max_posts: int = Field(default=25, ge=1, le=100)
    result_type: str = Field(default="popular", pattern="^(popular|recent|mixed)$")
    only_with_images: bool = True
    lang: str | None = Field(default="en", min_length=2, max_length=16)


class XDraftGenerateRequest(BaseModel):
    run_id: int = Field(..., ge=1)
    limit: int = Field(default=3, ge=1, le=20)
    require_images: bool = True


class XTrendTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    name: str
    trend_url: str | None = None
    tweet_volume: int | None = None
    position: int | None = None
    raw_payload: dict | None = None


class XPostMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_row_id: int
    media_key: str | None = None
    media_type: str | None = None
    media_url: str | None = None
    preview_image_url: str | None = None
    width: int | None = None
    height: int | None = None
    alt_text: str | None = None
    raw_payload: dict | None = None


class XPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    post_id: str
    query: str | None = None
    author_id: str | None = None
    author_username: str | None = None
    author_name: str | None = None
    text: str
    lang: str | None = None
    conversation_id: str | None = None
    created_at_x: datetime | None = None
    like_count: int
    repost_count: int
    reply_count: int
    quote_count: int
    bookmark_count: int
    impression_count: int
    has_images: bool
    popularity_score: float
    permalink: str | None = None
    raw_payload: dict | None = None
    media_items: list[XPostMediaOut] = Field(default_factory=list)


class XDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    topic: str | None = None
    source_post_ids: list[str] | None = None
    title: str
    draft_text: str
    image_brief: str | None = None
    hook_pattern: str | None = None
    rationale: str | None = None
    score: float
    created_at: datetime


class XTrendRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    query: str | None = None
    location_woeid: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    summary: dict | None = None
    error_message: str | None = None


class XTrendRunDetailOut(XTrendRunOut):
    topics: list[XTrendTopicOut] = Field(default_factory=list)
    posts: list[XPostOut] = Field(default_factory=list)
    drafts: list[XDraftOut] = Field(default_factory=list)
