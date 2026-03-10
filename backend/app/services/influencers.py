from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import InfluencerProfile
from app.pipelines.persona import PersonaProfile


class InfluencerService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def list_influencers(self) -> list[InfluencerProfile]:
        stmt = select(InfluencerProfile).order_by(InfluencerProfile.updated_at.desc(), InfluencerProfile.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_influencer(self, influencer_id: str) -> InfluencerProfile | None:
        normalized = self._normalize_influencer_id(influencer_id)
        if not normalized:
            return None
        stmt = select(InfluencerProfile).where(InfluencerProfile.influencer_id == normalized).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert_influencer(
        self,
        *,
        influencer_id: str,
        name: str,
        description: str,
        hashtags: list[str],
        reference_image_path: str | None,
    ) -> InfluencerProfile:
        normalized_id = self._normalize_influencer_id(influencer_id)
        if not normalized_id:
            raise ValueError("influencer_id is required")

        record = self.get_influencer(normalized_id)
        cleaned_hashtags = self._normalize_hashtags(hashtags)
        if record is None:
            record = InfluencerProfile(
                influencer_id=normalized_id,
                name=name.strip(),
                description=description.strip(),
                hashtags=cleaned_hashtags,
                reference_image_path=reference_image_path,
            )
            self.db.add(record)
        else:
            record.name = name.strip()
            record.description = description.strip()
            record.hashtags = cleaned_hashtags
            if reference_image_path:
                record.reference_image_path = reference_image_path

        self.db.commit()
        self.db.refresh(record)
        return record

    def onboard(
        self,
        *,
        influencer_id: str,
        name: str,
        description: str,
        hashtags: list[str],
        reference_image: UploadFile,
    ) -> InfluencerProfile:
        normalized_id = self._normalize_influencer_id(influencer_id)
        if not normalized_id:
            raise ValueError("influencer_id is required")
        image_path = self._save_reference_image(normalized_id, reference_image)
        return self.upsert_influencer(
            influencer_id=normalized_id,
            name=name,
            description=description,
            hashtags=hashtags,
            reference_image_path=str(image_path),
        )

    def require_ready_influencer(self, influencer_id: str) -> InfluencerProfile:
        record = self.get_influencer(influencer_id)
        if record is None or not self.is_onboarding_complete(record):
            raise ValueError("Influencer onboarding required. Provide reference image, description, and hashtags first.")
        return record

    def is_onboarding_complete(self, record: InfluencerProfile) -> bool:
        if not record.reference_image_path:
            return False
        if not record.description or not record.description.strip():
            return False
        if not record.hashtags:
            return False
        return True

    def to_persona_profile(self, record: InfluencerProfile) -> PersonaProfile:
        hashtags = [tag for tag in (record.hashtags or []) if str(tag).strip()]
        return PersonaProfile(
            persona_id=f"influencer_{record.influencer_id}",
            name=record.name,
            summary=record.description or "",
            visual_features=[],
            style_keywords=hashtags[:8],
            content_preferences=hashtags[:12],
            substitution_constraints=[
                "prefer a single dominant person in frame",
                "reference face should remain visible for replacement",
                "stable enough motion and lighting for subject substitution",
            ],
            avoid=[
                "heavy face occlusion",
                "large groups with no clear main subject",
                "content unrelated to the influencer description or hashtags",
            ],
        )

    def _save_reference_image(self, influencer_id: str, reference_image: UploadFile) -> Path:
        suffix = Path(reference_image.filename or "").suffix.lower() or ".jpg"
        target_dir = self.settings.influencers_data_dir / influencer_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"reference{suffix}"
        with target_path.open("wb") as fh:
            shutil.copyfileobj(reference_image.file, fh)
        return target_path.resolve()

    def _normalize_influencer_id(self, raw: str) -> str:
        value = re.sub(r"[^a-z0-9_-]+", "-", str(raw or "").strip().lower()).strip("-")
        return value[:128]

    def _normalize_hashtags(self, hashtags: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for raw in hashtags:
            clean = str(raw or "").strip().lstrip("#").lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            output.append(clean)
        return output
