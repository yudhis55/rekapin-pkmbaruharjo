"""Tests for filter module."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from config.selectors import load_selectors
from scraper.browser import playwright_browser
from scraper.filter import apply_filter
from scraper.ruang_map import resolve_ruang_id, RUANG_ALL_VALUE

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


# --- Unit tests for resolve_ruang_id ---


def test_resolve_ruang_id_known_name() -> None:
    assert resolve_ruang_id("POLI UMUM") == "150"
    assert resolve_ruang_id("UGD") == "145"


def test_resolve_ruang_id_none_returns_all() -> None:
    assert resolve_ruang_id(None) == RUANG_ALL_VALUE
    assert resolve_ruang_id("") == RUANG_ALL_VALUE


def test_resolve_ruang_id_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown ruang name"):
        resolve_ruang_id("BOGUS RUANG")


def test_resolve_ruang_id_case_insensitive() -> None:
    assert resolve_ruang_id("poli umum") == "150"
    assert resolve_ruang_id("  UGD  ") == "145"


# --- Integration test with Playwright ---


@pytest.mark.asyncio
async def test_apply_filter_sets_date_and_ruang() -> None:
    selectors = load_selectors()
    daftar_html = (FIXTURES / "03-pendaftaran-induk.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(
                status=200, content_type="text/html", body=daftar_html
            )

        await ctx.route("**/*", handle)
        await page.goto(
            "https://example.test/daf/px/1/1/0/0", wait_until="domcontentloaded"
        )

        await apply_filter(page, selectors, date(2026, 5, 15), "POLI UMUM")
        # If we got here without exception, the form interaction worked
        # Verify the date input was filled
        val = await page.input_value("input[name='tanggal']")
        assert val == "2026-05-15"
