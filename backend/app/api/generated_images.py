import requests

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.generated_images import GenerateImageRequest, GeneratedImageOut
from app.services.generated_images import GeneratedImageService

router = APIRouter(prefix="/api/v1/generated-images", tags=["generated-images"])


@router.post("/generate", response_model=GeneratedImageOut)
def generate_image(
    request: GenerateImageRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GeneratedImageOut:
    service = GeneratedImageService(db=db, settings=settings)
    try:
        record = service.generate(
            influencer_id=request.influencer_id,
            prompt=request.prompt,
            picture_idea_id=request.picture_idea_id,
            reference_image_path=request.reference_image_path,
            model=request.model,
            api_key_env=request.api_key_env,
            aspect_ratio=request.aspect_ratio,
            hashtag_strategy=request.hashtag_strategy,
            hashtag_platforms=request.hashtag_platforms,
            trend_run_ids=request.trend_run_ids,
            trend_window_days=request.trend_window_days,
            max_hashtags=request.max_hashtags,
            mock=request.mock,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "onboarding required" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GeneratedImageOut.model_validate(record)


@router.get("", response_model=list[GeneratedImageOut])
def list_generated_images(
    influencer_id: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[GeneratedImageOut]:
    service = GeneratedImageService(db=db, settings=settings)
    records = service.list_images(influencer_id=influencer_id, limit=limit)
    return [GeneratedImageOut.model_validate(record) for record in records]
