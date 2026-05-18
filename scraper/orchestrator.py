"""Scrape job orchestrator: state machine + flow.

Flow per date:
  1. Publish "login" event
  2. Open Playwright browser context
  3. Login
  4. Navigate to PENDAFTARAN INDUK
  5. Apply filter (date + ruang)
  6. Extract visits
  7. Persist visits to DB
  8. Upsert recap for that date
  9. Close browser

For range mode: loop dates, restart browser context per date for isolation.

Error handling:
  - SessionExpiredError -> retry once with fresh login
  - LoginError, NavigationError, etc -> mark job error, persist message
  - asyncio.CancelledError -> mark cancelled, keep partial results
  - Any other Exception -> mark error
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from app.db.repositories import job_repo, recap_repo, visit_repo
from app.db.session import get_sessionmaker
from app.progress.event_bus import event_bus
from app.schemas.dto import ProgressEvent, ScrapeRequest
from config.selectors import load_selectors
from config.settings import get_settings
from models import JobStatus
from scraper.browser import playwright_browser
from scraper.exceptions import (
    JobAlreadyRunningError,
    LoginError,
    NavigationError,
    ScraperError,
    SessionExpiredError,
)
from scraper.extract import extract_visits
from scraper.filter import apply_filter
from scraper.login import login as scraper_login
from scraper.navigation import go_to_pendaftaran_induk
from scraper.types import VisitData

logger = logging.getLogger(__name__)


# Module-level registry of running asyncio tasks (one per job)
_running_tasks: dict[int, asyncio.Task[None]] = {}


def _date_iter(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


async def _publish(job_id: int, event_type: str, message: str = "", **kwargs) -> None:
    ev = ProgressEvent(event_type=event_type, message=message, **kwargs)
    await event_bus.publish(job_id, ev)


async def _persist_visits(
    visits: list[VisitData],
    job_id: int,
    tanggal: date,
) -> int:
    """Upsert visits + recompute recap. Returns count of visits persisted."""
    sm = get_sessionmaker()
    async with sm() as session:
        for v in visits:
            await visit_repo.upsert_visit(
                session,
                visit_repo.VisitInput(
                    no_rm=v.no_rm,
                    nama=v.nama,
                    tgl_lahir=v.tgl_lahir,
                    ruang=v.ruang,
                    tanggal_kunjungan=v.tanggal_kunjungan,
                    total_biaya=v.total_biaya,
                ),
                [
                    visit_repo.TreatmentInput(
                        nama_tindakan=t.nama_tindakan, biaya=t.biaya
                    )
                    for t in v.treatments
                ],
                scrape_job_id=job_id,
            )
        await job_repo.increment_visit_count(session, job_id, by=len(visits))
        await recap_repo.upsert_recap(session, tanggal, job_id=job_id)
    return len(visits)


async def _scrape_one_date(
    job_id: int,
    tanggal: date,
    ruang: str | None,
    *,
    retry_on_session_expired: bool = True,
) -> int:
    """Scrape a single date. Returns visits count."""
    settings = get_settings()
    selectors = load_selectors()

    async with playwright_browser() as (browser, ctx, page):
        await _publish(job_id, "log", message=f"login untuk tanggal {tanggal}")
        try:
            await scraper_login(page, selectors, settings)
        except LoginError:
            raise

        await _publish(job_id, "log", message="navigasi ke pendaftaran induk")
        await go_to_pendaftaran_induk(page, selectors)

        await _publish(
            job_id, "log",
            message=f"terapkan filter tanggal={tanggal} ruang={ruang or 'SEMUA'}",
        )
        await apply_filter(page, selectors, tanggal, ruang)

        async def progress_cb(current: int, total: int, label: str) -> None:
            await _publish(
                job_id, "progress",
                message=label, current=current, total=total,
            )

        try:
            visits = await extract_visits(
                page, selectors, fallback_date=tanggal, on_progress=progress_cb,
            )
        except SessionExpiredError:
            if not retry_on_session_expired:
                raise
            logger.warning(
                "orchestrator: session expired - retrying once for date %s", tanggal
            )
            await _publish(job_id, "log", message="sesi habis - retry login")
            return await _scrape_one_date(
                job_id, tanggal, ruang, retry_on_session_expired=False,
            )

    persisted = await _persist_visits(visits, job_id, tanggal)
    await _publish(
        job_id, "log",
        message=f"tanggal {tanggal} selesai: {persisted} kunjungan disimpan",
    )
    return persisted


async def run_scrape_job(job_id: int, request: ScrapeRequest) -> None:
    """Main orchestrator. Updates job status, persists visits, publishes progress events."""
    sm = get_sessionmaker()

    # Active-job lock check
    async with sm() as session:
        active = await job_repo.get_active_job(session)
        if active is not None and active.id != job_id:
            raise JobAlreadyRunningError(f"job {active.id} already running")
        await job_repo.update_job_status(session, job_id, JobStatus.RUNNING)

    total_persisted = 0
    try:
        from_d = request.tanggal_from
        to_d = request.tanggal_to or request.tanggal_from
        for d in _date_iter(from_d, to_d):
            await _publish(job_id, "log", message=f"mulai tanggal {d}")
            total_persisted += await _scrape_one_date(job_id, d, request.ruang)

        async with sm() as session:
            await job_repo.update_job_status(session, job_id, JobStatus.DONE)
        await _publish(
            job_id, "done",
            message=f"selesai: {total_persisted} kunjungan disimpan",
            payload={"total_visits": total_persisted},
        )
    except asyncio.CancelledError:
        async with sm() as session:
            await job_repo.update_job_status(
                session, job_id, JobStatus.CANCELLED,
                error="dibatalkan oleh pengguna",
            )
        await _publish(job_id, "cancelled", message="dibatalkan")
        raise
    except (LoginError, NavigationError, SessionExpiredError, ScraperError) as exc:
        async with sm() as session:
            await job_repo.update_job_status(
                session, job_id, JobStatus.ERROR, error=str(exc),
            )
        await _publish(job_id, "error", message=str(exc))
        logger.exception("orchestrator: scraper error")
    except Exception as exc:  # noqa: BLE001 - last-resort
        async with sm() as session:
            await job_repo.update_job_status(
                session, job_id, JobStatus.ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
        await _publish(job_id, "error", message=str(exc))
        logger.exception("orchestrator: unexpected error")
    finally:
        await event_bus.close(job_id)
        _running_tasks.pop(job_id, None)


def register_task(job_id: int, task: asyncio.Task[None]) -> None:
    """Register an asyncio.Task so cancel_job can find it."""
    _running_tasks[job_id] = task


async def cancel_job(job_id: int) -> bool:
    """Request cancellation of an active job. Returns True if cancellation was requested."""
    task = _running_tasks.get(job_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True
