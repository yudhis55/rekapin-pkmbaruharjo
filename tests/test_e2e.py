"""End-to-end integration tests for the full scrape flow.

Uses TestClient + heavily mocked scraper modules. Real SQLite DB.
Verifies: POST /api/scrape -> visits in DB -> /api/recap reflects totals.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scraper.types import VisitData


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    db_file = tmp_path / "e2e.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    from config.settings import get_settings
    get_settings.cache_clear()
    import app.db.session as db_mod
    db_mod._engine = None
    db_mod._sessionmaker = None
    yield


def _patch_scraper(monkeypatch: pytest.MonkeyPatch, visits_per_call: list[list[VisitData]]) -> None:
    """Patch orchestrator's scraper functions. Each call to extract_visits returns the next batch."""
    from scraper import orchestrator

    call_idx = {"n": 0}

    @asynccontextmanager
    async def _br(*a, **k):
        yield ("b", "c", "p")

    async def _ok(*a, **k):
        return None

    async def _extract(page, selectors, fallback_date=None, on_progress=None):
        idx = call_idx["n"]
        call_idx["n"] += 1
        batch = visits_per_call[idx] if idx < len(visits_per_call) else []
        if on_progress:
            await on_progress(0, len(batch), "start")
            for i, v in enumerate(batch, 1):
                await on_progress(i, len(batch), f"visit {i}")
        return list(batch)

    monkeypatch.setattr(orchestrator, "playwright_browser", _br)
    monkeypatch.setattr(orchestrator, "scraper_login", _ok)
    monkeypatch.setattr(orchestrator, "go_to_pendaftaran_induk", _ok)
    monkeypatch.setattr(orchestrator, "apply_filter", _ok)
    monkeypatch.setattr(orchestrator, "extract_visits", _extract)


def _wait_for_job_status(client: TestClient, job_id: int, target: str, timeout: float = 10.0) -> dict:
    """Poll GET /api/scrape/{id} until status matches or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/scrape/{job_id}")
        if r.status_code == 200:
            data = r.json()
            if data["status"] == target:
                return data
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach status={target} within {timeout}s")


def _make_visit(no_rm: str, ruang: str, tanggal: date) -> VisitData:
    import hashlib
    emr_id = hashlib.md5(f"{no_rm}_{ruang}_{tanggal}".encode()).hexdigest()[:12]
    return VisitData(
        no_rm=no_rm,
        nama=f"Sample {no_rm}",
        tgl_lahir=date(1990, 1, 1),
        ruang=ruang,
        tanggal_kunjungan=tanggal,
        total_biaya=Decimal("0.00"),
        treatments=tuple(),
        emr_visit_id=emr_id,
        cara_bayar="UMUM",
        bayar_url=None,
    )


def test_e2e_full_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    visits = [
        _make_visit("RM001", "POLI UMUM", date(2026, 5, 16)),
        _make_visit("RM002", "POLI GIGI", date(2026, 5, 16)),
        _make_visit("RM003", "POLI UMUM", date(2026, 5, 16)),
    ]
    _patch_scraper(monkeypatch, [visits])

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape", json={"mode": "single", "tanggal_from": "2026-05-16"})
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        _wait_for_job_status(client, job_id, "done")

        # Visits endpoint
        r2 = client.get("/api/visits", params={"tanggal_from": "2026-05-16"})
        assert r2.status_code == 200
        v = r2.json()
        assert len(v) == 3

        # Recap endpoint
        r3 = client.get("/api/recap")
        assert r3.status_code == 200
        recaps = r3.json()
        assert len(recaps) == 1
        assert recaps[0]["tanggal_kunjungan"] == "2026-05-16"
        assert recaps[0]["total_pasien"] == 3


def test_e2e_rescrape_updates_recap_not_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run scrape twice for same date; recap should remain ONE row, updated."""
    first = [_make_visit("RM001", "POLI UMUM", date(2026, 5, 16))]
    second = [
        _make_visit("RM001", "POLI UMUM", date(2026, 5, 16)),
        _make_visit("RM002", "POLI GIGI", date(2026, 5, 16)),
    ]
    _patch_scraper(monkeypatch, [first, second])

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r1 = client.post("/api/scrape", json={"mode": "single", "tanggal_from": "2026-05-16"})
        job1 = r1.json()["job_id"]
        _wait_for_job_status(client, job1, "done")

        r2 = client.post("/api/scrape", json={"mode": "single", "tanggal_from": "2026-05-16"})
        job2 = r2.json()["job_id"]
        _wait_for_job_status(client, job2, "done")

        # Recap must still have only ONE row
        rec = client.get("/api/recap").json()
        same_date = [r for r in rec if r["tanggal_kunjungan"] == "2026-05-16"]
        assert len(same_date) == 1
        assert same_date[0]["total_pasien"] == 2


def test_e2e_range_iterates_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    day1 = [_make_visit("RM001", "POLI UMUM", date(2026, 5, 15))]
    day2 = [
        _make_visit("RM002", "POLI UMUM", date(2026, 5, 16)),
        _make_visit("RM003", "POLI GIGI", date(2026, 5, 16)),
    ]
    _patch_scraper(monkeypatch, [day1, day2])

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape", json={
            "mode": "range",
            "tanggal_from": "2026-05-15",
            "tanggal_to": "2026-05-16",
        })
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        _wait_for_job_status(client, job_id, "done")

        rec = client.get("/api/recap").json()
        dates = sorted(r["tanggal_kunjungan"] for r in rec)
        assert dates == ["2026-05-15", "2026-05-16"]


def test_e2e_login_failure_marks_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from scraper import orchestrator
    from scraper.exceptions import LoginError

    @asynccontextmanager
    async def _br(*a, **k):
        yield ("b", "c", "p")

    async def _bad(*a, **k):
        raise LoginError("invalid")

    async def _ok(*a, **k):
        return None

    monkeypatch.setattr(orchestrator, "playwright_browser", _br)
    monkeypatch.setattr(orchestrator, "scraper_login", _bad)
    monkeypatch.setattr(orchestrator, "go_to_pendaftaran_induk", _ok)
    monkeypatch.setattr(orchestrator, "apply_filter", _ok)

    async def _ev(*a, **k):
        return []

    monkeypatch.setattr(orchestrator, "extract_visits", _ev)

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/scrape", json={"mode": "single", "tanggal_from": "2026-05-16"})
        job_id = r.json()["job_id"]
        data = _wait_for_job_status(client, job_id, "error")
        assert "invalid" in (data.get("error_message") or "").lower()
