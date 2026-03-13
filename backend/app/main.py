from dotenv import load_dotenv

load_dotenv()  # export .env vars into os.environ for os.getenv() callers

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.generated_images import router as generated_images_router
from app.api.influencers import router as influencers_router
from app.api.pipeline import router as pipeline_router
from app.api.picture_ideas import router as picture_ideas_router
from app.api.x_content import router as x_content_router

from app.api.trends import router as trends_router
from app.api.ui import router as ui_router
from app.core.config import get_settings
from app.db.migrations import run_prototype_migrations
from app.db.base import Base
from app.db.session import engine

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    run_prototype_migrations(engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


app.include_router(trends_router)
app.include_router(influencers_router)
app.include_router(pipeline_router)
app.include_router(picture_ideas_router)
app.include_router(generated_images_router)
app.include_router(x_content_router)
app.include_router(ui_router)
