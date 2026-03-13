from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.pipeline import PipelineRunDetailOut, PipelineRunOut, PipelineRunRequest, PipelineRunSummaryOut
from app.services.pipeline_history import PipelineHistoryService
from app.services.pipeline_runner import PipelineRunnerService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.post("/run", response_model=PipelineRunOut)
def run_pipeline(
    request: PipelineRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PipelineRunOut:
    service = PipelineRunnerService(db=db, settings=settings)
    try:
        return service.run(request)
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "onboarding required" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/runs", response_model=list[PipelineRunSummaryOut])
def list_pipeline_runs(
    influencer_id: str | None = None,
    settings: Settings = Depends(get_settings),
) -> list[PipelineRunSummaryOut]:
    service = PipelineHistoryService(settings=settings)
    return service.list_runs(influencer_id=influencer_id)


@router.get("/runs/{influencer_id}/{run_id}", response_model=PipelineRunDetailOut)
def get_pipeline_run(
    influencer_id: str,
    run_id: str,
    settings: Settings = Depends(get_settings),
) -> PipelineRunDetailOut:
    service = PipelineHistoryService(settings=settings)
    record = service.get_run(influencer_id=influencer_id, run_id=run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return record
