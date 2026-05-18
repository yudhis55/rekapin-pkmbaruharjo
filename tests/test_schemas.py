"""Tests for Pydantic DTOs."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.dto import (
    ProgressEvent,
    ScrapeRequest,
    TreatmentOut,
    VisitOut,
)


def test_scrape_request_single_mode_defaults_tanggal_to() -> None:
    req = ScrapeRequest(mode="single", tanggal_from=date(2026, 5, 15))
    assert req.tanggal_to == date(2026, 5, 15)


def test_scrape_request_range_validates_order() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ScrapeRequest(
            mode="range",
            tanggal_from=date(2026, 5, 20),
            tanggal_to=date(2026, 5, 15),
        )
    assert "tanggal_to" in str(exc_info.value)


def test_scrape_request_range_max_31_days() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ScrapeRequest(
            mode="range",
            tanggal_from=date(2026, 1, 1),
            tanggal_to=date(2026, 3, 15),
        )
    assert "31" in str(exc_info.value)


def test_scrape_request_range_within_limit_ok() -> None:
    req = ScrapeRequest(
        mode="range",
        tanggal_from=date(2026, 5, 1),
        tanggal_to=date(2026, 5, 31),
    )
    assert req.tanggal_from == date(2026, 5, 1)
    assert req.tanggal_to == date(2026, 5, 31)


def test_visit_out_serializes_decimal_as_string_or_number() -> None:
    visit = VisitOut(
        id=1,
        no_rm="RM001",
        nama="Sample",
        tgl_lahir=date(1990, 1, 1),
        ruang="Poli Umum",
        tanggal_kunjungan=date(2026, 5, 15),
        total_biaya=Decimal("100000.00"),
        treatments=[TreatmentOut(nama_tindakan="X", biaya=Decimal("50000.00"))],
    )
    dumped = visit.model_dump_json()
    assert "100000" in dumped


def test_progress_event_validates_event_type() -> None:
    ev = ProgressEvent(event_type="progress", message="x", current=1, total=10)
    assert ev.event_type == "progress"
    with pytest.raises(ValidationError):
        ProgressEvent(event_type="bogus")  # type: ignore[arg-type]
