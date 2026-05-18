"""Register all FastAPI routers on an app instance."""
from __future__ import annotations

from fastapi import FastAPI

from app.routes.api import router as api_router
from app.routes.page import router as page_router


def register_routes(app: FastAPI) -> None:
    app.include_router(page_router)
    app.include_router(api_router)
