from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.generated_images import GeneratedImageOut
from app.schemas.trends import TrendSelectorIn


class PlatformPipelineConfigIn(BaseModel):
    enabled: bool = True
    source: str = Field(..., pattern="^(seed|apify|tiktok_custom|instagram_custom)$")
    limit: int = Field(default=20, ge=1, le=200)
    selector: TrendSelectorIn = Field(default_factory=TrendSelectorIn)


class DownloadStageConfigIn(BaseModel):
    enabled: bool = True
    force: bool = False


class FilterStageConfigIn(BaseModel):
    enabled: bool = True
    probe_seconds: int = Field(default=8, ge=3, le=120)
    workers: int = Field(default=4, ge=1, le=32)
    top_k: int = Field(default=15, ge=1, le=200)


class VlmThresholdsIn(BaseModel):
    min_readiness: float = 7.0
    min_confidence: float = 0.70
    min_persona_fit: float = 6.5
    max_occlusion_risk: float = 6.0
    max_scene_cut_complexity: float = 6.0


class VlmStageConfigIn(BaseModel):
    enabled: bool = True
    model: str = "gemini-3.1-flash-lite-preview"
    api_key_env: str = "GEMINI_API_KEY"
    timeout_sec: int = Field(default=300, ge=30, le=3600)
    mock: bool = False
    max_videos: int = Field(default=15, ge=1, le=200)
    theme: str = "influencer channel"
    sync_folders: bool = True
    thresholds: VlmThresholdsIn = Field(default_factory=VlmThresholdsIn)


class ImageStageConfigIn(BaseModel):
    enabled: bool = False
    prompt: str = Field(default="", max_length=8000)
    picture_idea_id: int | None = Field(default=None, ge=1)
    reference_image_path: str | None = None
    model: str = "gemini-2.5-flash-image"
    api_key_env: str = "GEMINI_API_KEY"
    aspect_ratio: str = "9:16"
    hashtag_strategy: str = Field(default="mixed", pattern="^(base|trending|mixed)$")
    hashtag_platforms: list[str] = Field(default_factory=lambda: ["instagram"])
    trend_run_ids: list[int] = Field(default_factory=list)
    trend_window_days: int = Field(default=7, ge=1, le=365)
    max_hashtags: int = Field(default=6, ge=1, le=20)
    mock: bool = False


class PipelineRunRequest(BaseModel):
    influencer_id: str = Field(..., min_length=1, max_length=128)
    platforms: dict[str, PlatformPipelineConfigIn] = Field(default_factory=dict)
    download: DownloadStageConfigIn = Field(default_factory=DownloadStageConfigIn)
    filter: FilterStageConfigIn = Field(default_factory=FilterStageConfigIn)
    vlm: VlmStageConfigIn = Field(default_factory=VlmStageConfigIn)
    image: ImageStageConfigIn = Field(default_factory=ImageStageConfigIn)


class PipelinePlatformRunOut(BaseModel):
    platform: str
    source: str
    trend_run_id: int
    ingested_items: int
    download_counts: dict[str, int]
    candidate_report_path: str | None = None
    filtered_dir: str | None = None
    vlm_summary_path: str | None = None
    selected_dir: str | None = None
    accepted: int | None = None
    rejected: int | None = None


class PipelineRunOut(BaseModel):
    influencer_id: str
    started_at: datetime
    base_dir: str
    platforms: list[PipelinePlatformRunOut]
    generated_images: list[GeneratedImageOut] = Field(default_factory=list)
