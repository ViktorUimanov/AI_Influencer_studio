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
