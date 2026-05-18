"""DailyRecap model: aggregated totals per visit-date."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.job import ScrapeJob


class DailyRecap(Base, TimestampMixin):
    __tablename__ = "daily_recaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tanggal_kunjungan: Mapped[date] = mapped_column(
        Date, unique=True, nullable=False, index=True,
    )
    total_biaya: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False,
    )
    total_pasien: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tindakan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="SET NULL"), nullable=True,
    )

    last_job: Mapped["ScrapeJob | None"] = relationship("ScrapeJob", back_populates="recaps")
