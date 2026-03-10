from __future__ import annotations

import json
from datetime import UTC, datetime

import requests
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import XDraft, XPost, XPostMedia, XTrendRun, XTrendTopic
from app.pipelines.gemini_vlm import extract_json_object, sanitize_error_message
from app.schemas.x_pipeline import XPipelineRunOut
from app.services.influencers import InfluencerService
from app.services.x_content import XContentService


class XPipelineService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.influencers = InfluencerService(db=db, settings=settings)
        self.x_content = XContentService(db=db, settings=settings)

    def run(
        self,
        *,
        influencer_id: str,
        mode: str,
        location_woeid: int,
        max_trending_topics: int,
        selected_topics_limit: int,
        max_posts_per_topic: int,
        max_total_posts: int,
        draft_limit: int,
        image_mode: str,
        lang: str | None,
        model: str,
    ) -> XPipelineRunOut:
        influencer = self.influencers.require_ready_influencer(influencer_id)

        run = XTrendRun(
            status="running",
            query=f"{mode}:{influencer.influencer_id}",
            location_woeid=location_woeid,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            candidate_topics = self._build_candidate_topics(
                influencer=influencer,
                mode=mode,
                location_woeid=location_woeid,
                max_trending_topics=max_trending_topics,
            )
            selected_topics, selection_rationale = self._select_topics(
                influencer=influencer,
                mode=mode,
                candidate_topics=candidate_topics,
                selected_topics_limit=selected_topics_limit,
                model=model,
            )

            self._store_topics(
                run=run,
                candidate_topics=candidate_topics,
                selected_topics=selected_topics,
                mode=mode,
            )

            posts = self.x_content.search_posts_for_topics(
                topics=selected_topics,
                max_posts_per_topic=max_posts_per_topic,
                max_total_posts=max_total_posts,
                lang=lang,
                image_mode=image_mode,
            )
            stored_posts = self._store_posts(run=run, posts=posts)
            drafts, content_summary = self._generate_drafts_with_gemini(
                run=run,
                influencer=influencer,
                selected_topics=selected_topics,
                posts=stored_posts,
                draft_limit=draft_limit,
                model=model,
            )

            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.summary = {
                "mode": mode,
                "influencer_id": influencer.influencer_id,
                "candidate_topics": candidate_topics,
                "selected_topics": selected_topics,
                "selection_rationale": selection_rationale,
                "collected_posts": len(stored_posts),
                "image_posts": sum(1 for post in stored_posts if post.has_images),
                "drafts_generated": len(drafts),
                "content_summary": content_summary,
            }
            self.db.commit()

            run_detail = self.x_content.get_run(run.id)
            top_posts = sorted(stored_posts, key=lambda post: (post.popularity_score, post.like_count), reverse=True)
            return XPipelineRunOut(
                influencer_id=influencer.influencer_id,
                mode=mode,
                candidate_topics=candidate_topics,
                selected_topics=selected_topics,
                selection_rationale=selection_rationale,
                run=run_detail,  # type: ignore[arg-type]
                top_posts=top_posts[: min(len(top_posts), 10)],
                drafts=drafts,
            )
        except Exception as exc:
            self.db.rollback()
            failed = self.db.get(XTrendRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.completed_at = datetime.now(UTC)
                failed.error_message = str(exc)
                self.db.commit()
            raise

    def _build_candidate_topics(
        self,
        *,
        influencer,
        mode: str,
        location_woeid: int,
        max_trending_topics: int,
    ) -> list[str]:
        if mode == "base_hashtags":
            return self._normalize_topics(influencer.hashtags or [])

        trends = self.x_content.get_trending_topics(location_woeid=location_woeid, max_topics=max_trending_topics)
        return self._normalize_topics([str(item.get("name") or "") for item in trends])

    def _select_topics(
        self,
        *,
        influencer,
        mode: str,
        candidate_topics: list[str],
        selected_topics_limit: int,
        model: str,
    ) -> tuple[list[str], str]:
        if not candidate_topics:
            raise ValueError("No candidate X topics available for selection.")

        if mode == "base_hashtags" and len(candidate_topics) <= selected_topics_limit:
            return candidate_topics[:selected_topics_limit], "Using influencer base hashtags directly."

        payload = self._call_gemini_json(
            model=model,
            prompt=self._build_topic_selection_prompt(
                influencer=influencer,
                mode=mode,
                candidate_topics=candidate_topics,
                selected_topics_limit=selected_topics_limit,
            ),
        )
        normalized_map = {self._normalize_topic_key(topic): topic for topic in candidate_topics}
        selected_topics: list[str] = []
        seen: set[str] = set()
        for raw in payload.get("selected_topics") or []:
            key = self._normalize_topic_key(str(raw or ""))
            topic = normalized_map.get(key)
            if not topic or key in seen:
                continue
            seen.add(key)
            selected_topics.append(topic)
            if len(selected_topics) >= selected_topics_limit:
                break
        if not selected_topics:
            if mode == "trending_hashtags":
                raise ValueError("No trending X topics matched the influencer profile strongly enough.")
            selected_topics = candidate_topics[:selected_topics_limit]
        rationale = str(payload.get("rationale") or "").strip() or "Selected by Gemini based on influencer fit."
        return selected_topics, rationale

    def _store_topics(
        self,
        *,
        run: XTrendRun,
        candidate_topics: list[str],
        selected_topics: list[str],
        mode: str,
    ) -> None:
        selected_keys = {self._normalize_topic_key(topic) for topic in selected_topics}
        for idx, topic in enumerate(candidate_topics, start=1):
            self.db.add(
                XTrendTopic(
                    run_id=run.id,
                    name=topic,
                    trend_url=f"https://x.com/search?q={requests.utils.quote(topic)}",
                    position=idx,
                    raw_payload={
                        "mode": mode,
                        "selected": self._normalize_topic_key(topic) in selected_keys,
                    },
                )
            )
        self.db.flush()

    def _store_posts(self, *, run: XTrendRun, posts: list[dict]) -> list[XPost]:
        stored_posts: list[XPost] = []
        for post in posts:
            media_payloads = post.pop("media_payloads", [])
            post_row = XPost(run_id=run.id, **post)
            self.db.add(post_row)
            self.db.flush()
            for media in media_payloads:
                self.db.add(XPostMedia(post_row_id=post_row.id, **media))
            stored_posts.append(post_row)
        self.db.flush()
        for post in stored_posts:
            self.db.refresh(post)
        return stored_posts

    def _generate_drafts_with_gemini(
        self,
        *,
        run: XTrendRun,
        influencer,
        selected_topics: list[str],
        posts: list[XPost],
        draft_limit: int,
        model: str,
    ) -> tuple[list[XDraft], dict]:
        if not posts:
            return [], {"note": "No posts collected."}

        ranked_posts = sorted(posts, key=lambda post: (post.popularity_score, post.like_count), reverse=True)
        prompt = self._build_draft_generation_prompt(
            influencer=influencer,
            selected_topics=selected_topics,
            posts=ranked_posts[: min(len(ranked_posts), 12)],
            draft_limit=draft_limit,
        )
        payload = self._call_gemini_json(model=model, prompt=prompt)
        content_summary = payload.get("content_summary") or {}
        created: list[XDraft] = []
        post_by_id = {post.post_id: post for post in ranked_posts}
        for idx, item in enumerate(payload.get("drafts") or []):
            source_ids = []
            for source_id in item.get("source_post_ids") or []:
                clean = str(source_id or "").strip()
                if clean and clean in post_by_id and clean not in source_ids:
                    source_ids.append(clean)
            topic = str(item.get("topic") or "").strip() or (selected_topics[0] if selected_topics else None)
            draft = XDraft(
                run_id=run.id,
                topic=topic,
                source_post_ids=source_ids or None,
                title=str(item.get("title") or f"{topic or 'Topic'} / Draft {idx + 1}").strip(),
                draft_text=str(item.get("draft_text") or "").strip(),
                image_brief=str(item.get("image_brief") or "").strip() or None,
                hook_pattern=str(item.get("hook_pattern") or "").strip() or None,
                rationale=str(item.get("rationale") or "").strip() or None,
                score=self._coerce_score(item.get("score"), default=7.0),
            )
            if not draft.draft_text:
                continue
            self.db.add(draft)
            created.append(draft)
            if len(created) >= draft_limit:
                break
        self.db.flush()
        for draft in created:
            self.db.refresh(draft)
        return created, content_summary

    def _build_topic_selection_prompt(
        self,
        *,
        influencer,
        mode: str,
        candidate_topics: list[str],
        selected_topics_limit: int,
    ) -> str:
        candidate_blob = "\n".join(f"- {topic}" for topic in candidate_topics[:100])
        return (
            "You are selecting X topics/hashtags for an influencer content pipeline.\n"
            "Pick the topics that best fit the influencer's niche and are likely to support strong original posts.\n"
            "Prefer topics that are coherent with the influencer description and base hashtags.\n"
            "Avoid topics that conflict with the negative requirements.\n"
            "If none of the candidates genuinely fit the influencer, return an empty selected_topics list.\n\n"
            f"Mode: {mode}\n"
            f"Influencer name: {influencer.name}\n"
            f"Influencer description: {influencer.description or ''}\n"
            f"Base hashtags: {', '.join(influencer.hashtags or [])}\n"
            f"Negative content requirements: {influencer.video_suggestions_requirement or ''}\n"
            f"Select up to {selected_topics_limit} topics from this candidate list:\n"
            f"{candidate_blob}\n\n"
            "Return JSON only in this shape:\n"
            '{'
            '"selected_topics": ["topic1", "topic2"], '
            '"rationale": "short explanation"'
            '}'
        )

    def _build_draft_generation_prompt(
        self,
        *,
        influencer,
        selected_topics: list[str],
        posts: list[XPost],
        draft_limit: int,
    ) -> str:
        examples = []
        for post in posts:
            media_summary = []
            for media in post.media_items[:2]:
                bits = [media.media_type or "media"]
                if media.alt_text:
                    bits.append(f"alt={media.alt_text[:120]}")
                if media.media_url:
                    bits.append(f"url={media.media_url}")
                media_summary.append(", ".join(bits))
            examples.append(
                {
                    "post_id": post.post_id,
                    "topic": post.query,
                    "author": post.author_username,
                    "text": post.text,
                    "likes": post.like_count,
                    "reposts": post.repost_count,
                    "replies": post.reply_count,
                    "quotes": post.quote_count,
                    "bookmarks": post.bookmark_count,
                    "impressions": post.impression_count,
                    "has_images": post.has_images,
                    "media": media_summary,
                    "permalink": post.permalink,
                }
            )
        return (
            "You are creating original X posts for an influencer by studying high-performing examples.\n"
            "Do not copy the source posts. Extract patterns, hooks, tone, and image concepts, then produce new original drafts.\n"
            "If image-backed posts are present, produce image briefs that reuse the attention pattern, not the exact visual.\n\n"
            f"Influencer name: {influencer.name}\n"
            f"Influencer description: {influencer.description or ''}\n"
            f"Influencer hashtags: {', '.join(influencer.hashtags or [])}\n"
            f"Negative content requirements: {influencer.video_suggestions_requirement or ''}\n"
            f"Selected topics: {', '.join(selected_topics)}\n"
            f"Top source posts (JSON): {json.dumps(examples, ensure_ascii=True)}\n\n"
            f"Return JSON only in this shape with up to {draft_limit} drafts:\n"
            '{'
            '"content_summary": {'
            '"themes": ["..."], '
            '"hooks": ["..."], '
            '"image_patterns": ["..."]'
            '}, '
            '"drafts": ['
            '{'
            '"topic": "topic", '
            '"title": "short title", '
            '"draft_text": "original X post text", '
            '"image_brief": "optional image brief or empty string", '
            '"hook_pattern": "question|list|statement|contrarian|command", '
            '"rationale": "why this fits", '
            '"score": 0-10, '
            '"source_post_ids": ["123", "456"]'
            '}'
            ']'
            '}'
        )

    def _call_gemini_json(self, *, model: str, prompt: str) -> dict:
        api_key = (self.settings.gemini_api_key or "").strip()
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY")

        payload = {
            "generationConfig": {
                "temperature": 0.25,
                "responseMimeType": "application/json",
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = requests.post(url, params={"key": api_key}, json=payload, timeout=120)
            response.raise_for_status()
        except requests.HTTPError as exc:
            message = sanitize_error_message(str(exc), api_key=api_key)
            raise RuntimeError(f"Gemini request failed: {message}") from exc

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "\n".join(str(part.get("text") or "").strip() for part in parts if part.get("text")).strip()
        if not text:
            raise RuntimeError(f"Gemini returned no text output: {data}")
        return extract_json_object(text)

    def _normalize_topics(self, raw_topics: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in raw_topics:
            topic = " ".join(str(raw or "").strip().split())
            if not topic:
                continue
            key = self._normalize_topic_key(topic)
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(topic)
        return normalized

    def _normalize_topic_key(self, topic: str) -> str:
        return str(topic or "").strip().lower().lstrip("#")

    def _coerce_score(self, value, *, default: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(score, 10.0))
