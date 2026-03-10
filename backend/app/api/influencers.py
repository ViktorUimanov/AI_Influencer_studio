from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.influencers import InfluencerOut, InfluencerStatusOut, InfluencerUpsertRequest
from app.services.influencers import InfluencerService

router = APIRouter(prefix="/api/v1/influencers", tags=["influencers"])


@router.get("", response_model=list[InfluencerStatusOut])
def list_influencers(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[InfluencerStatusOut]:
    service = InfluencerService(db=db, settings=settings)
    records = service.list_influencers()
    return [
        InfluencerStatusOut.model_validate(
            {
                **InfluencerOut.model_validate(record).model_dump(),
                "onboarding_complete": service.is_onboarding_complete(record),
            }
        )
        for record in records
    ]


@router.get("/{influencer_id}", response_model=InfluencerStatusOut)
def get_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InfluencerStatusOut:
    service = InfluencerService(db=db, settings=settings)
    record = service.get_influencer(influencer_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Influencer not found")
    return InfluencerStatusOut.model_validate(
        {
            **InfluencerOut.model_validate(record).model_dump(),
            "onboarding_complete": service.is_onboarding_complete(record),
        }
    )


@router.put("/{influencer_id}", response_model=InfluencerStatusOut)
def upsert_influencer(
    influencer_id: str,
    request: InfluencerUpsertRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InfluencerStatusOut:
    service = InfluencerService(db=db, settings=settings)
    try:
        record = service.upsert_influencer(
            influencer_id=influencer_id,
            name=request.name,
            description=request.description,
            hashtags=request.hashtags,
            video_suggestions_requirement=request.video_suggestions_requirement,
            reference_image_path=request.reference_image_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InfluencerStatusOut.model_validate(
        {
            **InfluencerOut.model_validate(record).model_dump(),
            "onboarding_complete": service.is_onboarding_complete(record),
        }
    )


@router.post("/onboarding", response_model=InfluencerStatusOut)
def onboarding(
    influencer_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    hashtags: str = Form(...),
    video_suggestions_requirement: str = Form(...),
    reference_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InfluencerStatusOut:
    service = InfluencerService(db=db, settings=settings)
    parsed_hashtags = [item.strip() for item in hashtags.split(",") if item.strip()]
    try:
        record = service.onboard(
            influencer_id=influencer_id,
            name=name,
            description=description,
            hashtags=parsed_hashtags,
            video_suggestions_requirement=video_suggestions_requirement,
            reference_image=reference_image,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InfluencerStatusOut.model_validate(
        {
            **InfluencerOut.model_validate(record).model_dump(),
            "onboarding_complete": service.is_onboarding_complete(record),
        }
    )
