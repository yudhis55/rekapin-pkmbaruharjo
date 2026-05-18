"""EMR navigation: dashboard -> PENDAFTARAN INDUK page."""
from __future__ import annotations

import logging

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from config.selectors import Selectors
from scraper.exceptions import NavigationError, SelectorNotFoundError

logger = logging.getLogger(__name__)


async def go_to_pendaftaran_induk(page: Page, selectors: Selectors) -> None:
    """Click PENDAFTARAN INDUK link and wait for the patient list page.

    Caller must have already logged in (page on dashboard).

    Raises:
        SelectorNotFoundError: PENDAFTARAN INDUK link not found.
        NavigationError: Click succeeded but daftar page didn't load.
    """
    link_sel = selectors.dashboard.pendaftaran_induk_link
    table_sel = selectors.daftar.patient_table

    try:
        await page.wait_for_selector(link_sel, timeout=10_000)
    except PlaywrightTimeoutError as exc:
        raise SelectorNotFoundError(
            f"PENDAFTARAN INDUK link not found: {link_sel}"
        ) from exc

    logger.info("navigation: clicking PENDAFTARAN INDUK")
    await page.click(link_sel)

    # Wait for daftar page (URL match OR table appears)
    try:
        await page.wait_for_selector(table_sel, timeout=15_000)
    except PlaywrightTimeoutError as exc:
        raise NavigationError(
            f"daftar page did not load (table {table_sel} not found)"
        ) from exc

    if "/daf/px/" not in page.url:
        raise NavigationError(f"unexpected URL after navigation: {page.url}")
    logger.info("navigation: arrived at %s", page.url)


async def is_logged_in(page: Page, selectors: Selectors) -> bool:
    """Quick session check: are we on a logged-in page?

    Returns True if PENDAFTARAN INDUK link visible OR currently on /daf/px/.
    Returns False if login form fields visible.
    """
    # Fast positive signal: URL is on a /daf/px/ subpage
    if "/daf/px/" in page.url:
        try:
            await page.wait_for_selector(selectors.daftar.patient_table, timeout=2000)
            return True
        except PlaywrightTimeoutError:
            pass

    # Dashboard signal
    try:
        await page.wait_for_selector(selectors.dashboard.pendaftaran_induk_link, timeout=2000)
        return True
    except PlaywrightTimeoutError:
        pass

    # If login form is visible, definitely not logged in
    try:
        await page.wait_for_selector(selectors.login.username_input, timeout=2000)
        return False
    except PlaywrightTimeoutError:
        # Inconclusive - fall through to False (safer)
        return False
