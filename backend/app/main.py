from fastapi import FastAPI

from app.api.trends import router as trends_router
from app.api.ui import router as ui_router
from app.core.config import get_settings
from app.db.migrations import run_prototype_migrations
from app.db.base import Base
from app.db.session import engine

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    run_prototype_migrations(engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


app.include_router(trends_router)
app.include_router(ui_router)
