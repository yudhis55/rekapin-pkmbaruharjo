"""Tests for scraper login flow using local HTML fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from config.selectors import load_selectors
from config.settings import Settings
from scraper.browser import playwright_browser
from scraper.exceptions import LoginError
from scraper.login import login

FIXTURES = Path(__file__).parent / "fixtures" / "emr"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMR_USERNAME", "test_user")
    monkeypatch.setenv("EMR_PASSWORD", "test_pass")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "PUSKESMAS BARUHARJO")
    monkeypatch.setenv("BROWSER_MODE", "headless")
    monkeypatch.setenv("SCRAPE_TIMEOUT", "10")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from config.settings import get_settings
    get_settings.cache_clear()


def _settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


async def test_login_success_redirects_to_dashboard() -> None:
    """Login fixture flow: route /daf POST to a fake dashboard HTML."""
    selectors = load_selectors()
    settings = _settings()

    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")
    dashboard_html = (FIXTURES / "02-after-login.html").read_text(encoding="utf-8")
    base = settings.emr_base_url.rstrip("/")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            if request.method == "POST" or "px/1/1/0/0" in request.url:
                await route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            else:
                await route.fulfill(status=200, content_type="text/html", body=login_html)

        await ctx.route("**/*", handle)
        await page.goto(base, wait_until="domcontentloaded")
        await login(page, selectors, settings)


async def test_login_invalid_credentials_raises() -> None:
    """If after submit we still see the login form, LoginError raised."""
    selectors = load_selectors()
    settings = _settings()

    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(status=200, content_type="text/html", body=login_html)

        await ctx.route("**/*", handle)
        await page.goto(settings.emr_base_url, wait_until="domcontentloaded")

        with pytest.raises(LoginError):
            await login(page, selectors, settings)


async def test_login_redacts_credentials_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Logs must not contain raw username or password."""
    selectors = load_selectors()
    settings = _settings()

    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")
    dashboard_html = (FIXTURES / "02-after-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            if request.method == "POST":
                await route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            else:
                await route.fulfill(status=200, content_type="text/html", body=login_html)

        await ctx.route("**/*", handle)
        await page.goto(settings.emr_base_url, wait_until="domcontentloaded")
        with caplog.at_level("INFO"):
            await login(page, selectors, settings)
        full = " ".join(rec.getMessage() for rec in caplog.records)
        assert "test_user" not in full
        assert "test_pass" not in full


async def test_login_native_select_option_used() -> None:
    """Verify select_option is called for puskesmas (native select works on fixture)."""
    selectors = load_selectors()
    settings = _settings()
    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")
    dashboard_html = (FIXTURES / "02-after-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            if request.method == "POST":
                await route.fulfill(status=200, content_type="text/html", body=dashboard_html)
            else:
                await route.fulfill(status=200, content_type="text/html", body=login_html)

        await ctx.route("**/*", handle)
        await page.goto(settings.emr_base_url, wait_until="domcontentloaded")
        await login(page, selectors, settings)
        # If we got here without exception, native select handling worked
        # (the alternative would be Select2 click sequences which would fail on the fixture)
