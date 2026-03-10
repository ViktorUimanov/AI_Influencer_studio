from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PersonaRecord


@dataclass(slots=True)
class PersonaProfile:
    persona_id: str
    name: str
    summary: str
    visual_features: list[str] = field(default_factory=list)
    style_keywords: list[str] = field(default_factory=list)
    content_preferences: list[str] = field(default_factory=list)
    substitution_constraints: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict) -> "PersonaProfile":
        return cls(
            persona_id=str(payload.get("persona_id") or "default-persona"),
            name=str(payload.get("name") or "Persona"),
            summary=str(payload.get("summary") or ""),
            visual_features=[str(v) for v in (payload.get("visual_features") or []) if str(v).strip()],
            style_keywords=[str(v) for v in (payload.get("style_keywords") or []) if str(v).strip()],
            content_preferences=[str(v) for v in (payload.get("content_preferences") or []) if str(v).strip()],
            substitution_constraints=[
                str(v) for v in (payload.get("substitution_constraints") or []) if str(v).strip()
            ],
            avoid=[str(v) for v in (payload.get("avoid") or []) if str(v).strip()],
        )

    def to_dict(self) -> dict:
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "summary": self.summary,
            "visual_features": self.visual_features,
            "style_keywords": self.style_keywords,
            "content_preferences": self.content_preferences,
            "substitution_constraints": self.substitution_constraints,
            "avoid": self.avoid,
        }

    def to_prompt_block(self) -> str:
        sections: list[str] = [
            f"Persona ID: {self.persona_id}",
            f"Persona Name: {self.name}",
            f"Persona Summary: {self.summary}",
        ]

        def _add_list(title: str, values: list[str]) -> None:
            if not values:
                sections.append(f"{title}: (none)")
                return
            joined = "\n".join([f"- {value}" for value in values])
            sections.append(f"{title}:\n{joined}")

        _add_list("Visual Features", self.visual_features)
        _add_list("Style Keywords", self.style_keywords)
        _add_list("Content Preferences", self.content_preferences)
        _add_list("Substitution Constraints", self.substitution_constraints)
        _add_list("Avoid", self.avoid)
        return "\n".join(sections)


def load_persona(persona_path: Path | None) -> PersonaProfile | None:
    if persona_path is None:
        return None
    if not persona_path.exists():
        raise FileNotFoundError(f"Persona file not found: {persona_path}")

    payload = json.loads(persona_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Persona file must contain a JSON object: {persona_path}")
    return PersonaProfile.from_dict(payload)


def load_persona_from_db(db: Session, persona_id: str) -> PersonaProfile | None:
    normalized_id = str(persona_id or "").strip()
    if not normalized_id:
        return None
    stmt = select(PersonaRecord).where(PersonaRecord.persona_id == normalized_id).limit(1)
    record = db.execute(stmt).scalar_one_or_none()
    if record is None:
        return None
    payload = record.payload or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Persona payload must be a JSON object for persona_id={normalized_id}")
    return PersonaProfile.from_dict(payload)


def save_persona_to_db(db: Session, persona: PersonaProfile, source_path: Path | None = None) -> PersonaRecord:
    stmt = select(PersonaRecord).where(PersonaRecord.persona_id == persona.persona_id).limit(1)
    record = db.execute(stmt).scalar_one_or_none()
    if record is None:
        record = PersonaRecord(
            persona_id=persona.persona_id,
            name=persona.name,
            payload=persona.to_dict(),
            source_path=str(source_path) if source_path else None,
        )
        db.add(record)
    else:
        record.name = persona.name
        record.payload = persona.to_dict()
        record.source_path = str(source_path) if source_path else record.source_path
    db.commit()
    db.refresh(record)
    return record


def resolve_persona(
    *,
    db: Session | None = None,
    persona_id: str | None = None,
    persona_path: Path | None = None,
    prefer_db: bool = True,
    sync_file_to_db: bool = False,
) -> PersonaProfile | None:
    normalized_id = str(persona_id or "").strip()
    if prefer_db and db is not None and normalized_id:
        persona = load_persona_from_db(db=db, persona_id=normalized_id)
        if persona is not None:
            return persona

    persona = load_persona(persona_path)
    if persona is not None and db is not None and sync_file_to_db:
        save_persona_to_db(db=db, persona=persona, source_path=persona_path)
        if prefer_db and normalized_id and persona.persona_id != normalized_id:
            raise ValueError(
                f"Persona file id={persona.persona_id!r} does not match requested persona_id={normalized_id!r}"
            )
    return persona


def save_persona(persona: PersonaProfile, persona_path: Path) -> Path:
    persona_path.parent.mkdir(parents=True, exist_ok=True)
    persona_path.write_text(json.dumps(persona.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return persona_path
