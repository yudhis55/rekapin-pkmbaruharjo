"""ScrapeJob model: tracks scraping execution state."""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.recap import DailyRecap
    from models.visit import PatientVisit


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class ScrapeJob(Base, TimestampMixin):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"),
        default=JobStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tanggal_from: Mapped[date] = mapped_column(Date, nullable=False)
    tanggal_to: Mapped[date] = mapped_column(Date, nullable=False)
    ruang_filter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_visits_scraped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    visits: Mapped[list["PatientVisit"]] = relationship(
        "PatientVisit", back_populates="job",
    )
    recaps: Mapped[list["DailyRecap"]] = relationship(
        "DailyRecap", back_populates="last_job",
    )
