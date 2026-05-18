"""Tests for index page and ruang API."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "p")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/t.db")
    from config.settings import get_settings
    get_settings.cache_clear()
    import app.db.session as db_mod
    db_mod._engine = None
    db_mod._sessionmaker = None
    yield


def test_index_returns_200_with_today_date() -> None:
    from app.main import create_app
    from datetime import date as _date
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert _date.today().isoformat() in r.text


def test_index_includes_ruang_list_in_html() -> None:
    """The ruang list is loaded via JS fetch (not server-rendered).

    Verify the index page contains the JS hooks needed: a #ruang select element
    and a script that loads from /api/ruang.
    """
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        # The select element exists for JS to populate
        assert 'id="ruang"' in r.text
        # Static js loaded
        assert "/static/js/app.js" in r.text


def test_api_ruang_returns_list() -> None:
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/api/ruang")
        assert r.status_code == 200
        data = r.json()
        assert "ruang" in data
        assert isinstance(data["ruang"], list)
        assert len(data["ruang"]) > 0
