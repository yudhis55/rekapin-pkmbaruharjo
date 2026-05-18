"""Repository for ScrapeJob operations."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import JobStatus, ScrapeJob


async def create_job(
    session: AsyncSession,
    tanggal_from: date,
    tanggal_to: date,
    ruang_filter: str | None,
) -> ScrapeJob:
    job = ScrapeJob(
        status=JobStatus.PENDING,
        tanggal_from=tanggal_from,
        tanggal_to=tanggal_to,
        ruang_filter=ruang_filter,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def update_job_status(
    session: AsyncSession,
    job_id: int,
    status: JobStatus,
    error: str | None = None,
) -> None:
    values: dict[str, object] = {"status": status}
    if status == JobStatus.RUNNING:
        values["started_at"] = datetime.utcnow()
    if status in (JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELLED):
        values["finished_at"] = datetime.utcnow()
    if error is not None:
        values["error_message"] = error
    await session.execute(
        update(ScrapeJob).where(ScrapeJob.id == job_id).values(**values)
    )
    await session.commit()


async def get_active_job(session: AsyncSession) -> ScrapeJob | None:
    stmt = select(ScrapeJob).where(
        ScrapeJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def increment_visit_count(session: AsyncSession, job_id: int, by: int = 1) -> None:
    await session.execute(
        update(ScrapeJob)
        .where(ScrapeJob.id == job_id)
        .values(total_visits_scraped=ScrapeJob.total_visits_scraped + by)
    )
    await session.commit()


async def get_job(session: AsyncSession, job_id: int) -> ScrapeJob | None:
    return (
        await session.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    ).scalar_one_or_none()
