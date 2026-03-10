from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import PictureIdea, TrendSignal
from app.services.influencers import InfluencerService
from app.services.trend_parser import TrendParserService


class PictureIdeaService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.influencers = InfluencerService(db=db, settings=settings)
        self.trends = TrendParserService(db=db, settings=settings)

    def list_ideas(self, influencer_id: str, limit: int = 20) -> list[PictureIdea]:
        stmt = (
            select(PictureIdea)
            .where(PictureIdea.influencer_id == influencer_id)
            .order_by(desc(PictureIdea.created_at), desc(PictureIdea.id))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def generate(self, influencer_id: str, platforms: list[str], limit: int, run_ids: list[int] | None = None) -> list[PictureIdea]:
        influencer = self.influencers.require_ready_influencer(influencer_id)
        platform_list = self._normalize_platforms(platforms)
        if not platform_list:
            raise ValueError("At least one supported platform is required.")

        effective_run_ids = [rid for rid in (run_ids or []) if int(rid) > 0]
        if not effective_run_ids:
            effective_run_ids = self._latest_run_ids(platform_list)
        if not effective_run_ids:
            raise ValueError("No completed trend runs found for the requested platforms.")

        signals = self._load_signals(platform_list, effective_run_ids)
        if not signals:
            raise ValueError("No trend signals available for picture idea generation.")

        influencer_tags = set(influencer.hashtags or [])
        desc_tokens = set(self._tokens(influencer.description or ""))
        negative_tokens = set(self._tokens(influencer.video_suggestions_requirement or ""))

        buckets: dict[str, list[TrendSignal]] = defaultdict(list)
        for signal in signals:
            buckets[signal.signal_type].append(signal)

        hashtags = buckets.get("hashtag", [])
        topics = buckets.get("topic", [])
        styles = buckets.get("style", [])
        hooks = buckets.get("hook", [])

        ideas: list[PictureIdea] = []
        seen_titles: set[str] = set()
        for idx, hashtag_signal in enumerate(hashtags[: max(limit * 2, limit)], start=1):
            hashtag = str(hashtag_signal.value).strip().lstrip("#").lower()
            fit_bonus = 0.0
            if hashtag in influencer_tags:
                fit_bonus += 1.5
            if hashtag in desc_tokens:
                fit_bonus += 1.0
            if hashtag in negative_tokens:
                fit_bonus -= 3.0

            topic_signal = topics[(idx - 1) % len(topics)] if topics else None
            style_signal = styles[(idx - 1) % len(styles)] if styles else None
            hook_signal = hooks[(idx - 1) % len(hooks)] if hooks else None

            style_text = str(style_signal.value).replace("_", " ") if style_signal else "editorial social photo"
            topic_text = str(topic_signal.value).replace("_", " ") if topic_signal else hashtag.replace("_", " ")
            hook_text = str(hook_signal.value) if hook_signal else ""
            score = round(float(hashtag_signal.score) + fit_bonus, 4)

            title = self._title_from_parts(hashtag=hashtag, topic=topic_text, style=style_text)
            if title in seen_titles:
                continue
            seen_titles.add(title)

            prompt = (
                f"Create a picture idea for {influencer.name}. "
                f"Influencer profile: {influencer.description}. "
                f"Visual direction: {style_text}. "
                f"Core trend topic: {topic_text}. "
                f"Anchor hashtags: #{hashtag}"
            )
            if hook_text:
                prompt = f"{prompt}. Caption vibe: {hook_text}"
            prompt = (
                f"{prompt}. Must avoid: {influencer.video_suggestions_requirement}. "
                f"Reference image should stay consistent with the influencer identity."
            )

            rationale = (
                f"Built from hashtag #{hashtag} with topic '{topic_text}' and style '{style_text}'. "
                f"Fit bonus={fit_bonus:.1f} based on influencer hashtags/description."
            )

            idea = PictureIdea(
                influencer_id=influencer.influencer_id,
                platforms=platform_list,
                source_run_ids=effective_run_ids,
                title=title,
                prompt=prompt,
                hashtags=[hashtag],
                score=score,
                rationale=rationale,
            )
            self.db.add(idea)
            ideas.append(idea)
            if len(ideas) >= limit:
                break

        self.db.commit()
        for idea in ideas:
            self.db.refresh(idea)
        return ideas

    def _latest_run_ids(self, platforms: list[str]) -> list[int]:
        run_ids: list[int] = []
        for platform in platforms:
            run = self.trends.latest_for_platform(platform)
            if run is not None and run.status == "completed":
                run_ids.append(run.id)
        return run_ids

    def _load_signals(self, platforms: list[str], run_ids: list[int]) -> list[TrendSignal]:
        stmt = (
            select(TrendSignal)
            .where(TrendSignal.platform.in_(platforms))
            .where(TrendSignal.run_id.in_(run_ids))
            .order_by(desc(TrendSignal.score), desc(TrendSignal.id))
        )
        return list(self.db.execute(stmt).scalars().all())

    def _normalize_platforms(self, platforms: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for platform in platforms:
            value = str(platform or "").strip().lower()
            if value not in {"tiktok", "instagram"} or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def _tokens(self, text: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(token) >= 3]

    def _title_from_parts(self, hashtag: str, topic: str, style: str) -> str:
        hashtag_part = hashtag.replace("_", " ").title()
        topic_part = topic.replace("_", " ").title()
        style_part = style.replace("_", " ").title()
        return f"{hashtag_part} / {topic_part} / {style_part}"
