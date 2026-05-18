"""Apply date + ruang filters to EMR patient list page."""
from __future__ import annotations

import logging
from datetime import date

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from config.selectors import Selectors
from scraper.exceptions import FilterError, SelectorNotFoundError
from scraper.ruang_map import resolve_ruang_id

logger = logging.getLogger(__name__)


def _format_date_for_emr(d: date) -> str:
    """EMR uses HTML date input -> YYYY-MM-DD."""
    return d.isoformat()


async def apply_filter(
    page: Page,
    selectors: Selectors,
    tanggal: date,
    ruang: str | None = None,
) -> None:
    """Set date + ruang filters and submit.

    Args:
        page: Page already on the patient list (/daf/px/1/...).
        selectors: Loaded selectors.
        tanggal: Single date to filter (EMR has only one date input).
        ruang: Display name or None for all ruang.

    Note: EMR filter is per single date. For range scraping, the orchestrator
    loops dates and calls apply_filter per day.
    """
    daftar = selectors.daftar

    try:
        await page.wait_for_selector(daftar.date_filter, timeout=5000)
    except PlaywrightTimeoutError as exc:
        raise SelectorNotFoundError(
            f"date filter not found: {daftar.date_filter}"
        ) from exc

    # Set date
    formatted = _format_date_for_emr(tanggal)
    logger.info("filter: setting tanggal=%s ruang=%s", formatted, ruang or "ALL")
    await page.fill(daftar.date_filter, formatted)

    # Set ruang
    ruang_value = resolve_ruang_id(ruang)
    try:
        await page.select_option(daftar.ruang_filter, value=ruang_value)
    except PlaywrightTimeoutError as exc:
        raise FilterError(f"ruang filter rejected value {ruang_value!r}") from exc

    # Click apply (form submit -> page reload)
    try:
        async with page.expect_navigation(
            wait_until="domcontentloaded", timeout=15_000
        ):
            await page.click(daftar.apply_filter_button)
    except PlaywrightTimeoutError:
        # Some forms reload the same URL without firing a navigation event;
        # wait for the table to (re)appear instead
        try:
            await page.wait_for_selector(daftar.patient_table, timeout=10_000)
        except PlaywrightTimeoutError as exc:
            raise FilterError("table did not refresh after apply") from exc
