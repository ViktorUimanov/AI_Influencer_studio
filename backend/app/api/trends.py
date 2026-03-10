from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.trends import (
    DownloadItemRequest,
    DownloadRunRequest,
    IngestTrendsRequest,
    TrendDownloadOut,
    TrendItemOut,
    TrendRunDetailOut,
    TrendRunOut,
    TrendSignalOut,
)
from app.services.downloader import TrendDownloadService
from app.services.trend_parser import TrendParserService

router = APIRouter(prefix="/api/v1/trends", tags=["trends"])


@router.post("/ingest", response_model=TrendRunDetailOut)
def ingest_trends(
    request: IngestTrendsRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrendRunDetailOut:
    service = TrendParserService(db=db, settings=settings)
    try:
        run = service.ingest(
            platforms=request.platforms,
            limit_per_platform=request.limit_per_platform,
            source=request.source,
            sources_by_platform={k.lower(): v for k, v in request.sources.items()},
            selectors={k.lower(): v.model_dump() for k, v in request.selectors.items()},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TrendRunDetailOut.model_validate(run)


@router.get("/runs", response_model=list[TrendRunOut])
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[TrendRunOut]:
    service = TrendParserService(db=db, settings=settings)
    runs = service.list_runs(limit=limit)
    return [TrendRunOut.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=TrendRunDetailOut)
def get_run(run_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> TrendRunDetailOut:
    service = TrendParserService(db=db, settings=settings)
    run = service.get_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return TrendRunDetailOut.model_validate(run)


@router.get("/latest", response_model=TrendRunDetailOut)
def latest_for_platform(
    platform: str = Query(..., pattern="^(tiktok|instagram)$"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrendRunDetailOut:
    service = TrendParserService(db=db, settings=settings)
    run = service.latest_for_platform(platform=platform)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No runs found for platform={platform}")
    return TrendRunDetailOut.model_validate(run)


@router.get("/items", response_model=list[TrendItemOut])
def list_items(
    platform: str | None = Query(default=None, pattern="^(tiktok|instagram)$"),
    run_id: int | None = Query(default=None, ge=1),
    hashtag: str | None = Query(default=None),
    query: str | None = Query(default=None),
    min_views: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[TrendItemOut]:
    service = TrendParserService(db=db, settings=settings)
    items = service.list_items(
        platform=platform,
        run_id=run_id,
        hashtag=hashtag,
        query=query,
        min_views=min_views,
        limit=limit,
    )
    return [TrendItemOut.model_validate(i) for i in items]


@router.get("/signals", response_model=list[TrendSignalOut])
def list_signals(
    platform: str | None = Query(default=None, pattern="^(tiktok|instagram)$"),
    signal_type: str | None = Query(default=None, pattern="^(hashtag|audio|topic|style|hook)$"),
    run_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[TrendSignalOut]:
    service = TrendParserService(db=db, settings=settings)
    signals = service.list_signals(platform=platform, signal_type=signal_type, run_id=run_id, limit=limit)
    return [TrendSignalOut.model_validate(s) for s in signals]


@router.post("/downloads/item/{item_id}", response_model=TrendDownloadOut)
def download_item(
    item_id: int,
    request: DownloadItemRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrendDownloadOut:
    service = TrendDownloadService(db=db, settings=settings)
    try:
        record = service.download_item(
            item_id=item_id,
            force=request.force,
            download_dir=request.download_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TrendDownloadOut.model_validate(record)


@router.post("/downloads/run", response_model=list[TrendDownloadOut])
def download_run(
    request: DownloadRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[TrendDownloadOut]:
    service = TrendDownloadService(db=db, settings=settings)
    records = service.download_from_run(
        run_id=request.run_id,
        platform=request.platform,
        limit=request.limit,
        force=request.force,
        download_dir=request.download_dir,
    )
    return [TrendDownloadOut.model_validate(record) for record in records]


@router.get("/downloads", response_model=list[TrendDownloadOut])
def list_downloads(
    run_id: int | None = Query(default=None, ge=1),
    trend_item_id: int | None = Query(default=None, ge=1),
    platform: str | None = Query(default=None, pattern="^(tiktok|instagram)$"),
    status: str | None = Query(default=None, pattern="^(running|downloaded|failed|skipped)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[TrendDownloadOut]:
    service = TrendDownloadService(db=db, settings=settings)
    records = service.list_downloads(
        run_id=run_id,
        trend_item_id=trend_item_id,
        platform=platform,
        status=status,
        limit=limit,
    )
    return [TrendDownloadOut.model_validate(record) for record in records]
