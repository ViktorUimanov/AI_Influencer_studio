from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.picture_ideas import GeneratePictureIdeasRequest, PictureIdeaOut
from app.services.picture_ideas import PictureIdeaService

router = APIRouter(prefix="/api/v1/picture-ideas", tags=["picture-ideas"])


@router.post("/generate", response_model=list[PictureIdeaOut])
def generate_picture_ideas(
    request: GeneratePictureIdeasRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[PictureIdeaOut]:
    service = PictureIdeaService(db=db, settings=settings)
    try:
        ideas = service.generate(
            influencer_id=request.influencer_id,
            platforms=request.platforms,
            limit=request.limit,
            run_ids=request.run_ids,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "onboarding required" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return [PictureIdeaOut.model_validate(idea) for idea in ideas]


@router.get("", response_model=list[PictureIdeaOut])
def list_picture_ideas(
    influencer_id: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[PictureIdeaOut]:
    service = PictureIdeaService(db=db, settings=settings)
    ideas = service.list_ideas(influencer_id=influencer_id, limit=limit)
    return [PictureIdeaOut.model_validate(idea) for idea in ideas]
