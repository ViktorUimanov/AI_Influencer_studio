from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.pipeline import PipelineRunOut, PipelineRunRequest
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
