"""PatientVisit model: one scraped patient encounter."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.job import ScrapeJob
    from models.treatment import Treatment


class PatientVisit(Base, TimestampMixin):
    __tablename__ = "patient_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    emr_visit_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    no_rm: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(255), nullable=False)
    tgl_lahir: Mapped[date | None] = mapped_column(Date, nullable=True)
    ruang: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    tanggal_kunjungan: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    cara_bayar: Mapped[str] = mapped_column(String(50), nullable=False, default="UMUM")
    total_biaya: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False,
    )
    scrape_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="SET NULL"), nullable=True,
    )

    job: Mapped["ScrapeJob | None"] = relationship("ScrapeJob", back_populates="visits")
    treatments: Mapped[list["Treatment"]] = relationship(
        "Treatment",
        back_populates="visit",
        cascade="all, delete-orphan",
    )
