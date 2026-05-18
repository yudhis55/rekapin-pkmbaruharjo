"""Repository for PatientVisit + Treatment operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import PatientVisit, Treatment


@dataclass
class VisitInput:
    """Plain data for creating/updating a visit."""

    emr_visit_id: str
    no_rm: str
    nama: str
    tgl_lahir: date | None
    ruang: str
    tanggal_kunjungan: date
    cara_bayar: str = "UMUM"
    total_biaya: Decimal = Decimal("0.00")


@dataclass
class TreatmentInput:
    nama_tindakan: str
    biaya: Decimal
    kategori: str = "biasa"
    tanggal: date | None = None


async def upsert_visit(
    session: AsyncSession,
    visit_data: VisitInput,
    treatments: list[TreatmentInput],
    scrape_job_id: int | None = None,
) -> PatientVisit:
    """Insert or update a visit by emr_visit_id.

    On update: replaces all treatments (delete-orphan via cascade).
    """
    stmt = (
        select(PatientVisit)
        .where(PatientVisit.emr_visit_id == visit_data.emr_visit_id)
        .options(selectinload(PatientVisit.treatments))
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        visit = PatientVisit(
            emr_visit_id=visit_data.emr_visit_id,
            no_rm=visit_data.no_rm,
            nama=visit_data.nama,
            tgl_lahir=visit_data.tgl_lahir,
            ruang=visit_data.ruang,
            tanggal_kunjungan=visit_data.tanggal_kunjungan,
            cara_bayar=visit_data.cara_bayar,
            total_biaya=visit_data.total_biaya,
            scrape_job_id=scrape_job_id,
            treatments=[
                Treatment(
                    nama_tindakan=t.nama_tindakan,
                    biaya=t.biaya,
                    kategori=t.kategori,
                    tanggal=t.tanggal,
                )
                for t in treatments
            ],
        )
        session.add(visit)
    else:
        existing.nama = visit_data.nama
        existing.tgl_lahir = visit_data.tgl_lahir
        existing.ruang = visit_data.ruang
        existing.tanggal_kunjungan = visit_data.tanggal_kunjungan
        existing.cara_bayar = visit_data.cara_bayar
        existing.total_biaya = visit_data.total_biaya
        existing.scrape_job_id = scrape_job_id
        # Replace treatments via cascade delete-orphan
        existing.treatments.clear()
        for t in treatments:
            existing.treatments.append(
                Treatment(
                    nama_tindakan=t.nama_tindakan,
                    biaya=t.biaya,
                    kategori=t.kategori,
                    tanggal=t.tanggal,
                )
            )
        visit = existing

    await session.commit()
    await session.refresh(visit, attribute_names=["treatments"])
    return visit


async def list_visits(
    session: AsyncSession,
    tanggal_from: date,
    tanggal_to: date,
    ruang: str | None = None,
    cara_bayar: str | None = None,
) -> list[PatientVisit]:
    stmt = (
        select(PatientVisit)
        .where(
            PatientVisit.tanggal_kunjungan >= tanggal_from,
            PatientVisit.tanggal_kunjungan <= tanggal_to,
        )
        .options(selectinload(PatientVisit.treatments))
        .order_by(PatientVisit.tanggal_kunjungan.desc(), PatientVisit.id.desc())
    )
    if ruang:
        stmt = stmt.where(PatientVisit.ruang == ruang)
    if cara_bayar:
        stmt = stmt.where(PatientVisit.cara_bayar == cara_bayar)
    result = await session.execute(stmt)
    return list(result.scalars().all())
