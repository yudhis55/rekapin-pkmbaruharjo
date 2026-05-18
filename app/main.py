"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.db.init_db import init_db
from scraper.exceptions import (
    JobAlreadyRunningError,
    LoginError,
    NavigationError,
    ScraperError,
    SessionExpiredError,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
TEMPLATES_DIR = ROOT / "templates"

# Module-level Jinja2 templates instance for routes to use
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run init_db on startup."""
    logger.info("lifespan: initializing db")
    await init_db()
    yield
    logger.info("lifespan: shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Rekap-In",
        description="Aplikasi scraping dan rekapitulasi data EMR Puskesmas Baruharjo",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
    )

    # NOTE: CORS NOT enabled - this is a single-origin local app
    # No middleware for cross-origin (security defense)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.exception_handler(LoginError)
    async def _login_handler(request: Request, exc: LoginError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "login_failed", "detail": str(exc)})

    @app.exception_handler(SessionExpiredError)
    async def _session_handler(request: Request, exc: SessionExpiredError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "session_expired", "detail": str(exc)})

    @app.exception_handler(JobAlreadyRunningError)
    async def _conflict_handler(request: Request, exc: JobAlreadyRunningError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "job_already_running", "detail": str(exc)})

    @app.exception_handler(NavigationError)
    async def _nav_handler(request: Request, exc: NavigationError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": "navigation_failed", "detail": str(exc)})

    @app.exception_handler(ScraperError)
    async def _scraper_handler(request: Request, exc: ScraperError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "scraper_error", "detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _val_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "validation_error", "detail": exc.errors()})

    from app.routes import register_routes
    register_routes(app)

    return app


app = create_app()
