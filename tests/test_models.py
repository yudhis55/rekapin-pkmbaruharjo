"""Tests for SQLAlchemy models."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base, DailyRecap, JobStatus, PatientVisit, ScrapeJob, Treatment


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_sm = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sm() as s:
        yield s
    await engine.dispose()


async def test_visit_creation(session: AsyncSession) -> None:
    visit = PatientVisit(
        no_rm="RM001",
        nama="Pasien Sample",
        tgl_lahir=date(1990, 1, 1),
        ruang="Poli Umum",
        tanggal_kunjungan=date(2026, 5, 15),
        total_biaya=Decimal("100000.00"),
    )
    session.add(visit)
    await session.commit()
    assert visit.id is not None
    assert visit.created_at is not None


async def test_visit_treatment_cascade(session: AsyncSession) -> None:
    visit = PatientVisit(
        no_rm="RM002", nama="X", ruang="Lab", tanggal_kunjungan=date(2026, 5, 15),
        treatments=[
            Treatment(nama_tindakan="Cek Darah", biaya=Decimal("50000.00")),
            Treatment(nama_tindakan="Cek Gula", biaya=Decimal("30000.00")),
        ],
    )
    session.add(visit)
    await session.commit()
    visit_id = visit.id

    await session.delete(visit)
    await session.commit()

    from sqlalchemy import select
    result = await session.execute(
        select(Treatment).where(Treatment.visit_id == visit_id)
    )
    assert result.scalars().all() == []


async def test_visit_unique_constraint(session: AsyncSession) -> None:
    v1 = PatientVisit(
        no_rm="RM003", nama="A", ruang="Poli Umum", tanggal_kunjungan=date(2026, 5, 15),
    )
    session.add(v1)
    await session.commit()

    v2 = PatientVisit(
        no_rm="RM003", nama="A again", ruang="Poli Umum", tanggal_kunjungan=date(2026, 5, 15),
    )
    session.add(v2)
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_recap_unique_per_date(session: AsyncSession) -> None:
    r1 = DailyRecap(
        tanggal_kunjungan=date(2026, 5, 15),
        total_biaya=Decimal("0.00"),
        last_scraped_at=datetime(2026, 5, 15, 10, 0, 0),
    )
    session.add(r1)
    await session.commit()

    r2 = DailyRecap(
        tanggal_kunjungan=date(2026, 5, 15),
        total_biaya=Decimal("0.00"),
        last_scraped_at=datetime(2026, 5, 15, 11, 0, 0),
    )
    session.add(r2)
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_job_status_enum(session: AsyncSession) -> None:
    job = ScrapeJob(
        status=JobStatus.PENDING,
        tanggal_from=date(2026, 5, 15),
        tanggal_to=date(2026, 5, 15),
    )
    session.add(job)
    await session.commit()
    assert job.status == JobStatus.PENDING
    job.status = JobStatus.RUNNING
    await session.commit()
    assert job.status == JobStatus.RUNNING
