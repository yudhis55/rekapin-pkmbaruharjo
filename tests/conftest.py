"""Shared pytest fixtures for rekap-in test suite."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop() -> Any:
    """Create event loop for async tests (session-scoped to share across tests)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[Any, None]:
    """In-memory async SQLite session.

    NOTE: Real implementation in Task 8 (db/session.py). This is a placeholder
    fixture that yields None for now. Tests in Task 5 will override it.
    """
    yield None


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set test env vars for config tests."""
    monkeypatch.setenv("EMR_USERNAME", "test_user")
    monkeypatch.setenv("EMR_PASSWORD", "test_pass")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "PUSKESMAS TEST")
    monkeypatch.setenv("BROWSER_MODE", "headless")
    monkeypatch.setenv("SCRAPE_TIMEOUT", "30")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8000")
