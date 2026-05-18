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


@dataclass(frozen=True, slots=True)
class VisitData:
    """Single patient visit with treatments."""

    no_rm: str
    nama: str
    tgl_lahir: date | None
    ruang: str
    tanggal_kunjungan: date
    total_biaya: Decimal
    treatments: tuple[TreatmentData, ...] = field(default_factory=tuple)
