"""Tests for extract module using local fixture."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from config.selectors import load_selectors
from scraper.browser import playwright_browser
from scraper.exceptions import SessionExpiredError
from scraper.extract import _parse_dmy_date, _redact_rm, extract_visits

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
async def test_extract_returns_visits_from_fixture() -> None:
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

        visits = await extract_visits(
            page, selectors, fallback_date=date(2026, 5, 16)
        )

    # The real fixture has many patients - we expect at least 1 visit
    assert len(visits) >= 1
    # Spot-check structure
    v = visits[0]
    assert v.no_rm
    assert v.nama
    assert v.ruang
    assert v.tanggal_kunjungan is not None
    assert v.total_biaya == Decimal("0.00")
    assert v.treatments == ()


@pytest.mark.asyncio
async def test_extract_calls_progress_callback_per_row() -> None:
    selectors = load_selectors()
    daftar_html = (FIXTURES / "03-pendaftaran-induk.html").read_text(encoding="utf-8")

    progress_calls: list[tuple[int, int, str]] = []

    async def cb(current: int, total: int, label: str) -> None:
        progress_calls.append((current, total, label))

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(
                status=200, content_type="text/html", body=daftar_html
            )

        await ctx.route("**/*", handle)
        await page.goto(
            "https://example.test/daf/px/1/1/0/0", wait_until="domcontentloaded"
        )
        await extract_visits(page, selectors, on_progress=cb)

    # First call is (0, total, "starting extraction"), then per-row updates
    assert len(progress_calls) >= 2
    assert progress_calls[0][0] == 0
    assert progress_calls[0][2] == "starting extraction"
    # Subsequent calls have incrementing current
    assert progress_calls[1][0] == 1


@pytest.mark.asyncio
async def test_extract_handles_empty_table() -> None:
    """Empty <tbody> returns empty list, not error."""
    selectors = load_selectors()
    empty_html = """
    <html><body>
    <table class="table table-sm table-bordered table-hover small">
      <thead><tr><th>No</th></tr></thead>
      <tbody></tbody>
    </table>
    <a href="https://example.test/daf/px/1/1/0/0">PENDAFTARAN INDUK</a>
    </body></html>
    """

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(
                status=200, content_type="text/html", body=empty_html
            )

        await ctx.route("**/*", handle)
        await page.goto(
            "https://example.test/daf/px/1/1/0/0", wait_until="domcontentloaded"
        )

        visits = await extract_visits(page, selectors)
        assert visits == []


@pytest.mark.asyncio
async def test_extract_raises_when_session_expired() -> None:
    """If is_logged_in returns False, SessionExpiredError raised."""
    selectors = load_selectors()
    # A login page (no patient table, no PENDAFTARAN INDUK link)
    login_html = (FIXTURES / "01-login.html").read_text(encoding="utf-8")

    async with playwright_browser(headless=True) as (browser, ctx, page):

        async def handle(route, request):
            await route.fulfill(
                status=200, content_type="text/html", body=login_html
            )

        await ctx.route("**/*", handle)
        await page.goto(
            "https://example.test/daf", wait_until="domcontentloaded"
        )

        with pytest.raises(SessionExpiredError):
            await extract_visits(page, selectors)


@pytest.mark.asyncio
async def test_extract_does_not_log_full_rm_or_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PII redaction: full no_rm and nama must NOT appear in INFO logs."""
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
        with caplog.at_level("INFO"):
            visits = await extract_visits(page, selectors)

    if not visits:
        pytest.skip("no visits produced from fixture")
    full_log = " ".join(rec.getMessage() for rec in caplog.records)
    sample = visits[0]
    # The full no_rm should NOT appear in logs (only redacted form)
    if len(sample.no_rm) >= 4:
        assert sample.no_rm not in full_log
    # The full nama should NOT appear in INFO logs
    assert sample.nama not in full_log


def test_parse_dmy_date_valid() -> None:
    """Unit test for date parsing helper."""
    assert _parse_dmy_date("01/01/1990") == date(1990, 1, 1)
    assert _parse_dmy_date("16-05-2026 16:09") == date(2026, 5, 16)
    assert _parse_dmy_date("") is None
    assert _parse_dmy_date(None) is None
    assert _parse_dmy_date("not a date") is None


def test_redact_rm() -> None:
    """Unit test for RM redaction helper."""
    assert _redact_rm("PATIENT_089") == "PA*********"
    assert _redact_rm("AB") == "**"
    assert _redact_rm("A") == "**"
    assert _redact_rm("12345") == "12***"
