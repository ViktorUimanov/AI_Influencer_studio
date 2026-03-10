from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrendSelectorIn(BaseModel):
    mode: str = Field(default="auto", pattern="^(auto|search|hashtag|mixed)$")
    search_terms: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    min_views: int | None = Field(default=None, ge=0)
    min_likes: int | None = Field(default=None, ge=0)
    published_within_days: int | None = Field(default=None, ge=1, le=3650)
    require_topic_match: bool = False
    source_params: dict | None = None


class IngestTrendsRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["tiktok", "instagram"])
    limit_per_platform: int = Field(default=20, ge=1, le=200)
    source: str | None = Field(default=None, pattern="^(seed|apify|tiktok_custom|instagram_custom)$")
    selectors: dict[str, TrendSelectorIn] = Field(default_factory=dict)


class TrendSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    platform: str
    signal_type: str
    value: str
    score: float
    metadata: dict | None = Field(default=None, alias="signal_metadata")


class TrendItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    source_item_id: str | None = None
    video_url: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    audio: str | None = None
    style_hint: str | None = None
    published_at: datetime | None = None
    views: int
    likes: int
    comments: int
    shares: int
    trending_score: float


class TrendRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    source: str
    platforms: list[str]
    selector_config: dict | None = None
    started_at: datetime
    completed_at: datetime | None = None
    summary: dict | None = None
    error_message: str | None = None


class TrendRunDetailOut(TrendRunOut):
    model_config = ConfigDict(from_attributes=True)

    items: list[TrendItemOut]
    signals: list[TrendSignalOut]


class DownloadItemRequest(BaseModel):
    force: bool = False
    download_dir: str | None = None


class DownloadRunRequest(BaseModel):
    run_id: int = Field(..., ge=1)
    platform: str | None = Field(default=None, pattern="^(tiktok|instagram)$")
    limit: int = Field(default=20, ge=1, le=200)
    force: bool = False
    download_dir: str | None = None


class TrendDownloadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    trend_item_id: int
    platform: str
    source_url: str
    status: str
    downloader: str

    local_path: str | None = None
    file_ext: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None

    attempted_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    metadata: dict | None = Field(default=None, alias="download_metadata")
