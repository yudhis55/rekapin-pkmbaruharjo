"""Extract patient visit data from EMR pendaftaran induk page.

The patient list page has each patient as a <tr> with a nested visit table
in the last <td>. We extract identity + visit info inline. Tindakan/biaya
extraction from detail pages is deferred to v2 (stub returns empty tuple).

Pagination: The patient list may span multiple pages. We detect the page
indicator (e.g. "1/3") and submit the next-page form to iterate all pages.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

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


def _extract_visit_id_from_url(url: str) -> str:
    """Extract visit ID from Bayar form action URL.

    URL pattern: /daf/px/20/1/0/{visit_id}
    Returns the last path segment.
    """
    return url.rstrip("/").rsplit("/", 1)[-1]


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

        # Cara Bayar is in second td (index 1): text + Bayar form
        cara_bayar_raw = (await vcells.nth(1).inner_text()).strip()
        # Normalize: take first line (may have button text), uppercase
        cara_bayar_line = cara_bayar_raw.split("\n")[0].strip().upper()
        # Clean up: ignore header text or empty
        if not cara_bayar_line or cara_bayar_line in ("CARA BAYAR", "BAYAR"):
            cara_bayar = "UMUM"
        else:
            cara_bayar = cara_bayar_line

        # Extract emr_visit_id and bayar_url from Bayar form action
        bayar_form = vcells.nth(1).locator("form[action*='/daf/px/20/1/']")
        bayar_url: str | None = None
        emr_visit_id = ""
        if await bayar_form.count() > 0:
            action = await bayar_form.first.get_attribute("action")
            if action:
                bayar_url = action
                # Extract visit_id from URL: /daf/px/20/1/0/{visit_id}
                parts = action.rstrip("/").split("/")
                emr_visit_id = parts[-1] if parts else ""

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
                cara_bayar=cara_bayar,
                emr_visit_id=emr_visit_id,
                bayar_url=bayar_url,
                total_biaya=Decimal("0.00"),
                treatments=tuple(),
            )
        )
    return visits


async def extract_visits(
    page: Page,
    selectors: Selectors,
    fallback_date: date | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[VisitData]:
    """Extract ALL patient visits from ALL pages of the daftar page.

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

    all_visits: list[VisitData] = []
    current_page = 1
    total_pages = 1  # will be updated after first page

    while True:
        # Wait for table on current page
        table_sel = selectors.daftar.patient_table
        try:
            await page.wait_for_selector(table_sel, timeout=10_000)
        except PlaywrightTimeoutError as exc:
            raise SelectorNotFoundError(
                f"patient table not found: {table_sel}"
            ) from exc

        # Get page indicator to know total pages
        try:
            indicator_sel = selectors.daftar_v2.pagination_indicator
            indicator_el = await page.query_selector(indicator_sel)
            if indicator_el:
                indicator_text = (await indicator_el.inner_text()).strip()
                # Format: "X/Y"
                if "/" in indicator_text:
                    parts = indicator_text.split("/")
                    current_page = int(parts[0].strip())
                    total_pages = int(parts[1].strip())
        except Exception:
            pass  # pagination might not exist for small result sets

        logger.info("extract: page %d/%d", current_page, total_pages)

        # Extract rows from current page
        rows = page.locator(f"{table_sel} > tbody > tr")
        total_rows = await rows.count()

        if on_progress is not None:
            await on_progress(
                0, total_rows, f"halaman {current_page}/{total_pages}"
            )

        for i in range(total_rows):
            row = rows.nth(i)
            try:
                row_visits = await _extract_visits_from_row(row, fallback_date)
            except Exception as exc:  # noqa: BLE001
                logger.warning("extract: row %d failed: %s", i, exc)
                row_visits = []

            all_visits.extend(row_visits)

            if on_progress is not None:
                label = (
                    f"hal {current_page}/{total_pages} baris {i + 1}/{total_rows}"
                )
                await on_progress(i + 1, total_rows, label)

        # Check if there's a next page
        if current_page >= total_pages:
            break  # we're on the last page

        # Navigate to next page by submitting the next-page form
        try:
            next_form_sel = selectors.daftar_v2.pagination_next_form
            next_forms = await page.query_selector_all(next_form_sel)
            if not next_forms:
                logger.info("extract: no next page form found, stopping")
                break

            # Submit the next page form and wait for table to reappear
            prev_page = current_page
            await next_forms[0].evaluate("form => form.submit()")
            await page.wait_for_selector(table_sel, timeout=15_000)
            await page.wait_for_timeout(500)  # brief pause for stability

            # Safety: detect if page didn't actually change
            try:
                indicator_el = await page.query_selector(
                    selectors.daftar_v2.pagination_indicator
                )
                if indicator_el:
                    txt = (await indicator_el.inner_text()).strip()
                    if "/" in txt:
                        new_page = int(txt.split("/")[0].strip())
                        if new_page <= prev_page:
                            logger.info(
                                "extract: page did not advance (%d), stopping",
                                new_page,
                            )
                            break
            except Exception:
                pass

        except Exception as exc:
            logger.warning("extract: pagination navigation failed: %s", exc)
            break

    logger.info(
        "extract: total %d visits from %d pages", len(all_visits), total_pages
    )
    return all_visits
