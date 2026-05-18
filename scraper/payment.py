"""Payment page scraper: click Bayar → parse tindakan tables → click Selesai."""
from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from config.selectors import Selectors
from scraper.exceptions import PaymentPageError  # noqa: F401
from scraper.types import TreatmentData

logger = logging.getLogger(__name__)


def _parse_currency(text: str) -> Decimal:
    """Parse Indonesian currency string to Decimal.

    Examples: 'Rp 50.000' → 50000, '10,000' → 10000, '0' → 0.00
    """
    if not text or text.strip() in ("-", "", "0"):
        return Decimal("0.00")
    # Remove Rp, spaces, dots (thousands sep), commas (thousands sep)
    cleaned = re.sub(r"[Rp\s.]", "", text.strip())
    cleaned = cleaned.replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0.00")


def _parse_date(text: str) -> date | None:
    """Parse date from DD/MM/YYYY or DD-MM-YYYY format (with optional time)."""
    if not text or text.strip() in ("-", ""):
        return None
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


async def _parse_tindakan_table(
    page: Page,
    table_selector: str,
    table_index: int,
    row_selector: str,
    cell_tanggal: str,
    cell_nama: str,
    cell_total: str,
    kategori: str,
) -> list[TreatmentData]:
    """Parse one tindakan table (biasa=index 0, lab=index 1).

    The payment page has two tables matching the tindakan_table selector
    (table.table-sm.table-bordered:has(tr.table-info)). Index 0 = biasa, 1 = lab.

    Table structure per row type:
    - Header row: tr.table-info → Tanggal | Nama Tindakan | Total | . | .
    - Sub-header row: td[0]=category name, td[1]=Tambah Jasa form, td[2]=subtotal
    - Data row: tr[style*=background-color:transparent] →
        td[0]=date (font-size:10px), td[1]=nama, td[2]=total, td[3]=X btn, td[4]=bayar btn
    """
    treatments: list[TreatmentData] = []

    try:
        tables = page.locator(table_selector)
        count = await tables.count()
        if count <= table_index:
            logger.debug("payment: table index %d not found (only %d tables)", table_index, count)
            return treatments

        table = tables.nth(table_index)
        rows = table.locator(row_selector)
        n = await rows.count()

        for i in range(n):
            row = rows.nth(i)
            # Skip header rows (tr.table-info)
            class_attr = await row.get_attribute("class") or ""
            if "table-info" in class_attr:
                continue

            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count < 3:
                continue

            tanggal_text = (await cells.nth(0).inner_text()).strip()
            nama_text = (await cells.nth(1).inner_text()).strip()
            total_text = (await cells.nth(2).inner_text()).strip()

            # Skip sub-header rows (e.g. "POLI UMUM" with "Tambah Jasa" button)
            if "Tambah Jasa" in nama_text:
                continue

            # Skip rows where nama is empty or is a column header
            if not nama_text or nama_text == "Nama Tindakan":
                continue

            # Data rows have style="background-color:transparent"
            # Sub-header rows do NOT have this style — use date presence as filter
            style_attr = await row.get_attribute("style") or ""
            has_transparent_bg = "background-color" in style_attr and "transparent" in style_attr

            # If row doesn't have transparent bg and has no parseable date, it's a sub-header
            parsed_date = _parse_date(tanggal_text)
            if not has_transparent_bg and not parsed_date:
                continue

            # Clean nama_text: remove trailing form button text artifacts (X, bayar)
            nama_clean = re.sub(r"\s*(X|bayar)\s*$", "", nama_text).strip()
            if not nama_clean:
                continue

            treatments.append(
                TreatmentData(
                    nama_tindakan=nama_clean,
                    biaya=_parse_currency(total_text),
                    kategori=kategori,
                    tanggal=parsed_date,
                )
            )
    except Exception as exc:
        logger.warning("payment: failed to parse %s table: %s", kategori, exc)

    return treatments


async def extract_payment_details(
    page: Page,
    selectors: Selectors,
    bayar_url: str,
) -> tuple[list[TreatmentData], Decimal]:
    """Navigate to payment page, extract tindakan from both tables, click Selesai.

    Args:
        page: Playwright page (currently on daftar page).
        selectors: Loaded selectors.
        bayar_url: Full URL of payment page (from form action).

    Returns:
        Tuple of (treatments list, total_biaya).
        Returns ([], Decimal("0.00")) if payment page not accessible.

    Raises:
        PaymentPageError: If navigation or parsing critically fails.
    """
    payment = selectors.payment

    # Navigate directly to payment URL (more reliable than form search after pagination)
    try:
        logger.info("payment: navigating to %s", bayar_url)
        await page.goto(bayar_url, wait_until="networkidle", timeout=15_000)
        await page.wait_for_timeout(500)

        # Verify we're on payment page
        if "/daf/px/20/1/" not in page.url:
            logger.warning("payment: unexpected URL after navigation: %s", page.url)
            return [], Decimal("0.00")

        logger.info("payment: on payment page %s", page.url)

    except PlaywrightTimeoutError as exc:
        logger.warning("payment: timeout navigating to payment page %s: %s", bayar_url, exc)
        return [], Decimal("0.00")
    except Exception as exc:
        logger.warning("payment: error navigating to payment page %s: %s", bayar_url, exc)
        return [], Decimal("0.00")

    # Parse both tindakan tables
    # Selector "table.table-sm.table-bordered:has(tr.table-info)" matches exactly
    # the 2 tindakan tables: biasa (index 0) and lab (index 1)
    treatments_biasa = await _parse_tindakan_table(
        page,
        table_selector=payment.tindakan_table,
        table_index=0,
        row_selector=payment.row,
        cell_tanggal=payment.cell_tanggal,
        cell_nama=payment.cell_nama_tindakan,
        cell_total=payment.cell_total,
        kategori="biasa",
    )

    treatments_lab = await _parse_tindakan_table(
        page,
        table_selector=payment.tindakan_table,
        table_index=1,
        row_selector=payment.row,
        cell_tanggal=payment.cell_tanggal,
        cell_nama=payment.cell_nama_tindakan,
        cell_total=payment.cell_total,
        kategori="lab",
    )

    all_treatments = treatments_biasa + treatments_lab
    total_biaya = sum((t.biaya for t in all_treatments), Decimal("0.00"))

    logger.info(
        "payment: found %d treatments (biasa=%d, lab=%d), total=%s",
        len(all_treatments),
        len(treatments_biasa),
        len(treatments_lab),
        total_biaya,
    )

    # Click Selesai to return to daftar
    try:
        selesai = page.locator(payment.selesai_button).first
        selesai_count = await selesai.count()
        if selesai_count > 0:
            await selesai.click()
            await page.wait_for_load_state("networkidle", timeout=10_000)
            logger.info("payment: clicked Selesai, back to %s", page.url)
        else:
            # Fallback: look for button with text "Selesai"
            selesai_btn = page.locator("button:has-text('Selesai')").first
            btn_count = await selesai_btn.count()
            if btn_count > 0:
                await selesai_btn.click()
                await page.wait_for_load_state("networkidle", timeout=10_000)
            else:
                logger.warning("payment: Selesai button not found, navigating back")
                await page.go_back()
                await page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception as exc:
        logger.warning("payment: error clicking Selesai: %s", exc)
        try:
            await page.go_back()
        except Exception:
            pass

    return all_treatments, total_biaya
