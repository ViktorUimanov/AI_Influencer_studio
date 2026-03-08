from __future__ import annotations

import math
from datetime import datetime

import requests
from dateutil import parser

from app.adapters.types import RawTrendVideo, TrendFetchSelector


class ApifyTrendAdapter:
    def __init__(self, token: str, actor_id: str, platform: str, query: str):
        self.token = token
        self.actor_id = actor_id.replace("/", "~")
        self.platform = platform
        self.query = query
        self.base_url = "https://api.apify.com/v2"

    def fetch(self, limit: int, selector: TrendFetchSelector | None = None) -> list[RawTrendVideo]:
        actor_input = self._build_actor_input(limit=limit, selector=selector)
        run = self._start_actor_run(actor_input=actor_input)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []

        rows = self._read_dataset(dataset_id, limit)
        videos: list[RawTrendVideo] = []
        for row in rows:
            videos.extend(self._normalize_rows(row))

        # Deduplicate variants (e.g. parent post + carousel children) by source+URL.
        unique: dict[tuple[str, str], RawTrendVideo] = {}
        for video in videos:
            key = (
                (video.source_item_id or "").strip(),
                (video.video_url or "").strip(),
            )
            if key in unique:
                continue
            unique[key] = video
        return self._apply_post_filters(list(unique.values()), selector)

    def _start_actor_run(self, actor_input: dict) -> dict:
        endpoint = f"{self.base_url}/acts/{self.actor_id}/runs"
        params = {"waitForFinish": 120}
        headers = {"Authorization": f"Bearer {self.token}"}

        response = requests.post(endpoint, params=params, headers=headers, json=actor_input, timeout=140)
        response.raise_for_status()
        return response.json().get("data", {})

    def _read_dataset(self, dataset_id: str, limit: int) -> list[dict]:
        endpoint = f"{self.base_url}/datasets/{dataset_id}/items"
        params = {
            "clean": "true",
            "limit": limit,
            "format": "json",
        }
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(endpoint, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        return []

    def _normalize_row(self, row: dict) -> RawTrendVideo | None:
        video_url = row.get("videoUrl") or row.get("webVideoUrl")
        post_url = row.get("url") or row.get("webVideoUrl")
        caption = row.get("text") or row.get("caption") or row.get("description")

        hashtags = self._normalize_hashtags(row.get("hashtags") or [])
        if not hashtags:
            hashtags = self._extract_hashtags_from_caption(caption)

        media_type = str(row.get("type") or row.get("productType") or "").lower().strip()
        if self.platform == "instagram":
            has_video_hints = bool(
                video_url
                or row.get("videoViewCount")
                or row.get("videoPlayCount")
                or row.get("videoDuration")
                or row.get("audioUrl")
                or media_type in {"video", "reel", "clips"}
            )

            # For now we ingest only IG video posts/reels.
            if not has_video_hints:
                return None
            if not video_url:
                video_url = post_url

        published_at = None
        for candidate in ["createTimeISO", "timestamp", "publishedAt", "createTime"]:
            value = row.get(candidate)
            if not value:
                continue
            try:
                published_at = parser.parse(str(value))
                break
            except (ValueError, TypeError):
                continue

        stats = row.get("stats") or {}
        music_meta = row.get("musicMeta") or {}
        music_info = row.get("musicInfo") or {}

        views = self._first_int(
            row.get("playCount"),
            row.get("videoViewCount"),
            row.get("videoPlayCount"),
            row.get("igPlayCount"),
            stats.get("playCount"),
            row.get("views"),
            row.get("viewCount"),
            default=0,
        )
        likes = self._first_int(
            row.get("diggCount"),
            row.get("likesCount"),
            stats.get("diggCount"),
            row.get("likes"),
            default=0,
        )
        comments = self._first_int(
            row.get("commentCount"),
            row.get("commentsCount"),
            stats.get("commentCount"),
            row.get("comments"),
            default=0,
        )
        shares = self._first_int(
            row.get("shareCount"),
            stats.get("shareCount"),
            row.get("shares"),
            default=0,
        )
        views = max(0, views)
        likes = max(0, likes)
        comments = max(0, comments)
        shares = max(0, shares)

        return RawTrendVideo(
            platform=self.platform,
            source_item_id=str(row.get("id") or row.get("shortCode") or ""),
            video_url=video_url or post_url,
            caption=caption,
            hashtags=[str(h).strip("#") for h in hashtags if h],
            audio=(
                row.get("musicName")
                or row.get("audioName")
                or row.get("music")
                or music_meta.get("musicName")
                or music_meta.get("title")
                or music_info.get("song_name")
                or music_info.get("artist_name")
                or None
            ),
            style_hint=row.get("type") or row.get("contentType") or None,
            published_at=published_at,
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            raw_payload=row,
        )

    def _normalize_rows(self, row: dict) -> list[RawTrendVideo]:
        normalized: list[RawTrendVideo] = []
        parent = self._normalize_row(row)
        if parent is not None:
            normalized.append(parent)

        if self.platform != "instagram":
            return normalized

        child_posts = row.get("childPosts")
        if not isinstance(child_posts, list):
            return normalized

        for child in child_posts:
            if not isinstance(child, dict):
                continue
            merged_child = self._merge_instagram_child_row(parent=row, child=child)
            child_video = self._normalize_row(merged_child)
            if child_video is not None:
                normalized.append(child_video)

        return normalized

    def _merge_instagram_child_row(self, parent: dict, child: dict) -> dict:
        merged = dict(parent)
        merged.update(child)

        # Child records in IG sidecars often miss these fields; inherit from parent post.
        for key in ["url", "shortCode", "ownerId", "ownerUsername", "ownerFullName", "musicInfo"]:
            if merged.get(key) is None:
                merged[key] = parent.get(key)
        if not merged.get("caption"):
            merged["caption"] = parent.get("caption")
        if not merged.get("hashtags"):
            merged["hashtags"] = parent.get("hashtags")
        if merged.get("likesCount") is None:
            merged["likesCount"] = parent.get("likesCount")
        if merged.get("commentsCount") is None:
            merged["commentsCount"] = parent.get("commentsCount")
        if merged.get("timestamp") is None:
            merged["timestamp"] = parent.get("timestamp")
        return merged

    def _build_actor_input(self, limit: int, selector: TrendFetchSelector | None) -> dict:
        actor = self.actor_id.lower()
        if "clockworks~tiktok-scraper" in actor:
            return self._build_tiktok_actor_input(limit=limit, selector=selector)
        if "instagram-api-scraper" in actor or "instagram-scraper" in actor:
            return self._build_instagram_api_actor_input(limit=limit, selector=selector)

        query = self._selector_query(selector)
        actor_input: dict = {
            "search": query,
            "resultsLimit": limit,
        }
        if selector and selector.source_params:
            actor_input.update(selector.source_params)
            actor_input.setdefault("resultsLimit", limit)
            actor_input.setdefault("search", query)
        return actor_input

    def _selector_query(self, selector: TrendFetchSelector | None) -> str:
        if selector is None:
            return self.query

        mode = (selector.mode or "auto").lower().strip()
        tags = [f"#{str(tag).strip().lstrip('#')}" for tag in selector.hashtags if str(tag).strip()]
        terms = [str(term).strip() for term in selector.search_terms if str(term).strip()]

        if mode == "hashtag" and tags:
            return " ".join(tags)
        if mode == "search" and terms:
            return " ".join(terms)
        if mode == "mixed":
            mixed = [*tags, *terms]
            if mixed:
                return " ".join(mixed)

        fallback = [*tags, *terms]
        if fallback:
            return " ".join(fallback)
        return self.query

    def _build_tiktok_actor_input(self, limit: int, selector: TrendFetchSelector | None) -> dict:
        hashtags = [str(tag).strip().lstrip("#") for tag in (selector.hashtags if selector else []) if str(tag).strip()]
        terms = [str(term).strip() for term in (selector.search_terms if selector else []) if str(term).strip()]
        source_count = len(hashtags) if hashtags else len(terms) if terms else 1
        per_source_limit = max(1, math.ceil(limit / source_count))

        actor_input: dict = {
            # This actor applies "per hashtag/profile/search" pagination. Keep total near the requested limit.
            "resultsPerPage": per_source_limit,
            "resultsLimit": limit,
        }
        if hashtags:
            actor_input["hashtags"] = hashtags
        elif terms:
            actor_input["searchQueries"] = terms
            actor_input["searchSection"] = "/video"
        else:
            actor_input["searchQueries"] = [self.query]
            actor_input["searchSection"] = "/video"

        if selector and selector.source_params:
            actor_input.update(selector.source_params)
            actor_input.setdefault("resultsLimit", limit)
        return actor_input

    def _build_instagram_api_actor_input(self, limit: int, selector: TrendFetchSelector | None) -> dict:
        hashtags = [str(tag).strip().lstrip("#") for tag in (selector.hashtags if selector else []) if str(tag).strip()]
        terms = [str(term).strip() for term in (selector.search_terms if selector else []) if str(term).strip()]

        def to_tag_url(tag: str) -> str:
            slug = "".join(ch for ch in tag.lower() if ch.isalnum() or ch == "_")
            return f"https://www.instagram.com/explore/tags/{slug}/"

        actor_input: dict = {
            # Prototype target is IG videos/reels only.
            "resultsType": "reels",
            "resultsLimit": limit,
        }

        if hashtags:
            actor_input["directUrls"] = [to_tag_url(tag) for tag in hashtags]
        elif terms:
            actor_input["directUrls"] = [to_tag_url(term.replace(" ", "")) for term in terms]
        else:
            actor_input["search"] = self.query
            actor_input["searchType"] = "hashtag"
            actor_input["searchLimit"] = max(limit, 1)

        if selector and selector.source_params:
            actor_input.update(selector.source_params)
            actor_input.setdefault("resultsLimit", limit)
            actor_input.setdefault("resultsType", "reels")
        return actor_input

    def _apply_post_filters(
        self,
        videos: list[RawTrendVideo],
        selector: TrendFetchSelector | None,
    ) -> list[RawTrendVideo]:
        if selector is None:
            return videos

        min_views = selector.min_views
        min_likes = selector.min_likes
        if min_views is None and min_likes is None:
            return videos

        filtered: list[RawTrendVideo] = []
        for video in videos:
            if min_views is not None and video.views < min_views:
                continue
            if min_likes is not None and video.likes < min_likes:
                continue
            filtered.append(video)
        return filtered

    def _normalize_hashtags(self, hashtags: list | str) -> list[str]:
        if isinstance(hashtags, str):
            return [tag.strip("#") for tag in hashtags.split() if tag.startswith("#")]
        if not isinstance(hashtags, list):
            return []

        output: list[str] = []
        for tag in hashtags:
            if isinstance(tag, str):
                clean = tag.strip().lstrip("#")
                if clean:
                    output.append(clean)
                continue
            if isinstance(tag, dict):
                value = tag.get("name") or tag.get("tag") or tag.get("hash")
                if value:
                    output.append(str(value).strip().lstrip("#"))
        return output

    def _extract_hashtags_from_caption(self, caption: str | None) -> list[str]:
        if not caption:
            return []
        return [token.strip().lstrip("#") for token in caption.split() if token.startswith("#")]

    def _first_int(self, *values, default: int = 0) -> int:
        for value in values:
            parsed = self._to_int(value)
            if parsed is not None:
                return parsed
        return default

    def _to_int(self, value) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            raw = value.strip().lower()
            if not raw:
                return None
            multiplier = 1
            if raw.endswith("k"):
                multiplier = 1_000
                raw = raw[:-1]
            elif raw.endswith("m"):
                multiplier = 1_000_000
                raw = raw[:-1]
            elif raw.endswith("b"):
                multiplier = 1_000_000_000
                raw = raw[:-1]
            raw = raw.replace(",", "").replace(" ", "")
            try:
                return int(float(raw) * multiplier)
            except ValueError:
                return None
        return None
