"""Repository for DailyRecap upsert and queries."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import DailyRecap, PatientVisit, Treatment


async def upsert_recap(
    session: AsyncSession,
    tanggal_kunjungan: date,
    job_id: int | None = None,
) -> DailyRecap:
    """Recompute totals from current visits/treatments and upsert recap row."""
    biaya_stmt = (
        select(func.coalesce(func.sum(Treatment.biaya), 0))
        .join(PatientVisit, Treatment.visit_id == PatientVisit.id)
        .where(PatientVisit.tanggal_kunjungan == tanggal_kunjungan)
    )
    total_biaya: Decimal = (await session.execute(biaya_stmt)).scalar_one()

    pasien_stmt = select(func.count(PatientVisit.id)).where(
        PatientVisit.tanggal_kunjungan == tanggal_kunjungan
    )
    total_pasien: int = (await session.execute(pasien_stmt)).scalar_one()

    tindakan_stmt = (
        select(func.count(Treatment.id))
        .join(PatientVisit, Treatment.visit_id == PatientVisit.id)
        .where(PatientVisit.tanggal_kunjungan == tanggal_kunjungan)
    )
    total_tindakan: int = (await session.execute(tindakan_stmt)).scalar_one()

    existing_stmt = select(DailyRecap).where(
        DailyRecap.tanggal_kunjungan == tanggal_kunjungan
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()

    now = datetime.utcnow()
    if existing is None:
        recap = DailyRecap(
            tanggal_kunjungan=tanggal_kunjungan,
            total_biaya=Decimal(str(total_biaya)),
            total_pasien=int(total_pasien),
            total_tindakan=int(total_tindakan),
            last_scraped_at=now,
            last_job_id=job_id,
        )
        session.add(recap)
    else:
        existing.total_biaya = Decimal(str(total_biaya))
        existing.total_pasien = int(total_pasien)
        existing.total_tindakan = int(total_tindakan)
        existing.last_scraped_at = now
        existing.last_job_id = job_id
        recap = existing

    await session.commit()
    await session.refresh(recap)
    return recap


async def list_recaps(session: AsyncSession, limit: int = 50) -> list[DailyRecap]:
    stmt = select(DailyRecap).order_by(DailyRecap.tanggal_kunjungan.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_recap_by_date(session: AsyncSession, tanggal: date) -> DailyRecap | None:
    return (
        await session.execute(
            select(DailyRecap).where(DailyRecap.tanggal_kunjungan == tanggal)
        )
    ).scalar_one_or_none()
