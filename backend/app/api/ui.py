from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])


@router.get("/ui", response_class=HTMLResponse)
def ui_page() -> HTMLResponse:
    html_path = Path(__file__).resolve().parents[1] / "web" / "index.html"
    html = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)
