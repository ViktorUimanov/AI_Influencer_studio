import requests

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.x_content import (
    XCollectRequest,
    XDraftGenerateRequest,
    XDraftOut,
    XPostOut,
    XTrendRunDetailOut,
    XTrendRunOut,
    XTrendTopicOut,
)
from app.schemas.x_pipeline import XPipelineRunOut, XPipelineRunRequest
from app.services.x_content import XContentService
from app.services.x_pipeline import XPipelineService

router = APIRouter(prefix="/api/v1/x", tags=["x"])


@router.post("/collect", response_model=XTrendRunDetailOut)
def collect_x_content(
    request: XCollectRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> XTrendRunDetailOut:
    service = XContentService(db=db, settings=settings)
    try:
        run = service.collect(
            query=request.query,
            location_woeid=request.location_woeid,
            max_topics=request.max_topics,
            max_posts=request.max_posts,
            result_type=request.result_type,
            only_with_images=request.only_with_images,
            lang=request.lang,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except requests.RequestException as exc:  # type: ignore[name-defined]
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return XTrendRunDetailOut.model_validate(run)


@router.post("/pipeline/run", response_model=XPipelineRunOut)
def run_x_pipeline(
    request: XPipelineRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> XPipelineRunOut:
    service = XPipelineService(db=db, settings=settings)
    try:
        return service.run(
            influencer_id=request.influencer_id,
            mode=request.mode,
            location_woeid=request.location_woeid,
            max_trending_topics=request.max_trending_topics,
            selected_topics_limit=request.selected_topics_limit,
            max_posts_per_topic=request.max_posts_per_topic,
            max_total_posts=request.max_total_posts,
            draft_limit=request.draft_limit,
            image_mode=request.image_mode,
            lang=request.lang,
            model=request.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/runs", response_model=list[XTrendRunOut])
def list_x_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[XTrendRunOut]:
    service = XContentService(db=db, settings=settings)
    return [XTrendRunOut.model_validate(run) for run in service.list_runs(limit=limit)]


@router.get("/runs/{run_id}", response_model=XTrendRunDetailOut)
def get_x_run(
    run_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> XTrendRunDetailOut:
    service = XContentService(db=db, settings=settings)
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="X trend run not found")
    return XTrendRunDetailOut.model_validate(run)


@router.get("/topics", response_model=list[XTrendTopicOut])
def list_x_topics(
    run_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[XTrendTopicOut]:
    service = XContentService(db=db, settings=settings)
    return [XTrendTopicOut.model_validate(topic) for topic in service.list_topics(run_id=run_id, limit=limit)]


@router.get("/posts", response_model=list[XPostOut])
def list_x_posts(
    run_id: int | None = Query(default=None, ge=1),
    only_with_images: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[XPostOut]:
    service = XContentService(db=db, settings=settings)
    return [
        XPostOut.model_validate(post)
        for post in service.list_posts(run_id=run_id, only_with_images=only_with_images, limit=limit)
    ]


@router.post("/drafts/generate", response_model=list[XDraftOut])
def generate_x_drafts(
    request: XDraftGenerateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[XDraftOut]:
    service = XContentService(db=db, settings=settings)
    try:
        drafts = service.generate_drafts(
            run_id=request.run_id,
            limit=request.limit,
            require_images=request.require_images,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [XDraftOut.model_validate(draft) for draft in drafts]


@router.get("/drafts", response_model=list[XDraftOut])
def list_x_drafts(
    run_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[XDraftOut]:
    service = XContentService(db=db, settings=settings)
    return [XDraftOut.model_validate(draft) for draft in service.list_drafts(run_id=run_id, limit=limit)]
