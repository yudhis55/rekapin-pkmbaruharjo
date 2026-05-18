"""JSON API routes."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.repositories import recap_repo, visit_repo
from app.db.session import get_session
from app.progress.event_bus import event_bus
from app.schemas.dto import RecapOut, ScrapeJobOut, ScrapeRequest, VisitOut
from config.ruang import RUANG_LIST
from scraper import orchestrator

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/ruang")
async def list_ruang() -> dict[str, list[str]]:
    """Return the ruang list configured in config/ruang.py."""
    return {"ruang": RUANG_LIST}


@router.get("/visits", response_model=list[VisitOut])
async def list_visits_endpoint(
    tanggal_from: date,
    tanggal_to: Annotated[date | None, Query()] = None,
    ruang: Annotated[str | None, Query()] = None,
    cara_bayar: Annotated[str | None, Query()] = None,
    session: AsyncSession = Depends(get_session),
) -> list[VisitOut]:
    if tanggal_to is None:
        tanggal_to = tanggal_from
    if tanggal_to < tanggal_from:
        raise HTTPException(status_code=422, detail="tanggal_to harus >= tanggal_from")
    delta_days = (tanggal_to - tanggal_from).days
    if delta_days > 31:
        raise HTTPException(status_code=422, detail="Rentang tanggal max 31 hari")
    visits = await visit_repo.list_visits(session, tanggal_from, tanggal_to, ruang, cara_bayar)
    return [VisitOut.model_validate(v) for v in visits]


@router.get("/recap", response_model=list[RecapOut])
async def list_recap_endpoint(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    session: AsyncSession = Depends(get_session),
) -> list[RecapOut]:
    recaps = await recap_repo.list_recaps(session, limit=limit)
    return [RecapOut.model_validate(r) for r in recaps]


@router.get("/recap/{tanggal}", response_model=RecapOut)
async def get_recap_by_date_endpoint(
    tanggal: date,
    session: AsyncSession = Depends(get_session),
) -> RecapOut:
    recap = await recap_repo.get_recap_by_date(session, tanggal)
    if recap is None:
        raise HTTPException(status_code=404, detail=f"Tidak ada rekap untuk {tanggal}")
    return RecapOut.model_validate(recap)


@router.post("/scrape", status_code=202)
async def create_scrape_job(
    request: ScrapeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int | str]:
    """Trigger a scrape job. Returns immediately with job_id."""
    from app.db.repositories import job_repo
    active = await job_repo.get_active_job(session)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Job lain ({active.id}) sedang berjalan",
        )
    tanggal_to = request.tanggal_to or request.tanggal_from
    job = await job_repo.create_job(
        session, request.tanggal_from, tanggal_to, request.ruang,
    )
    # Schedule the orchestrator task
    task = asyncio.create_task(orchestrator.run_scrape_job(job.id, request))
    orchestrator.register_task(job.id, task)
    return {"job_id": job.id, "status": "pending"}


@router.get("/scrape/{job_id}", response_model=ScrapeJobOut)
async def get_scrape_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> ScrapeJobOut:
    from app.db.repositories import job_repo
    job = await job_repo.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan")
    return ScrapeJobOut.model_validate(job)


@router.get("/scrape/{job_id}/stream")
async def scrape_stream(job_id: int) -> EventSourceResponse:
    """Server-Sent Events stream for a scrape job's progress."""
    async def event_generator():
        async for event in event_bus.subscribe(job_id):
            yield {"event": event.event_type, "data": event.model_dump_json()}

    return EventSourceResponse(event_generator())


@router.post("/scrape/{job_id}/cancel", status_code=204)
async def cancel_scrape_job(job_id: int) -> None:
    cancelled = await orchestrator.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} tidak aktif atau sudah selesai",
        )
