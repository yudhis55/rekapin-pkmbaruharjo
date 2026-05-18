"""EMR login flow.

Discovered behavior (Task 7 / docs/EMR-FLOW.md):
- Form: <form name="form" method="post" action="https://emrtrenggalek.my.id/daf">
- Puskesmas: native <select name="id_cabang"> wrapped in Select2; native select_option works
- Username: input[name="user"]
- Password: input[name="pass"]
- Submit: input[name="submit"][value="Login"]
- Success indicator: <a href="https://emrtrenggalek.my.id/daf/px/1/1/0/0">PENDAFTARAN INDUK</a> appears
- Failure indicator: still on login page, possibly with error banner
"""
from __future__ import annotations

import logging

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from config.selectors import Selectors
from config.settings import Settings
from scraper.exceptions import LoginError, SelectorNotFoundError

logger = logging.getLogger(__name__)


async def login(page: Page, selectors: Selectors, settings: Settings) -> None:
    """Perform full login flow against EMR.

    Args:
        page: An open Playwright page on the EMR base URL.
        selectors: Loaded selectors from config/selectors.yaml.
        settings: App settings with credentials.

    Raises:
        SelectorNotFoundError: If required form elements not present.
        LoginError: If credentials invalid or login flow fails.
    """
    base_url = settings.emr_base_url
    logger.info("login: starting flow at %s for puskesmas %s", base_url, settings.emr_puskesmas)

    # Navigate (caller may have already done this; navigate idempotently)
    if not page.url.startswith(base_url.rstrip("/")):
        await page.goto(base_url, wait_until="domcontentloaded")

    login_sel = selectors.login

    try:
        await page.wait_for_selector(login_sel.puskesmas_select, timeout=10_000)
    except PlaywrightTimeoutError as exc:
        raise SelectorNotFoundError(
            f"puskesmas dropdown not found: {login_sel.puskesmas_select}"
        ) from exc

    # Select puskesmas (native select option by value)
    await page.select_option(login_sel.puskesmas_select, value=login_sel.puskesmas_value)

    # Fill credentials
    await page.fill(login_sel.username_input, settings.emr_username.get_secret_value())
    await page.fill(login_sel.password_input, settings.emr_password.get_secret_value())

    # Submit
    await page.click(login_sel.submit_button)

    # Wait for either success (PENDAFTARAN INDUK link) or stay-on-login (failure)
    try:
        await page.wait_for_selector(
            selectors.dashboard.pendaftaran_induk_link,
            timeout=15_000,
        )
        logger.info("login: success for puskesmas %s", settings.emr_puskesmas)
    except PlaywrightTimeoutError as exc:
        # Still on login? Failure.
        login_form_visible = await page.locator(login_sel.username_input).count() > 0
        if login_form_visible:
            raise LoginError("invalid credentials or login form rejected") from exc
        raise LoginError(
            "login submitted but dashboard link not found within timeout"
        ) from exc
