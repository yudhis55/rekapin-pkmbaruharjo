"""Frozen dataclasses for scraped data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TreatmentData:
    """Single tindakan + biaya."""

    nama_tindakan: str
    biaya: Decimal
    kategori: str = "biasa"
    tanggal: date | None = None


@dataclass(frozen=True, slots=True)
class VisitData:
    """Single patient visit with treatments."""

    emr_visit_id: str
    no_rm: str
    nama: str
    tgl_lahir: date | None
    ruang: str
    tanggal_kunjungan: date
    cara_bayar: str
    total_biaya: Decimal
    bayar_url: str | None = None
    treatments: tuple[TreatmentData, ...] = field(default_factory=tuple)
