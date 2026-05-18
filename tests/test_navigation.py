"""Tests for navigation module using local fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from config.selectors import load_selectors
from scraper.browser import playwright_browser
from scraper.exceptions import NavigationError, SelectorNotFoundError
from scraper.navigation import go_to_pendaftaran_induk, is_logged_in

FIXTURES = Path(__file__).parent / "fixtures" / "emr"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    monkeypatch.setenv("BROWSER_MODE", "headless")
    monkeypatch.setenv("SCRAPE_TIMEOUT", "10")
    from config.settings import get_settings
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_navigation_to_daftar_succeeds() -> None:
    selectors = load_selectors()
    dashboard_html = (FIXTURES / "02-after-login.html").read_text(encoding="utf-8")
    daftar_html = (FIXTURES / "03-pendaftaran-induk.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            if "/px/1/1/0/0" in request.url:
                await route.fulfill(status=200, content_type="text/html", body=daftar_html)
            else:
                await route.fulfill(status=200, content_type="text/html", body=dashboard_html)

        await ctx.route("**/*", handle)
        await page.goto("https://example.test/daf", wait_until="domcontentloaded")

        await go_to_pendaftaran_induk(page, selectors)
        assert "/daf/px/" in page.url


@pytest.mark.asyncio
async def test_navigation_missing_link_raises() -> None:
    selectors = load_selectors()
    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(status=200, content_type="text/html", body=login_html)

        await ctx.route("**/*", handle)
        await page.goto("https://example.test/daf", wait_until="domcontentloaded")

        with pytest.raises(SelectorNotFoundError):
            await go_to_pendaftaran_induk(page, selectors)


@pytest.mark.asyncio
async def test_is_logged_in_detects_login_page() -> None:
    selectors = load_selectors()
    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(status=200, content_type="text/html", body=login_html)

        await ctx.route("**/*", handle)
        await page.goto("https://example.test/daf", wait_until="domcontentloaded")

        assert await is_logged_in(page, selectors) is False


@pytest.mark.asyncio
async def test_is_logged_in_detects_dashboard() -> None:
    selectors = load_selectors()
    dashboard_html = (FIXTURES / "02-after-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(status=200, content_type="text/html", body=dashboard_html)

        await ctx.route("**/*", handle)
        await page.goto("https://example.test/daf", wait_until="domcontentloaded")

        assert await is_logged_in(page, selectors) is True
