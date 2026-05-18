"""Tests for data API routes."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
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


async def _seed(client: TestClient) -> None:
    """Seed database with sample visits + recap via direct repo calls."""
    from app.db.repositories import visit_repo, recap_repo
    from app.db.session import get_sessionmaker
    sm = get_sessionmaker()
    async with sm() as session:
        await visit_repo.upsert_visit(
            session,
            visit_repo.VisitInput(
                emr_visit_id="EMR001",
                no_rm="RM001", nama="Sample 1", tgl_lahir=date(1990, 1, 1),
                ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 15),
                cara_bayar="UMUM",
                total_biaya=Decimal("0.00"),
            ),
            [],
        )
        await visit_repo.upsert_visit(
            session,
            visit_repo.VisitInput(
                emr_visit_id="EMR002",
                no_rm="RM002", nama="Sample 2", tgl_lahir=None,
                ruang="POLI GIGI", tanggal_kunjungan=date(2026, 5, 16),
                cara_bayar="BPJS",
                total_biaya=Decimal("0.00"),
            ),
            [],
        )
        await recap_repo.upsert_recap(session, date(2026, 5, 15))
        await recap_repo.upsert_recap(session, date(2026, 5, 16))


def test_get_visits_default_range_filters_correctly() -> None:
    import asyncio
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        asyncio.get_event_loop().run_until_complete(_seed(client))
        r = client.get("/api/visits", params={"tanggal_from": "2026-05-15"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["no_rm"] == "RM001"


def test_get_visits_with_ruang_filter() -> None:
    import asyncio
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        asyncio.get_event_loop().run_until_complete(_seed(client))
        r = client.get("/api/visits", params={
            "tanggal_from": "2026-05-15",
            "tanggal_to": "2026-05-16",
            "ruang": "POLI GIGI",
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["ruang"] == "POLI GIGI"


def test_get_visits_with_cara_bayar_filter() -> None:
    import asyncio
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        asyncio.get_event_loop().run_until_complete(_seed(client))
        r = client.get("/api/visits", params={
            "tanggal_from": "2026-05-15",
            "tanggal_to": "2026-05-16",
            "cara_bayar": "BPJS",
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["cara_bayar"] == "BPJS"
        assert data[0]["no_rm"] == "RM002"


def test_get_visits_range_too_large_returns_422() -> None:
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/api/visits", params={
            "tanggal_from": "2026-01-01",
            "tanggal_to": "2026-03-15",
        })
        assert r.status_code == 422


def test_get_recap_returns_ordered_desc() -> None:
    import asyncio
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        asyncio.get_event_loop().run_until_complete(_seed(client))
        r = client.get("/api/recap")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        # Newest first
        assert data[0]["tanggal_kunjungan"] == "2026-05-16"


def test_get_recap_by_missing_date_returns_404() -> None:
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/api/recap/2099-01-01")
        assert r.status_code == 404
