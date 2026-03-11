from __future__ import annotations

import math
import re
import time
from datetime import UTC, datetime

import requests
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models import XDraft, XPost, XPostMedia, XTrendRun, XTrendTopic

HEALTH_QUERY_EXPANSIONS = {
    "healthy lifestyle": [
        "healthy lifestyle",
        "wellness routine",
        "healthy habits",
        "nutrition tips",
        "meal prep",
        "high protein meals",
        "fitness routine",
    ],
    "health": [
        "healthy habits",
        "wellness",
        "nutrition",
        "meal prep",
        "fitness tips",
    ],
}

PROMO_PATTERNS = [
    "buy now",
    "discount",
    "order now",
    "sign up",
    "subscribe",
    "link in bio",
    "shop now",
    "dm me",
    "android",
    "ios",
    "app store",
    "google play",
    "solution kit",
    "affiliate",
    "coupon",
]


class XContentService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def collect(self, *, query: str, location_woeid: int, max_topics: int, max_posts: int, result_type: str, only_with_images: bool, lang: str | None) -> XTrendRun:
        normalized_query = self._normalize_query(query)
        if not normalized_query:
            raise ValueError("query is required")
        if not self.settings.x_api_bearer_token:
            raise ValueError("Missing X_API_BEARER_TOKEN")

        run = XTrendRun(status="running", query=normalized_query, location_woeid=location_woeid)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            topics: list[dict] = []
            try:
                topics = self._fetch_trending_topics(location_woeid=location_woeid, max_topics=max_topics)
            except requests.HTTPError as exc:
                response = getattr(exc, "response", None)
                if response is None or response.status_code not in {403, 404}:
                    raise
            for idx, topic in enumerate(topics, start=1):
                self.db.add(
                    XTrendTopic(
                        run_id=run.id,
                        name=str(topic.get("name") or "").strip(),
                        trend_url=topic.get("url"),
                        tweet_volume=self._to_int(topic.get("tweet_volume")),
                        position=idx,
                        raw_payload=topic,
                    )
                )

            posts = self._fetch_posts(
                query=normalized_query,
                max_posts=max_posts,
                result_type=result_type,
                only_with_images=only_with_images,
                lang=lang,
            )
            for post in posts:
                media_payloads = post.pop("media_payloads", [])
                post_row = XPost(run_id=run.id, **post)
                self.db.add(post_row)
                self.db.flush()
                for media in media_payloads:
                    self.db.add(XPostMedia(post_row_id=post_row.id, **media))

            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.summary = {
                "topics": len(topics),
                "posts": len(posts),
                "with_images": sum(1 for post in posts if bool(post.get("has_images"))),
                "result_type": result_type,
                "search_queries": self._build_search_queries(query=normalized_query, only_with_images=only_with_images, lang=lang),
            }
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            failed = self.db.get(XTrendRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.completed_at = datetime.now(UTC)
                failed.error_message = str(exc)
                self.db.commit()
            raise

        return self.get_run(run.id)

    def list_runs(self, limit: int = 20) -> list[XTrendRun]:
        stmt = select(XTrendRun).order_by(desc(XTrendRun.id)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_trending_topics(self, *, location_woeid: int, max_topics: int) -> list[dict]:
        if not self.settings.x_api_bearer_token:
            raise ValueError("Missing X_API_BEARER_TOKEN")
        return self._fetch_trending_topics(location_woeid=location_woeid, max_topics=max_topics)

    def search_posts_for_topics(
        self,
        *,
        topics: list[str],
        max_posts_per_topic: int,
        max_total_posts: int,
        lang: str | None,
        image_mode: str = "any",
    ) -> list[dict]:
        if not self.settings.x_api_bearer_token:
            raise ValueError("Missing X_API_BEARER_TOKEN")

        normalized_topics: list[str] = []
        seen_topics: set[str] = set()
        for raw in topics:
            topic = self._normalize_query(raw)
            if not topic:
                continue
            key = topic.lower()
            if key in seen_topics:
                continue
            seen_topics.add(key)
            normalized_topics.append(topic)

        aggregated: dict[str, dict] = {}
        for topic in normalized_topics:
            search_query = self._compose_topic_search_query(topic=topic, lang=lang, image_mode=image_mode)
            batch = self._fetch_posts_v2(
                search_query=search_query,
                logical_query=topic,
                max_posts=min(max(max_posts_per_topic, 10), 50),
            )
            for post in batch:
                if self._is_sparse_post(post):
                    continue
                score = post["popularity_score"] + self._topic_post_bonus(post=post, image_mode=image_mode)
                post["popularity_score"] = round(score, 4)
                existing = aggregated.get(post["post_id"])
                if existing is None or post["popularity_score"] > existing["popularity_score"]:
                    aggregated[post["post_id"]] = post

        posts = list(aggregated.values())
        posts.sort(
            key=lambda item: (
                item["popularity_score"],
                item["impression_count"],
                item["like_count"],
                item["repost_count"],
            ),
            reverse=True,
        )
        return posts[:max_total_posts]

    def get_run(self, run_id: int) -> XTrendRun | None:
        stmt = (
            select(XTrendRun)
            .where(XTrendRun.id == run_id)
            .options(
                selectinload(XTrendRun.topics),
                selectinload(XTrendRun.posts).selectinload(XPost.media_items),
                selectinload(XTrendRun.drafts),
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_posts(self, *, run_id: int | None = None, only_with_images: bool = False, limit: int = 50) -> list[XPost]:
        stmt = (
            select(XPost)
            .options(selectinload(XPost.media_items))
            .order_by(desc(XPost.popularity_score), desc(XPost.id))
            .limit(limit)
        )
        if run_id is not None:
            stmt = stmt.where(XPost.run_id == run_id)
        if only_with_images:
            stmt = stmt.where(XPost.has_images.is_(True))
        return list(self.db.execute(stmt).scalars().all())

    def list_topics(self, *, run_id: int | None = None, limit: int = 50) -> list[XTrendTopic]:
        stmt = select(XTrendTopic).order_by(XTrendTopic.position.asc(), desc(XTrendTopic.id)).limit(limit)
        if run_id is not None:
            stmt = stmt.where(XTrendTopic.run_id == run_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_drafts(self, *, run_id: int | None = None, limit: int = 50) -> list[XDraft]:
        stmt = select(XDraft).order_by(desc(XDraft.score), desc(XDraft.id)).limit(limit)
        if run_id is not None:
            stmt = stmt.where(XDraft.run_id == run_id)
        return list(self.db.execute(stmt).scalars().all())

    def generate_drafts(self, *, run_id: int, limit: int, require_images: bool) -> list[XDraft]:
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"X trend run not found: {run_id}")

        topic_names = [topic.name for topic in run.topics if topic.name]
        topic_hint = self._pick_topic_hint(topic_names=topic_names, query=run.query or "")
        posts = sorted(run.posts, key=lambda post: (post.popularity_score, post.like_count), reverse=True)
        if require_images:
            posts = [post for post in posts if post.has_images]
        if not posts:
            raise ValueError("No matching X posts available for draft generation.")

        created: list[XDraft] = []
        seen_titles: set[str] = set()
        for post in posts:
            pattern = self._detect_hook_pattern(post.text)
            title = self._build_title(topic_hint=topic_hint, pattern=pattern)
            if title in seen_titles:
                continue
            seen_titles.add(title)

            draft_text = self._build_draft_text(post=post, topic_hint=topic_hint, pattern=pattern)
            image_brief = self._build_image_brief(post=post, topic_hint=topic_hint)
            rationale = (
                f"Adapted from high-performing X post {post.post_id} "
                f"({post.like_count} likes, {post.repost_count} reposts) using pattern '{pattern}'."
            )
            score = round(post.popularity_score, 4)
            draft = XDraft(
                run_id=run.id,
                topic=topic_hint,
                source_post_ids=[post.post_id],
                title=title,
                draft_text=draft_text,
                image_brief=image_brief,
                hook_pattern=pattern,
                rationale=rationale,
                score=score,
            )
            self.db.add(draft)
            created.append(draft)
            if len(created) >= limit:
                break

        self.db.commit()
        for draft in created:
            self.db.refresh(draft)
        return created

    def _fetch_trending_topics(self, *, location_woeid: int, max_topics: int) -> list[dict]:
        url = f"{self.settings.x_api_base_url.rstrip('/')}/2/trends/by/woeid/{location_woeid}"
        payload = self._request_json(
            url=url,
            params={"max_trends": max_topics, "trend.fields": "trend_name,tweet_count"},
        )
        trends = payload.get("data") or []
        normalized: list[dict] = []
        for trend in trends:
            name = str(trend.get("trend_name") or trend.get("name") or "").strip()
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "url": f"https://x.com/search?q={requests.utils.quote(name)}",
                    "tweet_volume": self._to_int(trend.get("tweet_count")),
                    "raw": trend,
                }
            )
        normalized.sort(key=lambda item: (item.get("tweet_volume") or 0), reverse=True)
        return normalized[:max_topics]

    def _fetch_posts(self, *, query: str, max_posts: int, result_type: str, only_with_images: bool, lang: str | None) -> list[dict]:
        search_queries = self._build_search_queries(query=query, only_with_images=only_with_images, lang=lang)
        if not search_queries:
            search_queries = [self._compose_query(query=query, only_with_images=only_with_images, lang=lang)]

        aggregated: dict[str, dict] = {}
        per_query_limit = min(max(20, max_posts * 3), 200)
        for search_query in search_queries:
            batch = self._fetch_posts_v2(
                search_query=search_query,
                logical_query=query,
                max_posts=per_query_limit,
                sort_order="relevancy",
            )
            for post in batch:
                existing = aggregated.get(post["post_id"])
                if existing is None or post["popularity_score"] > existing["popularity_score"]:
                    aggregated[post["post_id"]] = post

        posts = [post for post in aggregated.values() if not self._is_low_quality_post(post)]
        posts.sort(key=lambda item: (item["popularity_score"], item["like_count"], item["repost_count"]), reverse=True)
        return posts[:max_posts]

    def _fetch_posts_v2(self, *, search_query: str, logical_query: str, max_posts: int, sort_order: str = "relevancy") -> list[dict]:
        url = f"{self.settings.x_api_base_url.rstrip('/')}/2/tweets/search/recent"
        posts: list[dict] = []
        seen_ids: set[str] = set()
        next_token: str | None = None
        max_results = min(max(max_posts, 20), 100)
        max_pages = max(1, min(self.settings.x_api_search_pages, math.ceil(max_posts / max_results) + 1))

        for _ in range(max_pages):
            params = {
                "query": search_query,
                "max_results": max_results,
                "sort_order": sort_order,
                "tweet.fields": "created_at,lang,public_metrics,attachments,author_id,conversation_id,text",
                "expansions": "attachments.media_keys,author_id",
                "media.fields": "url,preview_image_url,type,width,height,alt_text,public_metrics",
                "user.fields": "username,name",
            }
            if next_token:
                params["next_token"] = next_token
            payload = self._request_json(url=url, params=params)
            tweets = payload.get("data") or []
            includes = payload.get("includes") or {}
            media_by_key = {
                str(media.get("media_key") or ""): media
                for media in (includes.get("media") or [])
                if str(media.get("media_key") or "")
            }
            users_by_id = {
                str(user.get("id") or ""): user
                for user in (includes.get("users") or [])
                if str(user.get("id") or "")
            }
            for tweet in tweets:
                parsed = self._parse_v2_tweet(
                    tweet=tweet,
                    query=logical_query,
                    media_by_key=media_by_key,
                    users_by_id=users_by_id,
                )
                post_id = parsed.get("post_id")
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                posts.append(parsed)
                if len(posts) >= max_posts:
                    break
            if len(posts) >= max_posts:
                break
            next_token = ((payload.get("meta") or {}).get("next_token")) or None
            if not next_token:
                break
        posts.sort(key=lambda item: (item["popularity_score"], item["like_count"]), reverse=True)
        return posts[:max_posts]

    def _parse_v2_tweet(self, *, tweet: dict, query: str, media_by_key: dict[str, dict], users_by_id: dict[str, dict]) -> dict:
        text = str(tweet.get("text") or "").strip()
        author = users_by_id.get(str(tweet.get("author_id") or ""), {})
        metrics = tweet.get("public_metrics") or {}
        media_keys = ((tweet.get("attachments") or {}).get("media_keys")) or []
        media_payloads: list[dict] = []
        has_images = False
        media_view_count = 0
        for media_key in media_keys:
            media = media_by_key.get(str(media_key), {})
            media_type = str(media.get("type") or "").lower() or None
            has_images = has_images or media_type == "photo"
            media_metrics = media.get("public_metrics") or {}
            media_view_count = max(media_view_count, self._to_int(media_metrics.get("view_count")) or 0)
            media_payloads.append(
                {
                    "media_key": str(media.get("media_key") or media_key) or None,
                    "media_type": media_type,
                    "media_url": media.get("url"),
                    "preview_image_url": media.get("preview_image_url") or media.get("url"),
                    "width": self._to_int(media.get("width")),
                    "height": self._to_int(media.get("height")),
                    "alt_text": media.get("ext_alt_text"),
                    "raw_payload": media,
                }
            )

        created_at = self._parse_iso_datetime(tweet.get("created_at"))
        favorite_count = self._to_int(metrics.get("like_count")) or 0
        repost_count = self._to_int(metrics.get("retweet_count")) or 0
        reply_count = self._to_int(metrics.get("reply_count")) or 0
        quote_count = self._to_int(metrics.get("quote_count")) or 0
        bookmark_count = self._to_int(metrics.get("bookmark_count")) or 0
        impression_count = self._to_int(metrics.get("impression_count")) or 0
        popularity_score = self._popularity_score(
            favorite_count=favorite_count,
            repost_count=repost_count,
            reply_count=reply_count,
            quote_count=quote_count,
            media_view_count=media_view_count,
            has_images=has_images,
        )

        post_id = str(tweet.get("id") or "").strip()
        username = str(author.get("username") or "").strip() or None
        permalink = f"https://x.com/{username}/status/{post_id}" if username and post_id else None

        return {
            "post_id": post_id,
            "query": query,
            "author_id": str(author.get("id") or "") or None,
            "author_username": username,
            "author_name": str(author.get("name") or "").strip() or None,
            "text": text,
            "lang": tweet.get("lang"),
            "conversation_id": str(tweet.get("conversation_id") or "") or None,
            "created_at_x": created_at,
            "like_count": favorite_count,
            "repost_count": repost_count,
            "reply_count": reply_count,
            "quote_count": quote_count,
            "bookmark_count": bookmark_count,
            "impression_count": impression_count,
            "media_view_count": media_view_count,
            "has_images": has_images,
            "popularity_score": popularity_score,
            "permalink": permalink,
            "raw_payload": tweet,
            "media_payloads": media_payloads,
        }

    def _build_search_queries(self, *, query: str, only_with_images: bool, lang: str | None) -> list[str]:
        normalized = self._normalize_query(query).lower()
        candidates: list[str] = []
        seen: set[str] = set()

        expansions = HEALTH_QUERY_EXPANSIONS.get(normalized, [])
        if not expansions:
            if "health" in normalized or "wellness" in normalized or "fitness" in normalized or "nutrition" in normalized:
                expansions = HEALTH_QUERY_EXPANSIONS["healthy lifestyle"]
            else:
                expansions = [normalized]

        for term in expansions:
            built = self._compose_query(query=term, only_with_images=only_with_images, lang=lang)
            if built in seen:
                continue
            seen.add(built)
            candidates.append(built)
        return candidates

    def _compose_query(self, *, query: str, only_with_images: bool, lang: str | None) -> str:
        terms = [f'"{query}"'] if " " in query.strip() else [query.strip()]
        operator_parts = [*terms, "-is:retweet", "-is:reply", "-has:links"]
        if only_with_images:
            operator_parts.append("has:images")
        if lang:
            operator_parts.append(f"lang:{lang}")
        return " ".join(part for part in operator_parts if part)

    def _compose_topic_search_query(self, *, topic: str, lang: str | None, image_mode: str) -> str:
        clean = self._normalize_query(topic)
        if not clean:
            return ""

        terms: list[str] = []
        if clean.startswith("#"):
            bare = clean.lstrip("#")
            if bare:
                terms.append(clean)
                terms.append(f'"{bare}"')
        elif " " in clean:
            terms.append(f'"{clean}"')
        else:
            terms.append(clean)
            terms.append(f"#{clean.lstrip('#')}")

        operator_parts = []
        if len(terms) == 1:
            operator_parts.append(terms[0])
        else:
            operator_parts.append(f"({' OR '.join(terms)})")
        operator_parts.append("-is:retweet")
        if image_mode == "required":
            operator_parts.append("has:images")
        if lang:
            operator_parts.append(f"lang:{lang}")
        return " ".join(part for part in operator_parts if part)

    def _is_sparse_post(self, post: dict) -> bool:
        text = self._clean_text(post.get("text") or "")
        if not text:
            return True
        if text.startswith("RT "):
            return True
        total_engagement = sum(
            self._to_int(post.get(field)) or 0
            for field in (
                "like_count",
                "repost_count",
                "reply_count",
                "quote_count",
                "bookmark_count",
                "impression_count",
                "media_view_count",
            )
        )
        if total_engagement <= 0:
            return True
        return False

    def _topic_post_bonus(self, *, post: dict, image_mode: str) -> float:
        bonus = 0.0
        if image_mode == "prefer" and post.get("has_images"):
            bonus += 0.18
        impressions = self._to_int(post.get("impression_count")) or 0
        bookmarks = self._to_int(post.get("bookmark_count")) or 0
        if impressions > 0:
            bonus += min(math.log(impressions + 1, 10) * 0.06, 0.25)
        if bookmarks > 0:
            bonus += min(math.log(bookmarks + 1, 10) * 0.05, 0.15)
        return bonus

    def _is_low_quality_post(self, post: dict) -> bool:
        text = self._clean_text(post.get("text") or "")
        lowered = text.lower()
        if not text:
            return True
        if text.startswith("RT "):
            return True
        if sum(1 for token in text.split() if token.startswith("#")) > 5:
            return True
        if sum(1 for token in text.split() if token.startswith("http")) > 0:
            return True
        if any(pattern in lowered for pattern in PROMO_PATTERNS):
            return True
        if (post.get("like_count", 0) + post.get("repost_count", 0) + post.get("reply_count", 0) + post.get("quote_count", 0)) <= 0:
            return True
        if len(text) < 40:
            return True
        return False

    def _build_draft_text(self, *, post: XPost, topic_hint: str, pattern: str) -> str:
        text = self._clean_text(post.text)
        distilled = self._distill_claim(text)
        if pattern == "question":
            return f"{topic_hint}: what is the one change people keep underestimating, even though it compounds fast?\n\nMy take: {distilled}."
        if pattern == "list":
            return f"3 things about {topic_hint} that matter more than people think:\n1. clarity\n2. consistency\n3. proof\n\n{distilled}."
        if pattern == "contrarian":
            return f"Hot take on {topic_hint}: the flashy version is rarely the one that works.\n\n{distilled}. Keep it simple and repeatable."
        if pattern == "command":
            return f"If you care about {topic_hint}, stop overcomplicating it.\n\n{distilled}. Start with one action you can repeat this week."
        return f"{topic_hint}: {distilled}. That is the part worth testing this week."

    def _build_image_brief(self, *, post: XPost, topic_hint: str) -> str:
        media_types = ", ".join(sorted({media.media_type or "unknown" for media in post.media_items})) or "photo"
        return (
            f"Create an original {media_types}-led X visual for topic '{topic_hint}'. "
            "Keep the composition simple, mobile-readable, high-contrast, and built around one clear idea. "
            "Avoid copying the source image directly; preserve only the content format and attention pattern."
        )

    def _build_title(self, *, topic_hint: str, pattern: str) -> str:
        return f"{topic_hint.title()} / {pattern.replace('_', ' ').title()}"

    def _pick_topic_hint(self, *, topic_names: list[str], query: str) -> str:
        normalized_query = self._normalize_query(query)
        query_tokens = set(self._tokens(normalized_query))
        for topic in topic_names:
            tokens = set(self._tokens(topic))
            if query_tokens & tokens:
                return topic
        return normalized_query or (topic_names[0] if topic_names else "topic")

    def _detect_hook_pattern(self, text: str) -> str:
        stripped = self._clean_text(text)
        lowered = stripped.lower()
        if "?" in stripped[:160]:
            return "question"
        if re.match(r"^\s*(\d+|[1-9]\.)", stripped):
            return "list"
        if lowered.startswith(("hot take", "unpopular opinion", "counterpoint")):
            return "contrarian"
        if lowered.startswith(("stop ", "start ", "do ", "try ")):
            return "command"
        return "statement"

    def _distill_claim(self, text: str) -> str:
        cleaned = self._clean_text(text)
        first_sentence = re.split(r"[.!?\n]", cleaned)[0].strip()
        return first_sentence[:220] if first_sentence else cleaned[:220]

    def _clean_text(self, text: str) -> str:
        compact = re.sub(r"\s+", " ", text or "").strip()
        compact = re.sub(r"https?://\S+", "", compact).strip()
        return compact

    def _normalize_query(self, query: str) -> str:
        return re.sub(r"\s+", " ", str(query or "").strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.x_api_bearer_token}",
            "User-Agent": "InfluencerStudio/0.1",
        }

    def _request_json(self, *, url: str, params: dict, retries: int = 3, timeout: int = 60) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                if response is not None and response.status_code in {400, 401, 403, 404, 422}:
                    raise
                if attempt >= retries:
                    raise
                time.sleep(min(1.5 * attempt, 4.0))
        if last_error is not None:
            raise last_error
        raise RuntimeError("request failed without error")

    def _popularity_score(
        self,
        *,
        favorite_count: int,
        repost_count: int,
        reply_count: int,
        quote_count: int,
        media_view_count: int,
        has_images: bool,
    ) -> float:
        base = (favorite_count * 1.0) + (repost_count * 2.2) + (reply_count * 1.6) + (quote_count * 1.8)
        if media_view_count > 0:
            base += min(math.log(media_view_count + 1, 10) * 2.5, 18.0)
        if has_images:
            base *= 1.12
        return round(math.log(base + 1, 10), 4)

    def _parse_x_datetime(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y").astimezone(UTC)
        except ValueError:
            return None

    def _parse_iso_datetime(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None

    def _to_int(self, value) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _tokens(self, text: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(token) >= 3]
