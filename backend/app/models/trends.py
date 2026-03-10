from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrendRun(Base):
    __tablename__ = "trend_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    platforms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selector_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["TrendItem"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    signals: Mapped[list["TrendSignal"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class TrendItem(Base):
    __tablename__ = "trend_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("trend_runs.id"), nullable=False, index=True)

    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    audio: Mapped[str | None] = mapped_column(String(256), nullable=True)
    style_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trending_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped[TrendRun] = relationship(back_populates="items")
    downloads: Mapped[list["TrendDownload"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class TrendSignal(Base):
    __tablename__ = "trend_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("trend_runs.id"), nullable=False, index=True)

    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    signal_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    run: Mapped[TrendRun] = relationship(back_populates="signals")


class TrendDownload(Base):
    __tablename__ = "trend_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trend_item_id: Mapped[int] = mapped_column(ForeignKey("trend_items.id"), nullable=False, index=True)

    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", index=True)
    downloader: Mapped[str] = mapped_column(String(32), nullable=False, default="yt-dlp")

    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_ext: Mapped[str | None] = mapped_column(String(16), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    download_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    item: Mapped[TrendItem] = relationship(back_populates="downloads")


class PersonaRecord(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="Persona")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class InfluencerProfile(Base):
    __tablename__ = "influencers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    influencer_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="Influencer")
    reference_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    video_suggestions_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PictureIdea(Base):
    __tablename__ = "picture_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    influencer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platforms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_run_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    influencer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    picture_idea_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    reference_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_image_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class XTrendRun(Base):
    __tablename__ = "x_trend_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_woeid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    topics: Mapped[list["XTrendTopic"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    posts: Mapped[list["XPost"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    drafts: Mapped[list["XDraft"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class XTrendTopic(Base):
    __tablename__ = "x_trend_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("x_trend_runs.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    trend_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tweet_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped["XTrendRun"] = relationship(back_populates="topics")


class XPost(Base):
    __tablename__ = "x_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("x_trend_runs.id"), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    author_username: Mapped[str | None] = mapped_column(String(256), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at_x: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repost_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bookmark_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impression_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_images: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    popularity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped["XTrendRun"] = relationship(back_populates="posts")
    media_items: Mapped[list["XPostMedia"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class XPostMedia(Base):
    __tablename__ = "x_post_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_row_id: Mapped[int] = mapped_column(ForeignKey("x_posts.id"), nullable=False, index=True)
    media_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    media_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    post: Mapped["XPost"] = relationship(back_populates="media_items")


class XDraft(Base):
    __tablename__ = "x_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("x_trend_runs.id"), nullable=False, index=True)
    topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_post_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    image_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_pattern: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["XTrendRun"] = relationship(back_populates="drafts")
