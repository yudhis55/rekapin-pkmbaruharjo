"""TDD tests for repository layer."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base, JobStatus
from app.db.repositories.visit_repo import TreatmentInput, VisitInput, upsert_visit, list_visits
from app.db.repositories.job_repo import create_job, get_active_job, update_job_status, get_job
from app.db.repositories.recap_repo import upsert_recap, get_recap_by_date


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_sm = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sm() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _visit_input(
    no_rm: str = "RM001",
    nama: str = "Pasien A",
    ruang: str = "Poli Umum",
    tanggal: date = date(2026, 5, 15),
    biaya: Decimal = Decimal("100000.00"),
    emr_visit_id: str | None = None,
) -> VisitInput:
    import hashlib
    _emr_id = emr_visit_id or hashlib.md5(f"{no_rm}_{ruang}_{tanggal}".encode()).hexdigest()[:12]
    return VisitInput(
        emr_visit_id=_emr_id,
        no_rm=no_rm,
        nama=nama,
        tgl_lahir=date(1990, 1, 1),
        ruang=ruang,
        tanggal_kunjungan=tanggal,
        total_biaya=biaya,
        cara_bayar="UMUM",
    )


def _treatments(names_biaya: list[tuple[str, str]]) -> list[TreatmentInput]:
    return [TreatmentInput(nama_tindakan=n, biaya=Decimal(b)) for n, b in names_biaya]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_add_visit_with_treatments_persists(session: AsyncSession) -> None:
    """Inserting a new visit with treatments stores all rows."""
    visit = await upsert_visit(
        session,
        _visit_input(),
        _treatments([("Cek Darah", "50000.00"), ("Cek Gula", "30000.00")]),
    )

    assert visit.id is not None
    assert visit.no_rm == "RM001"
    assert len(visit.treatments) == 2
    names = {t.nama_tindakan for t in visit.treatments}
    assert names == {"Cek Darah", "Cek Gula"}


async def test_upsert_visit_replaces_treatments(session: AsyncSession) -> None:
    """Second upsert on same (no_rm, tanggal, ruang) replaces treatments."""
    await upsert_visit(
        session,
        _visit_input(),
        _treatments([("Cek Darah", "50000.00"), ("Cek Gula", "30000.00")]),
    )

    updated = await upsert_visit(
        session,
        _visit_input(nama="Pasien A Updated", biaya=Decimal("75000.00")),
        _treatments([("Rontgen", "75000.00")]),
    )

    assert updated.nama == "Pasien A Updated"
    assert updated.total_biaya == Decimal("75000.00")
    assert len(updated.treatments) == 1
    assert updated.treatments[0].nama_tindakan == "Rontgen"


async def test_recap_upsert_inserts_then_updates_on_same_date(session: AsyncSession) -> None:
    """upsert_recap inserts on first call, updates on second call for same date."""
    tanggal = date(2026, 5, 15)

    # Seed a visit so totals are non-zero
    await upsert_visit(
        session,
        _visit_input(tanggal=tanggal),
        _treatments([("Cek Darah", "50000.00")]),
    )

    recap1 = await upsert_recap(session, tanggal)
    assert recap1.id is not None
    assert recap1.total_pasien == 1
    assert recap1.total_tindakan == 1
    assert recap1.total_biaya == Decimal("50000.00")

    # Add another visit on same date
    await upsert_visit(
        session,
        _visit_input(no_rm="RM002", nama="Pasien B", tanggal=tanggal),
        _treatments([("Cek Urine", "20000.00")]),
    )

    recap2 = await upsert_recap(session, tanggal)
    assert recap2.id == recap1.id  # same row updated
    assert recap2.total_pasien == 2
    assert recap2.total_tindakan == 2
    assert recap2.total_biaya == Decimal("70000.00")


async def test_get_active_job_returns_running_only(session: AsyncSession) -> None:
    """get_active_job returns PENDING/RUNNING jobs, not DONE/ERROR."""
    job_done = await create_job(session, date(2026, 5, 1), date(2026, 5, 10), None)
    await update_job_status(session, job_done.id, JobStatus.DONE)

    job_error = await create_job(session, date(2026, 5, 1), date(2026, 5, 10), None)
    await update_job_status(session, job_error.id, JobStatus.ERROR)

    # No active job yet
    assert await get_active_job(session) is None

    # Create a running job
    job_running = await create_job(session, date(2026, 5, 11), date(2026, 5, 15), "Poli Umum")
    await update_job_status(session, job_running.id, JobStatus.RUNNING)

    active = await get_active_job(session)
    assert active is not None
    assert active.id == job_running.id
    assert active.status == JobStatus.RUNNING

    # Verify finished_at was set on done/error jobs
    done = await get_job(session, job_done.id)
    assert done is not None
    assert done.finished_at is not None

    err = await get_job(session, job_error.id)
    assert err is not None
    assert err.error_message is None  # no error message passed


async def test_list_visits_filters_by_date_and_ruang(session: AsyncSession) -> None:
    """list_visits respects tanggal range and optional ruang filter."""
    await upsert_visit(
        session,
        _visit_input(no_rm="RM001", ruang="Poli Umum", tanggal=date(2026, 5, 10)),
        _treatments([("A", "10000.00")]),
    )
    await upsert_visit(
        session,
        _visit_input(no_rm="RM002", ruang="Lab", tanggal=date(2026, 5, 12)),
        _treatments([("B", "20000.00")]),
    )
    await upsert_visit(
        session,
        _visit_input(no_rm="RM003", ruang="Poli Umum", tanggal=date(2026, 5, 20)),
        _treatments([("C", "30000.00")]),
    )

    # Date range covers first two only
    all_in_range = await list_visits(session, date(2026, 5, 9), date(2026, 5, 15))
    assert len(all_in_range) == 2

    # Filter by ruang within range
    poli_only = await list_visits(session, date(2026, 5, 9), date(2026, 5, 15), ruang="Poli Umum")
    assert len(poli_only) == 1
    assert poli_only[0].no_rm == "RM001"

    # Full range, all three
    all_visits = await list_visits(session, date(2026, 5, 1), date(2026, 5, 31))
    assert len(all_visits) == 3
