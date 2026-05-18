"""Async Playwright browser context manager."""
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Literal

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config.settings import get_settings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@asynccontextmanager
async def playwright_browser(
    headless: bool | None = None,
) -> AsyncIterator[tuple[Browser, BrowserContext, Page]]:
    """Yield (browser, context, page) and ensure cleanup.

    If headless is None, read browser_mode from settings.
    """
    if headless is None:
        mode: Literal["headless", "visible"] = get_settings().browser_mode
        headless = mode == "headless"

    timeout_ms = get_settings().scrape_timeout * 1000

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=USER_AGENT,
        )
        context.set_default_timeout(timeout_ms)
        page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()
