"""Tests for scrape endpoints."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    db_file = tmp_path / "t.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    from config.settings import get_settings
    get_settings.cache_clear()
    import app.db.session as db_mod
    db_mod._engine = None
    db_mod._sessionmaker = None
    yield


def _patch_orch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace orchestrator browser/scraper calls with no-ops returning empty visits."""
    from scraper import orchestrator
    @asynccontextmanager
    async def _br(*a, **k):
        yield ("b", "c", "p")
    async def _ok(*a, **k):
        return None
    async def _extract(*a, **k):
        return []
    monkeypatch.setattr(orchestrator, "playwright_browser", _br)
    monkeypatch.setattr(orchestrator, "scraper_login", _ok)
    monkeypatch.setattr(orchestrator, "go_to_pendaftaran_induk", _ok)
    monkeypatch.setattr(orchestrator, "apply_filter", _ok)
    monkeypatch.setattr(orchestrator, "extract_visits", _extract)


def test_post_scrape_creates_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_orch(monkeypatch)
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape", json={
            "mode": "single",
            "tanggal_from": "2026-05-16",
        })
        assert r.status_code == 202
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "pending"


def test_post_scrape_invalid_dates_returns_422() -> None:
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape", json={
            "mode": "range",
            "tanggal_from": "2026-05-20",
            "tanggal_to": "2026-05-15",
        })
        assert r.status_code == 422


def test_post_scrape_concurrent_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-create a running job in DB, then try to trigger another."""
    from app.main import create_app
    from app.db.repositories import job_repo
    from app.db.session import get_sessionmaker
    from models import JobStatus
    app = create_app()
    with TestClient(app) as client:
        # Drive lifespan first by hitting any endpoint
        client.get("/api/ruang")
        sm = get_sessionmaker()
        async def _seed():
            async with sm() as session:
                job = await job_repo.create_job(session, date(2026, 5, 16), date(2026, 5, 16), None)
                await job_repo.update_job_status(session, job.id, JobStatus.RUNNING)
        asyncio.get_event_loop().run_until_complete(_seed())
        r = client.post("/api/scrape", json={
            "mode": "single",
            "tanggal_from": "2026-05-16",
        })
        assert r.status_code == 409


def test_get_scrape_status_returns_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_orch(monkeypatch)
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape", json={
            "mode": "single",
            "tanggal_from": "2026-05-16",
        })
        job_id = r.json()["job_id"]
        # Allow background task to start
        import time as _t
        _t.sleep(0.05)
        r2 = client.get(f"/api/scrape/{job_id}")
        assert r2.status_code == 200
        body = r2.json()
        assert body["id"] == job_id
        assert body["status"] in ("pending", "running", "done")


def test_post_cancel_unknown_job_returns_404() -> None:
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape/99999/cancel")
        assert r.status_code == 404
