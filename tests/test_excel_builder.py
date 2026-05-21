"""Unit tests for Excel workbook builder (app/excel/builder.py).

Pure unit tests using stub objects (no DB, no async). The builder accesses
attributes on PatientVisit/Treatment objects, so SimpleNamespace works fine.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.excel.builder import build_rekap_workbook


def _make_treatment(nama_tindakan: str, biaya: Decimal, kategori: str) -> SimpleNamespace:
    return SimpleNamespace(
        nama_tindakan=nama_tindakan,
        biaya=biaya,
        kategori=kategori,
    )


def _make_visit(
    no_rm: str,
    nama: str,
    ruang: str,
    treatments: list[SimpleNamespace] | None = None,
    tanggal: date | None = None,
    tgl_lahir: date | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        no_rm=no_rm,
        nama=nama,
        tgl_lahir=tgl_lahir or date(1990, 1, 1),
        ruang=ruang,
        tanggal_kunjungan=tanggal or date(2026, 5, 15),
        cara_bayar="UMUM",
        total_biaya=Decimal("0.00"),
        treatments=treatments or [],
    )


def _row_values(ws, row: int) -> list[object]:
    """Get all cell values in a given row."""
    return [ws.cell(row=row, column=c).value for c in range(1, ws.max_column + 1)]


def test_build_workbook_with_3_patients() -> None:
    """3 patients across POLI UMUM and POLI GIGI, with 1 lab + 1 biasa tindakan."""
    visits = [
        _make_visit(
            no_rm="RM001",
            nama="Patient A",
            ruang="POLI UMUM",
            treatments=[
                _make_treatment("Hematologi", Decimal("25000"), "lab"),
            ],
        ),
        _make_visit(
            no_rm="RM002",
            nama="Patient B",
            ruang="POLI GIGI",
            treatments=[
                _make_treatment("Cabut Gigi", Decimal("50000"), "biasa"),
            ],
        ),
        _make_visit(
            no_rm="RM003",
            nama="Patient C",
            ruang="POLI UMUM",
        ),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    # 2 header + 3 data + 1 jumlah
    assert ws.max_row >= 5

    # Row 1 fixed headers
    assert ws.cell(row=1, column=1).value == "No"
    assert ws.cell(row=1, column=2).value == "Tanggal"
    assert ws.cell(row=1, column=3).value == "Nama"
    assert ws.cell(row=1, column=4).value == "No RM"

    # Row 1 group headers should include Ruangan, Laboratorium, Tindakan, Jumlah, Kwitansi
    row1 = _row_values(ws, 1)
    assert "Ruangan" in row1
    assert "Laboratorium" in row1
    assert "Tindakan" in row1
    assert "Jumlah" in row1
    assert "Kwitansi" in row1

    # Data rows start at row 3
    assert ws.cell(row=3, column=1).value == 1
    assert ws.cell(row=4, column=1).value == 2
    assert ws.cell(row=5, column=1).value == 3


def test_ruang_grouping_kia_kb_mtbs() -> None:
    """POLI KIA, POLI KB, POLI MTBS should collapse into one 'KIA/KB/MTBS' column."""
    visits = [
        _make_visit(no_rm="RM001", nama="A", ruang="POLI KIA"),
        _make_visit(no_rm="RM002", nama="B", ruang="POLI KB"),
        _make_visit(no_rm="RM003", nama="C", ruang="POLI MTBS"),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    # Row 2 sub-headers
    row2 = _row_values(ws, 2)
    assert row2.count("KIA/KB/MTBS") == 1
    # No raw POLI KIA/KB/MTBS labels
    assert "Kia" not in row2
    assert "Kb" not in row2
    assert "Mtbs" not in row2


def test_dynamic_lab_columns() -> None:
    """2 distinct lab tindakan should produce 2 lab columns in row 2."""
    visits = [
        _make_visit(
            no_rm="RM001",
            nama="A",
            ruang="POLI UMUM",
            treatments=[
                _make_treatment("Hematologi", Decimal("25000"), "lab"),
                _make_treatment("Urine", Decimal("15000"), "lab"),
            ],
        ),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    row2 = _row_values(ws, 2)
    assert "Hematologi" in row2
    assert "Urine" in row2


def test_dynamic_tindakan_columns() -> None:
    """2 distinct biasa tindakan should produce 2 tindakan columns in row 2."""
    visits = [
        _make_visit(
            no_rm="RM001",
            nama="A",
            ruang="POLI UMUM",
            treatments=[
                _make_treatment("Cabut Gigi", Decimal("50000"), "biasa"),
                _make_treatment("Tambal Gigi", Decimal("75000"), "biasa"),
            ],
        ),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    row2 = _row_values(ws, 2)
    assert "Cabut Gigi" in row2
    assert "Tambal Gigi" in row2


def test_formula_in_jumlah_column() -> None:
    """Jumlah cell on data rows should contain a SUM formula."""
    visits = [
        _make_visit(
            no_rm="RM001",
            nama="A",
            ruang="POLI UMUM",
            treatments=[_make_treatment("Hematologi", Decimal("25000"), "lab")],
        ),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    # Find Jumlah column (the one labeled "Jumlah" in row 1)
    jumlah_col = None
    for c in range(1, ws.max_column + 1):
        if ws.cell(row=1, column=c).value == "Jumlah":
            jumlah_col = c
            break
    assert jumlah_col is not None

    # Row 3 is the first data row
    formula = ws.cell(row=3, column=jumlah_col).value
    assert isinstance(formula, str)
    assert formula.startswith("=SUM(")


def test_formula_in_jumlah_row() -> None:
    """Last (JUMLAH) row: col B = 'JUMLAH', biaya columns have =SUM( formulas."""
    visits = [
        _make_visit(
            no_rm="RM001",
            nama="A",
            ruang="POLI UMUM",
            treatments=[_make_treatment("Hematologi", Decimal("25000"), "lab")],
        ),
        _make_visit(
            no_rm="RM002",
            nama="B",
            ruang="POLI GIGI",
            treatments=[_make_treatment("Cabut Gigi", Decimal("50000"), "biasa")],
        ),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    jumlah_row = ws.max_row
    assert ws.cell(row=jumlah_row, column=2).value == "JUMLAH"

    # Find Jumlah column
    jumlah_col = None
    for c in range(1, ws.max_column + 1):
        if ws.cell(row=1, column=c).value == "Jumlah":
            jumlah_col = c
            break
    assert jumlah_col is not None

    # Biaya columns start at col 5 (E) up to and including jumlah_col
    found_formula = False
    for c in range(5, jumlah_col + 1):
        val = ws.cell(row=jumlah_row, column=c).value
        if isinstance(val, str) and val.startswith("=SUM("):
            found_formula = True
    assert found_formula


def test_kwitansi_column_empty() -> None:
    """Kwitansi column (last col) should be empty/None on every data row."""
    visits = [
        _make_visit(
            no_rm="RM001",
            nama="A",
            ruang="POLI UMUM",
            treatments=[_make_treatment("Hematologi", Decimal("25000"), "lab")],
        ),
        _make_visit(
            no_rm="RM002",
            nama="B",
            ruang="POLI GIGI",
            treatments=[_make_treatment("Cabut Gigi", Decimal("50000"), "biasa")],
        ),
    ]

    wb = build_rekap_workbook(visits, date(2026, 5, 15), "UMUM")
    ws = wb.active

    # Find Kwitansi column
    kwitansi_col = None
    for c in range(1, ws.max_column + 1):
        if ws.cell(row=1, column=c).value == "Kwitansi":
            kwitansi_col = c
            break
    assert kwitansi_col is not None
    # Kwitansi should be the last column
    assert kwitansi_col == ws.max_column

    # Data rows are 3..(max_row - 1); JUMLAH row is max_row
    jumlah_row = ws.max_row
    for row in range(3, jumlah_row):
        assert ws.cell(row=row, column=kwitansi_col).value is None
