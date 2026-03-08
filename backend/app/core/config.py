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

    # Source strategy: seed | apify
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
    instagram_query: str = Field(
        default="reels trends",
        validation_alias=AliasChoices("INSTAGRAM_QUERY", "instagram_query"),
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
    apify_max_selector_terms: int = Field(
        default=3,
        validation_alias=AliasChoices("APIFY_MAX_SELECTOR_TERMS", "apify_max_selector_terms"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def seed_data_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data" / "seeds"

    @property
    def downloads_data_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data" / "downloads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
