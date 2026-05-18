"""Extract patient visit data from EMR pendaftaran induk page.

The patient list page has each patient as a <tr> with a nested visit table
in the last <td>. We extract identity + visit info inline. Tindakan/biaya
extraction from detail pages is deferred to v2 (stub returns empty tuple).

# v2: detail page extraction
# To get tindakan + biaya, for each visit:
#   1. Extract visit_id from form action (e.g., /rp/res/{visit_id}/0/0)
#   2. POST to that URL with CSRF token from per-row form
#   3. Parse tindakan table on result page
#   4. Navigate back to patient list
# This is significant complexity deferred to a future task.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.selectors import Selectors
from scraper.exceptions import SelectorNotFoundError, SessionExpiredError
from scraper.navigation import is_logged_in
from scraper.types import VisitData

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], Awaitable[None]]


_DATE_PATTERN = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")


def _parse_dmy_date(text: str | None) -> date | None:
    """Parse DD/MM/YYYY or DD-MM-YYYY from text. Returns None if no match."""
    if not text:
        return None
    m = _DATE_PATTERN.search(text)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _redact_rm(no_rm: str) -> str:
    """Return safe-to-log version of an RM number (first 2 chars + asterisks)."""
    if len(no_rm) <= 2:
        return "**"
    return no_rm[:2] + "*" * (len(no_rm) - 2)


async def _extract_visits_from_row(
    row: Locator, fallback_date: date
) -> list[VisitData]:
    """Extract one or more VisitData from a single patient <tr>.

    A row can have multiple visits in its nested kunjungan table -
    one VisitData per visit.
    """
    cells = row.locator(":scope > td")
    cell_count = await cells.count()
    if cell_count < 8:
        # Header rows or malformed rows - skip
        return []

    # Column structure (0-indexed):
    # 0=No, 1=No.RM (+buttons), 2=Nama (+Gabung), 3=Tgl Lahir,
    # 4=Alamat, 5=L/P, 6=Asuransi, 7=Edit, 8=Daftar, 9=Kunjungan nested table
    no_rm_raw = (await cells.nth(1).inner_text()).strip()
    nama_raw = (await cells.nth(2).inner_text()).strip()
    tgl_lahir_raw = (await cells.nth(3).inner_text()).strip()

    # No.RM cell contains RM number + buttons (Resume, CPPT) - take first line
    no_rm = no_rm_raw.split("\n", 1)[0].strip()
    # Nama cell contains name + "Gabung" button text - take first line
    nama = nama_raw.split("\n", 1)[0].strip()
    # Tgl lahir cell: "01/01/1990\n19\n\nP01793794225" - parse date from it
    tgl_lahir = _parse_dmy_date(tgl_lahir_raw)

    if not no_rm or not nama:
        return []

    # Last cell has the nested kunjungan table (border="1")
    last_cell = cells.nth(cell_count - 1)
    nested_table = last_cell.locator("table")
    nested_count = await nested_table.count()
    if nested_count == 0:
        return []

    # Visit rows are <tr style="background-color:transparent"> in the
    # outer nested table. Each has: td(Ruangan), td(Cara Bayar),
    # td(Tgl.Masuk), td(Batal)
    visit_rows = nested_table.first.locator(":scope > tbody > tr")
    n = await visit_rows.count()

    visits: list[VisitData] = []
    for i in range(n):
        vrow = visit_rows.nth(i)
        vcells = vrow.locator(":scope > td")
        vc_count = await vcells.count()
        if vc_count < 3:
            continue

        # Ruangan is in first td (may contain nested table with "Pindah" button)
        ruang_raw = (await vcells.nth(0).inner_text()).strip()
        # Take first meaningful line (before button text like "Pindah")
        ruang_lines = [
            ln.strip()
            for ln in ruang_raw.splitlines()
            if ln.strip() and ln.strip().lower() != "pindah"
        ]
        ruang = ruang_lines[0] if ruang_lines else ""

        # Tgl.Masuk is in third td (index 2): "01/01/1990 16:09"
        tgl_masuk_raw = (await vcells.nth(2).inner_text()).strip()
        tgl_kunjungan = _parse_dmy_date(tgl_masuk_raw) or fallback_date

        if not ruang:
            continue

        visits.append(
            VisitData(
                no_rm=no_rm,
                nama=nama,
                tgl_lahir=tgl_lahir,
                ruang=ruang,
                tanggal_kunjungan=tgl_kunjungan,
                total_biaya=Decimal("0.00"),
                treatments=tuple(),  # v2: populate from detail page
            )
        )
    return visits


async def extract_visits(
    page: Page,
    selectors: Selectors,
    fallback_date: date | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[VisitData]:
    """Extract all patient visits from the current daftar page.

    Args:
        page: Page on /daf/px/1/... after filter applied.
        selectors: Loaded selectors.
        fallback_date: Used when a visit row's tgl masuk is unparseable.
            Defaults to today.
        on_progress: Optional async callback (current, total, label).

    Returns:
        Flat list of VisitData (one per visit, NOT one per patient).
        A patient with multiple visits produces multiple VisitData rows.
    """
    fallback_date = fallback_date or date.today()

    # Pre-extraction session check
    if not await is_logged_in(page, selectors):
        raise SessionExpiredError("session expired before extraction")

    table_sel = selectors.daftar.patient_table
    try:
        await page.wait_for_selector(table_sel, timeout=10_000)
    except PlaywrightTimeoutError as exc:
        raise SelectorNotFoundError(
            f"patient table not found: {table_sel}"
        ) from exc

    rows = page.locator(f"{table_sel} > tbody > tr")
    total = await rows.count()
    logger.info("extract: found %d rows in patient table", total)

    if on_progress is not None:
        await on_progress(0, total, "starting extraction")

    all_visits: list[VisitData] = []
    for i in range(total):
        row = rows.nth(i)
        try:
            row_visits = await _extract_visits_from_row(row, fallback_date)
        except Exception as exc:  # noqa: BLE001
            logger.warning("extract: row %d failed: %s", i, exc)
            row_visits = []

        all_visits.extend(row_visits)
        if on_progress is not None:
            label = (
                f"row {i + 1}/{total}"
                if not row_visits
                else f"patient {_redact_rm(row_visits[0].no_rm)}"
                f" ({len(row_visits)} visits)"
            )
            await on_progress(i + 1, total, label)

    logger.info(
        "extract: produced %d visit records from %d rows",
        len(all_visits),
        total,
    )
    return all_visits
