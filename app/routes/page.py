"""HTML page routes (Jinja-rendered)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from config.ruang import RUANG_LIST

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    import app.main as _main  # lazy import to avoid circular
    return _main.templates.TemplateResponse(
        request,
        "index.html",
        {
            "ruang_list": RUANG_LIST,
            "today": date.today().isoformat(),
            "app_title": "Rekap-In",
        },
    )
