"""Tests for payment page scraper."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from config.selectors import load_selectors
from scraper.browser import playwright_browser
from scraper.payment import _parse_currency, _parse_date, extract_payment_details

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


class TestParseCurrency:
    """Unit tests for _parse_currency."""

    def test_rp_with_dots(self) -> None:
        assert _parse_currency("Rp 50.000") == Decimal("50000")

    def test_comma_thousands(self) -> None:
        assert _parse_currency("10,000") == Decimal("10000")

    def test_plain_number(self) -> None:
        assert _parse_currency("50000") == Decimal("50000")

    def test_zero(self) -> None:
        assert _parse_currency("0") == Decimal("0.00")

    def test_dash(self) -> None:
        assert _parse_currency("-") == Decimal("0.00")

    def test_empty(self) -> None:
        assert _parse_currency("") == Decimal("0.00")


class TestParseDate:
    """Unit tests for _parse_date."""

    def test_slash_format(self) -> None:
        assert _parse_date("16/05/2026") == date(2026, 5, 16)

    def test_dash_format(self) -> None:
        assert _parse_date("01-01-1990") == date(1990, 1, 1)

    def test_with_time(self) -> None:
        assert _parse_date("01/01/1990 19:02") == date(1990, 1, 1)

    def test_dash_returns_none(self) -> None:
        assert _parse_date("-") is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date("") is None

    def test_invalid_returns_none(self) -> None:
        assert _parse_date("not a date") is None


@pytest.mark.asyncio
async def test_extract_payment_handles_missing_bayar_form() -> None:
    """If Bayar form not found, returns empty list without exception."""
    selectors = load_selectors()
    simple_html = """<html><body>
    <a href="/daf/px/1/1/0/0">PENDAFTARAN INDUK</a>
    </body></html>"""

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(status=200, content_type="text/html", body=simple_html)

        await ctx.route("**/*", handle)
        await page.goto(
            "https://example.test/daf/px/1/1/0/0", wait_until="domcontentloaded"
        )

        treatments, total = await extract_payment_details(
            page, selectors, "https://example.test/daf/px/20/1/0/12345"
        )
        assert treatments == []
        assert total == Decimal("0.00")


@pytest.mark.asyncio
async def test_extract_payment_parses_fixture() -> None:
    """Parse tindakan from the real payment page fixture."""
    selectors = load_selectors()
    payment_html = (FIXTURES / "06-payment-page.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):
        call_count = {"n": 0}

        async def handle(route, request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First request: daftar page with a Bayar form
                daftar_html = """<html><body>
                <form action="https://example.test/daf/px/20/1/0/12345" method="post">
                    <input name="csrf_token_name" value="test">
                    <button type="submit">Bayar</button>
                </form>
                </body></html>"""
                await route.fulfill(
                    status=200, content_type="text/html", body=daftar_html
                )
            else:
                # Subsequent: serve payment page fixture
                await route.fulfill(
                    status=200, content_type="text/html", body=payment_html
                )

        await ctx.route("**/*", handle)
        await page.goto(
            "https://example.test/daf/px/1/1/0/0", wait_until="domcontentloaded"
        )

        treatments, total = await extract_payment_details(
            page, selectors, "https://example.test/daf/px/20/1/0/12345"
        )

        # Fixture has 1 treatment: "Pelayanan Rawat Jalan" with biaya 10,000
        assert len(treatments) >= 1
        assert any(t.nama_tindakan == "Pelayanan Rawat Jalan" for t in treatments)
        assert total == Decimal("10000")

        # Verify treatment structure
        t = next(t for t in treatments if t.nama_tindakan == "Pelayanan Rawat Jalan")
        assert t.biaya == Decimal("10000")
        assert t.kategori == "biasa"
        assert t.tanggal == date(1990, 1, 1)
