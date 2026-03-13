from __future__ import annotations

import base64
import json
import math
import mimetypes
import os
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import requests
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import GeneratedImage, PictureIdea, TrendRun, TrendSignal
from app.services.filesystem_store import FilesystemStore
from app.services.influencers import InfluencerService

NOISE_HASHTAGS = {
    "fyp",
    "fy",
    "foryou",
    "foryoupage",
    "viral",
    "trending",
    "trend",
    "reels",
    "reel",
    "video",
    "videos",
    "insta",
    "explore",
    "feed",
    "nyc",
}


class GeneratedImageService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.influencers = InfluencerService(db=db, settings=settings)
        self.fs = FilesystemStore(settings=settings)

    def list_images(self, influencer_id: str, limit: int = 20) -> list[GeneratedImage]:
        if self.settings.storage_mode == "filesystem":
            image_dir = self.fs.influencer_generated_images_dir(influencer_id)
            records = []
            for path in sorted(image_dir.glob("generated_*.json"), reverse=True)[:limit]:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records.append(SimpleNamespace(**payload))
            return records  # type: ignore[return-value]
        stmt = (
            select(GeneratedImage)
            .where(GeneratedImage.influencer_id == influencer_id)
            .order_by(desc(GeneratedImage.created_at), desc(GeneratedImage.id))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def generate(
        self,
        *,
        influencer_id: str,
        prompt: str,
        picture_idea_id: int | None,
        reference_image_path: str | None,
        model: str,
        api_key_env: str,
        aspect_ratio: str,
        hashtag_strategy: str,
        hashtag_platforms: list[str],
        trend_run_ids: list[int] | None,
        trend_window_days: int,
        max_hashtags: int,
        mock: bool,
    ) -> GeneratedImage:
        influencer = self.influencers.require_ready_influencer(influencer_id)
        picture_idea = self._get_picture_idea(picture_idea_id) if picture_idea_id else None
        if picture_idea is not None and picture_idea.influencer_id != influencer.influencer_id:
            raise ValueError("picture_idea_id does not belong to the requested influencer")
        if not prompt.strip() and picture_idea is None:
            raise ValueError("Provide prompt or picture_idea_id for image generation")
        selected_hashtags = self._select_hashtags(
            influencer=influencer,
            strategy=hashtag_strategy,
            platforms=hashtag_platforms,
            run_ids=trend_run_ids or [],
            trend_window_days=trend_window_days,
            max_hashtags=max_hashtags,
        )

        effective_prompt = self._build_prompt(
            influencer=influencer,
            user_prompt=prompt,
            picture_idea=picture_idea,
            hashtags=selected_hashtags,
        )
        ref_path = Path(reference_image_path).expanduser() if reference_image_path else None
        if ref_path is None:
            ref_path = Path(str(influencer.reference_image_path))
        if not ref_path.exists():
            raise ValueError(f"Reference image not found: {ref_path}")

        if mock:
            image_bytes, mime_type = self._generate_mock_output(reference_image_path=ref_path)
        else:
            api_key = self._get_api_key(api_key_env)
            image_bytes, mime_type = self._generate_with_gemini(
                model=model,
                api_key=api_key,
                reference_image_path=ref_path,
                prompt=effective_prompt,
                aspect_ratio=aspect_ratio,
            )
        output_path = self._save_output(
            influencer_id=influencer.influencer_id,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

        if self.settings.storage_mode == "filesystem":
            payload = {
                "id": int(datetime.now(UTC).timestamp() * 1000),
                "influencer_id": influencer.influencer_id,
                "picture_idea_id": picture_idea.id if picture_idea else None,
                "model": model,
                "prompt": effective_prompt,
                "hashtags": selected_hashtags,
                "reference_image_path": str(ref_path.resolve()),
                "output_image_path": str(output_path.resolve()),
                "mime_type": mime_type,
                "created_at": datetime.now(UTC),
            }
            metadata_path = output_path.with_suffix(".json")
            metadata_path.write_text(
                json.dumps({**payload, "created_at": payload["created_at"].isoformat()}, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(**payload)  # type: ignore[return-value]

        record = GeneratedImage(
            influencer_id=influencer.influencer_id,
            picture_idea_id=picture_idea.id if picture_idea else None,
            model=model,
            prompt=effective_prompt,
            hashtags=selected_hashtags,
            reference_image_path=str(ref_path.resolve()),
            output_image_path=str(output_path.resolve()),
            mime_type=mime_type,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _get_picture_idea(self, picture_idea_id: int) -> PictureIdea:
        stmt = select(PictureIdea).where(PictureIdea.id == picture_idea_id).limit(1)
        record = self.db.execute(stmt).scalar_one_or_none()
        if record is None:
            raise ValueError(f"Picture idea not found: {picture_idea_id}")
        return record

    def _build_prompt(
        self,
        *,
        influencer,
        user_prompt: str,
        picture_idea: PictureIdea | None,
        hashtags: list[str],
    ) -> str:
        sections: list[str] = [
            "Use the provided reference image to preserve the same person identity, facial structure, and overall look.",
            f"Influencer name: {influencer.name}",
            f"Influencer description: {influencer.description or ''}",
            f"Preferred hashtags/themes: {', '.join(hashtags) or '(none)'}",
            f"Do not include: {influencer.video_suggestions_requirement or '(none)'}",
        ]
        if picture_idea is not None:
            sections.append(f"Picture idea title: {picture_idea.title}")
            sections.append(f"Picture idea prompt: {picture_idea.prompt}")
        if user_prompt.strip():
            sections.append(f"User prompt: {user_prompt.strip()}")
        sections.append("Return a high-quality single image only.")
        return "\n".join(sections)

    def _select_hashtags(
        self,
        *,
        influencer,
        strategy: str,
        platforms: list[str],
        run_ids: list[int],
        trend_window_days: int,
        max_hashtags: int,
    ) -> list[str]:
        base_hashtags = self._clean_hashtags(influencer.hashtags or [])[:max_hashtags]
        normalized_strategy = (strategy or "mixed").strip().lower()
        if normalized_strategy == "base":
            return base_hashtags

        trending_hashtags = self._load_trending_hashtags(
            influencer=influencer,
            platforms=platforms,
            run_ids=run_ids,
            trend_window_days=trend_window_days,
            max_hashtags=max_hashtags,
        )
        if normalized_strategy == "trending":
            return trending_hashtags or base_hashtags

        merged: list[str] = []
        seen: set[str] = set()
        for hashtag in base_hashtags + trending_hashtags:
            if hashtag in seen:
                continue
            seen.add(hashtag)
            merged.append(hashtag)
            if len(merged) >= max_hashtags:
                break
        return merged

    def _load_trending_hashtags(
        self,
        *,
        influencer,
        platforms: list[str],
        run_ids: list[int],
        trend_window_days: int,
        max_hashtags: int,
    ) -> list[str]:
        normalized_platforms = self._normalize_platforms(platforms)
        if not normalized_platforms:
            normalized_platforms = ["instagram"]

        effective_run_ids = [int(run_id) for run_id in run_ids if int(run_id) > 0]
        if not effective_run_ids:
            effective_run_ids = self._recent_run_ids(normalized_platforms, trend_window_days)
        if not effective_run_ids:
            return []

        run_records = {
            int(run.id): run
            for run in self.db.execute(
                select(TrendRun).where(TrendRun.id.in_(effective_run_ids))
            ).scalars().all()
        }

        stmt = (
            select(TrendSignal)
            .where(TrendSignal.signal_type == "hashtag")
            .where(TrendSignal.platform.in_(normalized_platforms))
            .where(TrendSignal.run_id.in_(effective_run_ids))
            .order_by(desc(TrendSignal.score), desc(TrendSignal.id))
        )
        signals = list(self.db.execute(stmt).scalars().all())
        influencer_tags = set(self._clean_hashtags(influencer.hashtags or []))
        desc_tokens = set(self._tokens(influencer.description or ""))
        negative_tokens = set(self._tokens(influencer.video_suggestions_requirement or ""))

        aggregated_scores: dict[str, float] = defaultdict(float)
        signal_counts: dict[str, int] = defaultdict(int)
        for signal in signals:
            hashtag = self._normalize_hashtag(signal.value)
            if not hashtag or hashtag in NOISE_HASHTAGS:
                continue
            score = float(signal.score) * self._recency_weight(run_records.get(int(signal.run_id)), trend_window_days)
            if hashtag in negative_tokens:
                score -= 4.0
            if not self._is_usable_hashtag(hashtag):
                score -= 1.0
            if any(char.isdigit() for char in hashtag):
                score -= 2.0
            aggregated_scores[hashtag] += score
            signal_counts[hashtag] += 1

        scored: list[tuple[float, str]] = []
        for hashtag, base_score in aggregated_scores.items():
            affinity = self._hashtag_affinity(hashtag, influencer_tags, desc_tokens)
            frequency_bonus = math.log(signal_counts[hashtag] + 1, 2)
            scored.append((base_score + affinity + frequency_bonus, hashtag))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [hashtag for score, hashtag in scored[:max_hashtags] if score > 0]

    def _recent_run_ids(self, platforms: list[str], trend_window_days: int) -> list[int]:
        window_start = datetime.now(UTC) - timedelta(days=max(int(trend_window_days), 1))
        run_ids: list[int] = []
        stmt = (
            select(TrendRun)
            .where(TrendRun.status == "completed")
            .order_by(desc(TrendRun.completed_at), desc(TrendRun.id))
            .limit(200)
        )
        for run in self.db.execute(stmt).scalars().all():
            completed_at = self._to_utc(run.completed_at) if run.completed_at else None
            if completed_at is None or completed_at < window_start:
                continue
            if any(platform in (run.platforms or []) for platform in platforms):
                run_ids.append(int(run.id))
        return run_ids

    def _normalize_platforms(self, platforms: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for platform in platforms:
            value = str(platform or "").strip().lower()
            if value not in {"instagram", "tiktok"} or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def _normalize_hashtag(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "", str(value or "").strip().lower().lstrip("#"))

    def _clean_hashtags(self, values: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            hashtag = self._normalize_hashtag(value)
            if not hashtag or hashtag in seen:
                continue
            seen.add(hashtag)
            output.append(hashtag)
        return output

    def _tokens(self, text: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(token) >= 3]

    def _is_usable_hashtag(self, hashtag: str) -> bool:
        return len(hashtag) >= 3 and hashtag not in NOISE_HASHTAGS

    def _hashtag_affinity(self, hashtag: str, influencer_tags: set[str], desc_tokens: set[str]) -> float:
        score = 0.0
        for token in influencer_tags | desc_tokens:
            if not token:
                continue
            if hashtag == token:
                score += 2.0
            elif token in hashtag or hashtag in token:
                score += 1.0
        return score

    def _to_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _recency_weight(self, run: TrendRun | None, trend_window_days: int) -> float:
        if run is None or run.completed_at is None:
            return 1.0
        days_old = max((datetime.now(UTC) - self._to_utc(run.completed_at)).total_seconds() / 86_400, 0.0)
        return max(0.35, math.exp(-(days_old / max(float(trend_window_days), 1.0))))

    def _generate_mock_output(self, *, reference_image_path: Path) -> tuple[bytes, str]:
        mime_type = mimetypes.guess_type(reference_image_path.name)[0] or "image/jpeg"
        return reference_image_path.read_bytes(), mime_type

    def _generate_with_gemini(
        self,
        *,
        model: str,
        api_key: str,
        reference_image_path: Path,
        prompt: str,
        aspect_ratio: str,
    ) -> tuple[bytes, str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        mime_type = mimetypes.guess_type(reference_image_path.name)[0] or "image/jpeg"
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(reference_image_path.read_bytes()).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }
        response = requests.post(url, json=body, timeout=300)
        response.raise_for_status()
        payload = response.json()
        for candidate in payload.get("candidates", []):
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if not inline:
                    continue
                data = inline.get("data")
                output_mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                if data:
                    return base64.b64decode(data), output_mime
        raise RuntimeError("Gemini image generation returned no image data")

    def _save_output(self, *, influencer_id: str, image_bytes: bytes, mime_type: str) -> Path:
        extension = mimetypes.guess_extension(mime_type or "image/png") or ".png"
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        output_dir = self.fs.influencer_generated_images_dir(influencer_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"generated_{stamp}{extension}"
        target.write_bytes(image_bytes)
        return target

    def _get_api_key(self, api_key_env: str) -> str:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key and api_key_env == "GEMINI_API_KEY":
            api_key = (self.settings.gemini_api_key or "").strip()
        if not api_key:
            raise ValueError(f"Missing {api_key_env}")
        return api_key
