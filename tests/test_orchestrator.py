"""Tests for scrape orchestrator."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.db.session import get_sessionmaker, make_engine
from app.schemas.dto import ScrapeRequest
from models import Base, JobStatus
from scraper import orchestrator
from scraper.exceptions import LoginError, SessionExpiredError
from scraper.types import TreatmentData, VisitData


@pytest.fixture(autouse=True)
async def _setup(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    monkeypatch.setenv("BROWSER_MODE", "headless")
    monkeypatch.setenv("SCRAPE_TIMEOUT", "10")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    from config.settings import get_settings
    get_settings.cache_clear()

    # Reset DB engine module-level globals
    import app.db.session as db_session_mod
    db_session_mod._engine = None
    db_session_mod._sessionmaker = None

    engine = make_engine("sqlite+aiosqlite:///:memory:")
    db_session_mod._engine = engine
    db_session_mod._sessionmaker = None  # rebuild from new engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    db_session_mod._engine = None
    db_session_mod._sessionmaker = None


class _FakePage:
    """Minimal fake page that supports wait_for_timeout."""

    async def wait_for_timeout(self, ms: int) -> None:
        pass


@asynccontextmanager
async def _fake_browser(*args, **kwargs):
    yield ("browser", "ctx", _FakePage())


def _patch_scraper_calls(monkeypatch: pytest.MonkeyPatch, visits: list[VisitData]) -> None:
    monkeypatch.setattr(orchestrator, "playwright_browser", _fake_browser)

    async def _login(page, selectors, settings):
        return None

    async def _nav(page, selectors):
        return None

    async def _filter(page, selectors, tanggal, ruang):
        return None

    async def _extract(page, selectors, fallback_date=None, on_progress=None):
        if on_progress:
            await on_progress(0, len(visits), "start")
            for i, _v in enumerate(visits, 1):
                await on_progress(i, len(visits), f"visit {i}")
        return list(visits)

    async def _is_logged_in(page, selectors):
        return True

    async def _extract_payment(page, selectors, bayar_url):
        return [], Decimal("0.00")

    monkeypatch.setattr(orchestrator, "scraper_login", _login)
    monkeypatch.setattr(orchestrator, "go_to_pendaftaran_induk", _nav)
    monkeypatch.setattr(orchestrator, "apply_filter", _filter)
    monkeypatch.setattr(orchestrator, "extract_visits", _extract)
    monkeypatch.setattr(orchestrator, "is_logged_in", _is_logged_in)
    monkeypatch.setattr(orchestrator, "extract_payment_details", _extract_payment)


async def _create_job(tanggal_from: date, tanggal_to: date, ruang: str | None = None) -> int:
    from app.db.repositories import job_repo
    sm = get_sessionmaker()
    async with sm() as session:
        job = await job_repo.create_job(session, tanggal_from, tanggal_to, ruang)
    return job.id


async def test_orchestrator_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    visits = [
        VisitData(
            emr_visit_id="V001", no_rm="RM1", nama="A", tgl_lahir=date(1990, 1, 1),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="UMUM", total_biaya=Decimal("0.00"), treatments=tuple(),
        ),
        VisitData(
            emr_visit_id="V002", no_rm="RM2", nama="B", tgl_lahir=None,
            ruang="POLI GIGI", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="UMUM", total_biaya=Decimal("0.00"), treatments=tuple(),
        ),
    ]
    _patch_scraper_calls(monkeypatch, visits)
    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))

    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16), tanggal_to=date(2026, 5, 16))
    await orchestrator.run_scrape_job(job_id, req)

    from app.db.repositories import job_repo, recap_repo, visit_repo
    sm = get_sessionmaker()
    async with sm() as session:
        all_visits = await visit_repo.list_visits(session, date(2026, 5, 16), date(2026, 5, 16))
        recap = await recap_repo.get_recap_by_date(session, date(2026, 5, 16))
        job = await job_repo.get_job(session, job_id)
    assert len(all_visits) == 2
    assert recap is not None
    assert recap.total_pasien == 2
    assert job is not None
    assert job.status == JobStatus.DONE


async def test_orchestrator_session_expiry_retries_once(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    @asynccontextmanager
    async def _br(*a, **k):
        yield ("b", "c", _FakePage())

    monkeypatch.setattr(orchestrator, "playwright_browser", _br)

    async def _ok(*a, **k):
        return None

    monkeypatch.setattr(orchestrator, "scraper_login", _ok)
    monkeypatch.setattr(orchestrator, "go_to_pendaftaran_induk", _ok)
    monkeypatch.setattr(orchestrator, "apply_filter", _ok)
    monkeypatch.setattr(orchestrator, "is_logged_in", _ok)
    monkeypatch.setattr(orchestrator, "extract_payment_details", _ok)

    async def _extract(page, selectors, fallback_date=None, on_progress=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise SessionExpiredError("expired mid-run")
        return []

    monkeypatch.setattr(orchestrator, "extract_visits", _extract)

    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))
    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16))
    await orchestrator.run_scrape_job(job_id, req)
    assert call_count["n"] == 2  # retried once


async def test_orchestrator_login_error_marks_error(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def _br(*a, **k):
        yield ("b", "c", _FakePage())

    monkeypatch.setattr(orchestrator, "playwright_browser", _br)

    async def _bad_login(*a, **k):
        raise LoginError("invalid credentials")

    monkeypatch.setattr(orchestrator, "scraper_login", _bad_login)

    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))
    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16))
    await orchestrator.run_scrape_job(job_id, req)

    from app.db.repositories import job_repo
    sm = get_sessionmaker()
    async with sm() as session:
        job = await job_repo.get_job(session, job_id)
    assert job is not None
    assert job.status == JobStatus.ERROR
    assert "invalid credentials" in (job.error_message or "")


async def test_orchestrator_concurrent_trigger_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db.repositories import job_repo
    from scraper.exceptions import JobAlreadyRunningError

    sm = get_sessionmaker()
    async with sm() as session:
        # Pre-create a running job
        job1 = await job_repo.create_job(session, date(2026, 5, 16), date(2026, 5, 16), None)
        await job_repo.update_job_status(session, job1.id, JobStatus.RUNNING)
        # Create job2 then mark it as ERROR so it's not "active" in the query
        job2 = await job_repo.create_job(session, date(2026, 5, 17), date(2026, 5, 17), None)
        await job_repo.update_job_status(session, job2.id, JobStatus.ERROR)

    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 17))
    with pytest.raises(JobAlreadyRunningError):
        await orchestrator.run_scrape_job(job2.id, req)


async def test_orchestrator_cancellation_marks_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def _br(*a, **k):
        yield ("b", "c", _FakePage())

    monkeypatch.setattr(orchestrator, "playwright_browser", _br)

    async def _ok(*a, **k):
        return None

    async def _slow_extract(*a, **k):
        await asyncio.sleep(5)
        return []

    monkeypatch.setattr(orchestrator, "scraper_login", _ok)
    monkeypatch.setattr(orchestrator, "go_to_pendaftaran_induk", _ok)
    monkeypatch.setattr(orchestrator, "apply_filter", _ok)
    monkeypatch.setattr(orchestrator, "extract_visits", _slow_extract)
    monkeypatch.setattr(orchestrator, "is_logged_in", _ok)
    monkeypatch.setattr(orchestrator, "extract_payment_details", _ok)

    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))
    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16))
    task = asyncio.create_task(orchestrator.run_scrape_job(job_id, req))
    orchestrator.register_task(job_id, task)
    await asyncio.sleep(0.1)
    cancelled = await orchestrator.cancel_job(job_id)
    assert cancelled is True
    with pytest.raises(asyncio.CancelledError):
        await task

    from app.db.repositories import job_repo
    sm = get_sessionmaker()
    async with sm() as session:
        job = await job_repo.get_job(session, job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELLED


async def test_orchestrator_filter_umum_only_umum_visits_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter=UMUM: only UMUM visits are persisted."""
    visits = [
        VisitData(
            emr_visit_id="V010", no_rm="RM10", nama="Umum1", tgl_lahir=date(1990, 1, 1),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="UMUM", total_biaya=Decimal("0.00"),
        ),
        VisitData(
            emr_visit_id="V011", no_rm="RM11", nama="Bpjs1", tgl_lahir=date(1985, 3, 10),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="BPJS", total_biaya=Decimal("0.00"),
        ),
        VisitData(
            emr_visit_id="V012", no_rm="RM12", nama="Umum2", tgl_lahir=None,
            ruang="POLI GIGI", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="UMUM", total_biaya=Decimal("0.00"),
        ),
    ]
    _patch_scraper_calls(monkeypatch, visits)
    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))

    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16), cara_bayar="UMUM")
    await orchestrator.run_scrape_job(job_id, req)

    from app.db.repositories import visit_repo
    sm = get_sessionmaker()
    async with sm() as session:
        all_visits = await visit_repo.list_visits(session, date(2026, 5, 16), date(2026, 5, 16))
    assert len(all_visits) == 2
    names = {v.nama for v in all_visits}
    assert names == {"Umum1", "Umum2"}


