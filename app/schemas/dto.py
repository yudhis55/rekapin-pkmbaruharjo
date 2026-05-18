"""Pydantic DTOs for API request/response contracts."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DateMode = Literal["single", "range"]
EventType = Literal["log", "progress", "row", "done", "error", "cancelled"]


CaraBayarFilter = Literal["UMUM", "BPJS", "SEMUA"]


class ScrapeRequest(BaseModel):
    """Request to start a scrape job."""

    mode: DateMode
    tanggal_from: date
    tanggal_to: date | None = None
    ruang: str | None = None  # None means all ruang
    cara_bayar: CaraBayarFilter = "UMUM"

    @model_validator(mode="after")
    def validate_dates(self) -> "ScrapeRequest":
        if self.mode == "single":
            if self.tanggal_to is None:
                self.tanggal_to = self.tanggal_from
            elif self.tanggal_to != self.tanggal_from:
                raise ValueError("In single mode, tanggal_to must equal tanggal_from or be omitted")
        else:  # range
            if self.tanggal_to is None:
                raise ValueError("In range mode, tanggal_to is required")
            if self.tanggal_to < self.tanggal_from:
                raise ValueError("tanggal_to must be >= tanggal_from")
            delta = (self.tanggal_to - self.tanggal_from).days
            if delta > 31:
                raise ValueError(f"Date range exceeds 31 days (got {delta + 1} days)")
        return self


class TreatmentOut(BaseModel):
    """Treatment serialization."""

    model_config = ConfigDict(from_attributes=True)

    nama_tindakan: str
    biaya: Decimal
    kategori: str = "biasa"
    tanggal: date | None = None


class VisitOut(BaseModel):
    """Patient visit serialization with treatments."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    no_rm: str
    nama: str
    tgl_lahir: date | None
    ruang: str
    tanggal_kunjungan: date
    total_biaya: Decimal
    cara_bayar: str = "UMUM"
    emr_visit_id: str = ""
    treatments: list[TreatmentOut] = Field(default_factory=list)


class RecapOut(BaseModel):
    """Daily recap serialization."""

    model_config = ConfigDict(from_attributes=True)

    tanggal_kunjungan: date
    total_biaya: Decimal
    total_pasien: int
    total_tindakan: int
    last_scraped_at: datetime


class ScrapeJobOut(BaseModel):
    """Scrape job status serialization."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    tanggal_from: date
    tanggal_to: date
    ruang_filter: str | None
    total_visits_scraped: int
    error_message: str | None


class ProgressEvent(BaseModel):
    """SSE progress event payload."""

    event_type: EventType
    message: str = ""
    current: int | None = None
    total: int | None = None
    payload: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        valid = {"log", "progress", "row", "done", "error", "cancelled"}
        if v not in valid:
            raise ValueError(f"Invalid event_type: {v}")
        return v
