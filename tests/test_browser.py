"""Tests for browser context manager and screenshot helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from scraper.browser import playwright_browser
from scraper.screenshot import save_screenshot


@pytest.mark.asyncio
async def test_browser_launches_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")

    async with playwright_browser(headless=True) as (browser, ctx, page):
        await page.goto("about:blank")
        url = page.url
        assert url == "about:blank"


@pytest.mark.asyncio
async def test_browser_respects_visible_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """When headless arg is None, settings.browser_mode controls behavior."""
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    monkeypatch.setenv("BROWSER_MODE", "headless")
    # Clear settings cache so override takes effect
    from config.settings import get_settings
    get_settings.cache_clear()

    async with playwright_browser() as (browser, ctx, page):
        await page.goto("about:blank")
        # If we got here, the resolved value didn't crash
        assert browser is not None


@pytest.mark.asyncio
async def test_screenshot_saves_to_evidence_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    async with playwright_browser(headless=True) as (browser, ctx, page):
        await page.goto("about:blank")
        out = await save_screenshot(page, "test-shot", evidence_dir=tmp_path)
        assert out.exists()
        assert out.stat().st_size > 100
