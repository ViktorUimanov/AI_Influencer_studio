from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(
        default="Influencer Trends API",
        validation_alias=AliasChoices("APP_NAME", "app_name"),
    )
    app_env: str = Field(default="dev", validation_alias=AliasChoices("APP_ENV", "app_env"))
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/influencer",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    storage_mode: str = Field(
        default="db",
        validation_alias=AliasChoices("STORAGE_MODE", "storage_mode"),
    )
    workspace_data_dir_env: str | None = Field(
        default=None,
        validation_alias=AliasChoices("WORKSPACE_DATA_DIR", "workspace_data_dir"),
    )

    # Source strategy: seed | apify | tiktok_custom | instagram_custom
    default_source: str = Field(
        default="seed",
        validation_alias=AliasChoices("DEFAULT_SOURCE", "default_source"),
    )

    apify_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APIFY_TOKEN", "api_apify"),
    )
    tiktok_apify_actor: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TIKTOK_APIFY_ACTOR", "apify_tiktok_actor"),
    )
    instagram_apify_actor: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INSTAGRAM_APIFY_ACTOR", "apify_instagram_actor"),
    )
    tiktok_query: str = Field(
        default="viral videos",
        validation_alias=AliasChoices("TIKTOK_QUERY", "tiktok_query"),
    )
    tiktok_ms_tokens: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TIKTOK_MS_TOKENS", "tiktok_ms_tokens"),
    )
    tiktok_custom_headless: bool = Field(
        default=True,
        validation_alias=AliasChoices("TIKTOK_CUSTOM_HEADLESS", "tiktok_custom_headless"),
    )
    tiktok_custom_sessions: int = Field(
        default=1,
        validation_alias=AliasChoices("TIKTOK_CUSTOM_SESSIONS", "tiktok_custom_sessions"),
    )
    tiktok_custom_sleep_after: int = Field(
        default=3,
        validation_alias=AliasChoices("TIKTOK_CUSTOM_SLEEP_AFTER", "tiktok_custom_sleep_after"),
    )
    tiktok_custom_browser: str = Field(
        default="chromium",
        validation_alias=AliasChoices("TIKTOK_CUSTOM_BROWSER", "tiktok_custom_browser"),
    )
    instagram_query: str = Field(
        default="reels trends",
        validation_alias=AliasChoices("INSTAGRAM_QUERY", "instagram_query"),
    )
    instagram_custom_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INSTAGRAM_CUSTOM_USERNAME", "instagram_custom_username"),
    )
    instagram_custom_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INSTAGRAM_CUSTOM_PASSWORD", "instagram_custom_password"),
    )
    instagram_custom_session_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INSTAGRAM_CUSTOM_SESSION_FILE", "instagram_custom_session_file"),
    )
    instagram_custom_max_posts_per_tag: int = Field(
        default=120,
        validation_alias=AliasChoices("INSTAGRAM_CUSTOM_MAX_POSTS_PER_TAG", "instagram_custom_max_posts_per_tag"),
    )
    x_api_bearer_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("X_API_BEARER_TOKEN", "x_api_bearer_token"),
    )
    x_api_base_url: str = Field(
        default="https://api.x.com",
        validation_alias=AliasChoices("X_API_BASE_URL", "x_api_base_url"),
    )
    x_api_search_pages: int = Field(
        default=4,
        validation_alias=AliasChoices("X_API_SEARCH_PAGES", "x_api_search_pages"),
    )

    yt_dlp_command: str = Field(
        default="yt-dlp",
        validation_alias=AliasChoices("YT_DLP_COMMAND", "yt_dlp_command"),
    )
    yt_dlp_format: str = Field(
        default="bv*+ba/b",
        validation_alias=AliasChoices("YT_DLP_FORMAT", "yt_dlp_format"),
    )
    yt_dlp_merge_format: str = Field(
        default="mp4",
        validation_alias=AliasChoices("YT_DLP_MERGE_FORMAT", "yt_dlp_merge_format"),
    )
    yt_dlp_cookies_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("YT_DLP_COOKIES_FILE", "yt_dlp_cookies_file"),
    )
    download_timeout_sec: int = Field(
        default=900,
        validation_alias=AliasChoices("DOWNLOAD_TIMEOUT_SEC", "download_timeout_sec"),
    )
    db_fallback_to_sqlite: bool = Field(
        default=True,
        validation_alias=AliasChoices("DB_FALLBACK_TO_SQLITE", "db_fallback_to_sqlite"),
    )
    apify_fallback_to_seed: bool = Field(
        default=False,
        validation_alias=AliasChoices("APIFY_FALLBACK_TO_SEED", "apify_fallback_to_seed"),
    )
    apify_overfetch_multiplier: int = Field(
        default=1,
        validation_alias=AliasChoices("APIFY_OVERFETCH_MULTIPLIER", "apify_overfetch_multiplier"),
    )
    apify_cost_optimized: bool = Field(
        default=True,
        validation_alias=AliasChoices("APIFY_COST_OPTIMIZED", "apify_cost_optimized"),
    )
    apify_max_selector_terms: int = Field(
        default=1,
        validation_alias=AliasChoices("APIFY_MAX_SELECTOR_TERMS", "apify_max_selector_terms"),
    )
    apify_request_retries: int = Field(
        default=4,
        validation_alias=AliasChoices("APIFY_REQUEST_RETRIES", "apify_request_retries"),
    )
    apify_retry_backoff_sec: float = Field(
        default=1.5,
        validation_alias=AliasChoices("APIFY_RETRY_BACKOFF_SEC", "apify_retry_backoff_sec"),
    )
    apify_retry_max_backoff_sec: float = Field(
        default=12.0,
        validation_alias=AliasChoices("APIFY_RETRY_MAX_BACKOFF_SEC", "apify_retry_max_backoff_sec"),
    )
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def workspace_data_dir(self) -> Path:
        if self.workspace_data_dir_env:
            return Path(self.workspace_data_dir_env).expanduser().resolve()
        return (self.repo_root / "shared").resolve()

    @property
    def seed_data_dir(self) -> Path:
        return self.backend_root / "data" / "seeds"

    @property
    def downloads_data_dir(self) -> Path:
        return self.workspace_data_dir / "downloads"

    @property
    def influencers_data_dir(self) -> Path:
        return self.workspace_data_dir / "influencers"

    @property
    def pipeline_runs_data_dir(self) -> Path:
        return self.workspace_data_dir / "pipeline_runs"

    @property
    def generated_images_data_dir(self) -> Path:
        return self.workspace_data_dir / "generated_images"


@lru_cache
def get_settings() -> Settings:
    return Settings()