async def test_orchestrator_filter_bpjs_skips_payment_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter=BPJS: only BPJS visits persisted, payment extraction NOT called."""
    payment_called = {"n": 0}

    visits = [
        VisitData(
            emr_visit_id="V020", no_rm="RM20", nama="Umum1", tgl_lahir=date(1990, 1, 1),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="UMUM", total_biaya=Decimal("50000"),
            bayar_url="/daf/px/20/1/V020",
        ),
        VisitData(
            emr_visit_id="V021", no_rm="RM21", nama="Bpjs1", tgl_lahir=date(1985, 3, 10),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="BPJS", total_biaya=Decimal("0.00"),
        ),
    ]
    _patch_scraper_calls(monkeypatch, visits)

    async def _track_payment(page, selectors, bayar_url):
        payment_called["n"] += 1
        return [], Decimal("0.00")

    monkeypatch.setattr(orchestrator, "extract_payment_details", _track_payment)

    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))
    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16), cara_bayar="BPJS")
    await orchestrator.run_scrape_job(job_id, req)

    from app.db.repositories import visit_repo
    sm = get_sessionmaker()
    async with sm() as session:
        all_visits = await visit_repo.list_visits(session, date(2026, 5, 16), date(2026, 5, 16))
    assert len(all_visits) == 1
    assert all_visits[0].nama == "Bpjs1"
    assert payment_called["n"] == 0


async def test_orchestrator_filter_semua_umum_gets_tindakan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter=SEMUA: all visits persisted, only UMUM gets payment extraction."""
    payment_urls: list[str] = []

    visits = [
        VisitData(
            emr_visit_id="V030", no_rm="RM30", nama="Umum1", tgl_lahir=date(1990, 1, 1),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="UMUM", total_biaya=Decimal("0.00"),
            bayar_url="/daf/px/20/1/V030",
        ),
        VisitData(
            emr_visit_id="V031", no_rm="RM31", nama="Bpjs1", tgl_lahir=date(1985, 3, 10),
            ruang="POLI UMUM", tanggal_kunjungan=date(2026, 5, 16),
            cara_bayar="BPJS", total_biaya=Decimal("0.00"),
            bayar_url="/daf/px/20/1/V031",
        ),
    ]
    _patch_scraper_calls(monkeypatch, visits)

    async def _track_payment(page, selectors, bayar_url):
        payment_urls.append(bayar_url)
        treatments = [
            TreatmentData(nama_tindakan="Konsultasi", biaya=Decimal("50000")),
        ]
        return treatments, Decimal("50000")

    monkeypatch.setattr(orchestrator, "extract_payment_details", _track_payment)

    job_id = await _create_job(date(2026, 5, 16), date(2026, 5, 16))
    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 16), cara_bayar="SEMUA")
    await orchestrator.run_scrape_job(job_id, req)

    from app.db.repositories import visit_repo
    sm = get_sessionmaker()
    async with sm() as session:
        all_visits = await visit_repo.list_visits(session, date(2026, 5, 16), date(2026, 5, 16))
    # All visits persisted
    assert len(all_visits) == 2
    # Only UMUM visit had payment extraction called
    assert len(payment_urls) == 1
    assert "/V030" in payment_urls[0]
    # UMUM visit has treatments
    umum_visit = next(v for v in all_visits if v.cara_bayar == "UMUM")
    assert len(umum_visit.treatments) == 1
    assert umum_visit.treatments[0].nama_tindakan == "Konsultasi"
    assert umum_visit.total_biaya == Decimal("50000")
