from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.apify_source import ApifyTrendAdapter
from app.adapters.seed_source import SeedTrendAdapter
from app.adapters.types import RawTrendVideo, TrendFetchSelector
from app.core.config import Settings
from app.models import TrendItem, TrendRun, TrendSignal

VALID_PLATFORMS = {"tiktok", "instagram"}
VALID_SOURCES = {"seed", "apify"}

STOPWORDS = {
    "the",
    "and",
    "for",
    "you",
    "with",
    "this",
    "that",
    "from",
    "your",
    "have",
    "just",
    "when",
    "into",
    "over",
    "about",
    "what",
    "why",
    "how",
    "our",
    "are",
    "can",
    "its",
    "out",
    "new",
    "viral",
    "trend",
    "trending",
    "reel",
    "reels",
    "video",
    "videos",
}

STYLE_KEYWORDS = {
    "tutorial": ["how to", "tutorial", "step by step", "guide"],
    "before_after": ["before", "after", "transformation"],
    "day_in_life": ["day in my life", "ditl", "routine"],
    "behind_the_scenes": ["behind the scenes", "bts", "making of"],
    "listicle": ["top 3", "top 5", "top 10", "things"],
    "storytime": ["storytime", "plot twist", "what happened"],
}


class TrendParserService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def ingest(
        self,
        platforms: list[str],
        limit_per_platform: int,
        source: str | None = None,
        selectors: dict[str, dict] | None = None,
    ) -> TrendRun:
        platforms_normalized: list[str] = []
        seen = set()
        for platform in platforms:
            normalized = (platform or "").lower().strip()
            if normalized in VALID_PLATFORMS and normalized not in seen:
                platforms_normalized.append(normalized)
                seen.add(normalized)
        if not platforms_normalized:
            raise ValueError("No supported platforms provided. Use tiktok and/or instagram.")

        source_strategy = (source or self.settings.default_source).lower().strip()
        if source_strategy not in VALID_SOURCES:
            raise ValueError("Unsupported source. Use seed or apify.")
        selectors = selectors or {}
        run = TrendRun(
            status="running",
            source=source_strategy,
            platforms=platforms_normalized,
            selector_config=selectors,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            platform_videos: dict[str, list[RawTrendVideo]] = {}
            for platform in platforms_normalized:
                selector = TrendFetchSelector(**(selectors.get(platform) or {}))
                videos = self._fetch_videos(
                    platform=platform,
                    limit=limit_per_platform,
                    source=source_strategy,
                    selector=selector,
                )
                platform_videos[platform] = videos

                for video in videos:
                    trend_item = TrendItem(
                        run_id=run.id,
                        platform=platform,
                        source_item_id=video.source_item_id,
                        video_url=video.video_url,
                        caption=video.caption,
                        hashtags=video.hashtags,
                        audio=video.audio,
                        style_hint=video.style_hint,
                        published_at=video.published_at,
                        views=video.views,
                        likes=video.likes,
                        comments=video.comments,
                        shares=video.shares,
                        trending_score=self._score(video),
                        raw_payload=video.raw_payload,
                    )
                    self.db.add(trend_item)

            self.db.flush()

            extracted_signals = self._extract_signals(platform_videos)
            for signal in extracted_signals:
                self.db.add(
                    TrendSignal(
                        run_id=run.id,
                        platform=signal["platform"],
                        signal_type=signal["signal_type"],
                        value=signal["value"],
                        score=signal["score"],
                        signal_metadata=signal.get("metadata"),
                    )
                )

            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.summary = self._build_summary(platform_videos=platform_videos, extracted_signals=extracted_signals)
            self.db.commit()

        except Exception as exc:
            self.db.rollback()
            failed = self.db.get(TrendRun, run.id)
            if failed:
                failed.status = "failed"
                failed.completed_at = datetime.now(UTC)
                failed.error_message = str(exc)
                self.db.commit()
            raise

        return self.get_run(run.id)

    def list_runs(self, limit: int = 20) -> list[TrendRun]:
        stmt = select(TrendRun).order_by(desc(TrendRun.id)).limit(limit)
        return list(self.db.scalars(stmt))

    def get_run(self, run_id: int) -> TrendRun | None:
        stmt = (
            select(TrendRun)
            .where(TrendRun.id == run_id)
            .options(selectinload(TrendRun.items), selectinload(TrendRun.signals))
        )
        return self.db.scalar(stmt)

    def latest_for_platform(self, platform: str) -> TrendRun | None:
        stmt = (
            select(TrendRun)
            .where(TrendRun.status == "completed")
            .order_by(desc(TrendRun.id))
            .options(selectinload(TrendRun.items), selectinload(TrendRun.signals))
            .limit(50)
        )
        runs = list(self.db.scalars(stmt))
        for run in runs:
            if platform.lower() in (run.platforms or []):
                return run
        return None

    def list_items(
        self,
        platform: str | None = None,
        run_id: int | None = None,
        hashtag: str | None = None,
        query: str | None = None,
        min_views: int | None = None,
        limit: int = 50,
    ) -> list[TrendItem]:
        stmt = select(TrendItem).order_by(desc(TrendItem.trending_score), desc(TrendItem.id))
        if platform:
            stmt = stmt.where(TrendItem.platform == platform.lower())
        if run_id:
            stmt = stmt.where(TrendItem.run_id == run_id)
        if min_views is not None:
            stmt = stmt.where(TrendItem.views >= min_views)

        has_client_filters = bool(hashtag or query)
        candidate_limit = max(limit * 5, limit) if has_client_filters else limit
        items = list(self.db.scalars(stmt.limit(candidate_limit)))
        if not hashtag and not query:
            return items

        tag_normalized = (hashtag or "").lower().strip().lstrip("#")
        query_normalized = (query or "").lower().strip()
        filtered: list[TrendItem] = []
        for item in items:
            if tag_normalized:
                tags = [str(tag).lower().strip().lstrip("#") for tag in (item.hashtags or [])]
                if tag_normalized not in tags:
                    continue
            if query_normalized:
                haystack = f"{item.caption or ''} {' '.join(item.hashtags or [])}".lower()
                if query_normalized not in haystack:
                    continue
            filtered.append(item)
        return filtered[:limit]

    def list_signals(
        self,
        platform: str | None = None,
        signal_type: str | None = None,
        run_id: int | None = None,
        limit: int = 100,
    ) -> list[TrendSignal]:
        stmt = select(TrendSignal).order_by(desc(TrendSignal.score), desc(TrendSignal.id)).limit(limit)
        if platform:
            stmt = stmt.where(TrendSignal.platform == platform.lower())
        if signal_type:
            stmt = stmt.where(TrendSignal.signal_type == signal_type.lower())
        if run_id:
            stmt = stmt.where(TrendSignal.run_id == run_id)
        return list(self.db.scalars(stmt))

    def _fetch_videos(
        self,
        platform: str,
        limit: int,
        source: str,
        selector: TrendFetchSelector | None = None,
    ) -> list[RawTrendVideo]:
        selector = self._optimize_selector(selector)
        fetch_limit = limit
        if source == "seed":
            videos = SeedTrendAdapter(platform=platform, seed_dir=self.settings.seed_data_dir).fetch(
                limit=limit,
                selector=selector,
            )
            return self._select_top_videos(videos=videos, limit=limit)

        if source == "apify":
            # Over-fetch then rank to improve relevance (fresh + high-view videos).
            multiplier = max(int(self.settings.apify_overfetch_multiplier), 1)
            fetch_limit = min(max(limit * multiplier, limit), 200)
            actor_id = self.settings.tiktok_apify_actor if platform == "tiktok" else self.settings.instagram_apify_actor
            query = self.settings.tiktok_query if platform == "tiktok" else self.settings.instagram_query
            if not self.settings.apify_token or not actor_id:
                raise RuntimeError(
                    f"Apify source selected, but missing token/actor for platform={platform}. "
                    "Check APIFY_TOKEN and platform actor env."
                )
            try:
                videos = ApifyTrendAdapter(
                    token=self.settings.apify_token,
                    actor_id=actor_id,
                    platform=platform,
                    query=query,
                ).fetch(limit=fetch_limit, selector=selector)
                return self._select_top_videos(videos=videos, limit=limit)
            except Exception as exc:
                if self.settings.apify_fallback_to_seed:
                    videos = SeedTrendAdapter(platform=platform, seed_dir=self.settings.seed_data_dir).fetch(
                        limit=limit,
                        selector=selector,
                    )
                    return self._select_top_videos(videos=videos, limit=limit)
                raise RuntimeError(f"Apify fetch failed for platform={platform}: {exc}") from exc

        videos = SeedTrendAdapter(platform=platform, seed_dir=self.settings.seed_data_dir).fetch(
            limit=limit,
            selector=selector,
        )
        return self._select_top_videos(videos=videos, limit=limit)

    def _optimize_selector(self, selector: TrendFetchSelector | None) -> TrendFetchSelector | None:
        if selector is None:
            return None

        def _clean(items: list[str]) -> list[str]:
            seen: set[str] = set()
            output: list[str] = []
            for raw in items:
                item = str(raw or "").strip()
                if not item:
                    continue
                key = item.lower()
                if key in seen:
                    continue
                seen.add(key)
                output.append(item)
            return output

        hashtags = _clean(selector.hashtags)
        search_terms = _clean(selector.search_terms)

        max_terms = max(int(self.settings.apify_max_selector_terms), 1)
        hashtags = hashtags[:max_terms]
        search_terms = search_terms[:max_terms]

        return TrendFetchSelector(
            mode=selector.mode,
            search_terms=search_terms,
            hashtags=hashtags,
            min_views=selector.min_views,
            min_likes=selector.min_likes,
            source_params=selector.source_params,
        )

    def _score(self, video: RawTrendVideo) -> float:
        interactions = video.likes + video.comments + video.shares
        engagement = (interactions / video.views) if video.views > 0 else 0.0

        recency_boost = 0.3
        if video.published_at:
            published_utc = self._to_utc(video.published_at)
            hours_old = max((datetime.now(UTC) - published_utc).total_seconds() / 3600, 1)
            recency_boost = max(0.05, 1 / math.log(hours_old + 3, 10))

        reach_component = math.log(video.views + 1, 10)
        return round((reach_component * 0.65) + (engagement * 1.0) + (recency_boost * 0.9), 4)

    def _extract_signals(self, platform_videos: dict[str, list[RawTrendVideo]]) -> list[dict]:
        signals: list[dict] = []

        for platform, videos in platform_videos.items():
            hashtag_counter: Counter[str] = Counter()
            audio_counter: Counter[str] = Counter()
            topic_counter: Counter[str] = Counter()
            style_counter: Counter[str] = Counter()
            hook_counter: Counter[str] = Counter()

            for video in videos:
                weight = max(self._score(video), 0.1)

                for tag in video.hashtags:
                    clean_tag = tag.lower().strip().replace("#", "")
                    if clean_tag:
                        hashtag_counter[clean_tag] += weight

                if video.audio:
                    audio_counter[video.audio.lower().strip()] += weight

                caption = (video.caption or "").strip().lower()
                if caption:
                    for token in self._caption_tokens(caption):
                        topic_counter[token] += weight

                    hook = self._hook(caption)
                    if hook:
                        hook_counter[hook] += weight

                    style = video.style_hint or self._infer_style(caption)
                    if style:
                        style_counter[style.lower().strip()] += weight

            signals.extend(self._counter_to_signals(platform, "hashtag", hashtag_counter, top_n=12))
            signals.extend(self._counter_to_signals(platform, "audio", audio_counter, top_n=8))
            signals.extend(self._counter_to_signals(platform, "topic", topic_counter, top_n=12))
            signals.extend(self._counter_to_signals(platform, "style", style_counter, top_n=8))
            signals.extend(self._counter_to_signals(platform, "hook", hook_counter, top_n=8))

        return signals

    def _build_summary(self, platform_videos: dict[str, list[RawTrendVideo]], extracted_signals: list[dict]) -> dict:
        by_platform = defaultdict(lambda: {"videos": 0, "signals": defaultdict(list)})

        for platform, videos in platform_videos.items():
            by_platform[platform]["videos"] = len(videos)

        for signal in extracted_signals:
            by_platform[signal["platform"]]["signals"][signal["signal_type"]].append(
                {
                    "value": signal["value"],
                    "score": signal["score"],
                }
            )

        output = {"platforms": {}, "totals": {"videos": 0, "signals": len(extracted_signals)}}
        for platform, payload in by_platform.items():
            output["platforms"][platform] = {
                "videos": payload["videos"],
                "signals": dict(payload["signals"]),
            }
            output["totals"]["videos"] += payload["videos"]

        return output

    def _caption_tokens(self, caption: str) -> list[str]:
        tokens = [token for token in re.split(r"[^a-z0-9]+", caption) if token]
        return [t for t in tokens if len(t) >= 4 and t not in STOPWORDS]

    def _hook(self, caption: str) -> str | None:
        first_part = re.split(r"[.!?\n]", caption)[0].strip()
        if len(first_part) < 8:
            return None
        return first_part[:120]

    def _infer_style(self, caption: str) -> str | None:
        for style, keywords in STYLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in caption:
                    return style
        return None

    def _counter_to_signals(self, platform: str, signal_type: str, counter: Counter[str], top_n: int) -> list[dict]:
        return [
            {
                "platform": platform,
                "signal_type": signal_type,
                "value": value,
                "score": round(score, 4),
                "metadata": {"rank": idx + 1},
            }
            for idx, (value, score) in enumerate(counter.most_common(top_n))
        ]

    def _to_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _published_rank_value(self, published_at: datetime | None) -> float:
        if not published_at:
            return 0.0
        return self._to_utc(published_at).timestamp()

    def _select_top_videos(self, videos: list[RawTrendVideo], limit: int) -> list[RawTrendVideo]:
        ranked = sorted(
            videos,
            key=lambda video: (
                self._score(video),
                video.views,
                self._published_rank_value(video.published_at),
            ),
            reverse=True,
        )
        return ranked[:limit]
