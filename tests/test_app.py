"""Tests for FastAPI app skeleton."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scraper.exceptions import LoginError


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")

    from config.settings import get_settings
    get_settings.cache_clear()

    import app.db.session as db_session_mod
    db_session_mod._engine = None
    db_session_mod._sessionmaker = None
    yield
    db_session_mod._engine = None
    db_session_mod._sessionmaker = None


def test_app_has_routes() -> None:
    from app.main import create_app
    app = create_app()
    paths = [r.path for r in app.routes]
    # /docs and /static are always there
    assert any("/docs" in p for p in paths)


def test_app_lifespan_initializes_db() -> None:
    """Hit a static-style endpoint via TestClient to drive lifespan."""
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        # Lifespan runs on enter -> tables should exist
        from app.db.session import get_engine
        engine = get_engine()
        assert engine is not None


def test_login_error_handler_returns_401() -> None:
    from fastapi import APIRouter
    from app.main import create_app

    app = create_app()
    router = APIRouter()

    @router.get("/_test_raise_login")
    async def raise_login() -> None:
        raise LoginError("bad creds")

    app.include_router(router)

    with TestClient(app) as client:
        r = client.get("/_test_raise_login")
        assert r.status_code == 401
        body = r.json()
        assert body["error"] == "login_failed"


def test_unknown_route_returns_404() -> None:
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/this-route-does-not-exist")
        assert r.status_code == 404
